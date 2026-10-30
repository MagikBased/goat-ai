"""Confirm selected human decisions in an authorized local EDOPro duel.

Use the one-based decision numbers displayed in the GOAT AI replay viewer.
This writes a review annotation, not training-admitted data.
"""

import argparse
import hashlib
import json
from pathlib import Path

from goat_ai.replay.edopro_live_verify import (
    verify_edopro_human_annotations,
    verify_edopro_live_recording,
)
from goat_ai.replay.trajectory import read_trajectory


def confirm_frames(replay: Path, frames: list[int], native_root: Path,
                   output: Path, *, reviewer: str = "local-self") -> dict:
    """Save only reviewed, non-forced actions from the authorized human seat."""
    stem = replay.with_suffix("")
    review = stem.with_suffix(".review.json")
    metadata_path = stem.with_suffix(".meta.json")
    verified = verify_edopro_live_recording(replay, review, metadata_path, native_root)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("human_authorization") != "self_recorded":
        raise ValueError("room was not marked as an authorized self-recording")
    if not reviewer.strip() or not frames or any(type(frame) is not int or frame < 1
                                                 for frame in frames):
        raise ValueError("provide positive viewer decision numbers and a reviewer")
    if len(set(frames)) != len(frames):
        raise ValueError("viewer decision numbers must be distinct")
    trajectory = read_trajectory(review)
    seat = metadata["human_client_seat"]
    choices = []
    for frame in sorted(frames):
        index = frame - 1
        if index >= len(trajectory.decisions):
            raise ValueError(f"decision {frame} is beyond the recording")
        record = trajectory.decisions[index]
        if record.observation.acting_player != seat:
            raise ValueError(f"decision {frame} belongs to the AI seat")
        if len(record.legal_actions) < 2:
            raise ValueError(f"decision {frame} has no alternative legal action")
        choices.append({"decision_index": index,
                        "action_index": record.legal_actions.index(record.selected_action)})
    payload = {"schema_version": 1,
               "source_trajectory_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
               "authorization": "self_recorded", "reviewer": reviewer.strip(),
               "choices": choices}
    encoded = json.dumps(payload, indent=2) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != encoded:
        raise FileExistsError(f"{output} already contains different labels")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        checked = verify_edopro_human_annotations(
            replay, review, metadata_path, output, native_root)
    else:
        temporary = output.with_suffix(output.suffix + ".tmp")
        try:
            temporary.write_text(encoded, encoding="utf-8")
            checked = verify_edopro_human_annotations(
                replay, review, metadata_path, temporary, native_root)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
    return {**verified, "annotations": str(output),
            "confirmed_human_choices": checked["confirmed_human_choices"],
            "annotation_sha256": checked["annotation_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path, help="saved EDOPro room .yrpX")
    parser.add_argument("frames", type=int, nargs="+",
                        help="one-based viewer decision numbers to confirm")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path,
                        help="annotation JSON; defaults beside the room replay")
    parser.add_argument("--reviewer", default="local-self")
    args = parser.parse_args()
    output = args.output or args.replay.with_suffix(".human_labels.json")
    print(json.dumps(confirm_frames(args.replay, args.frames, args.native_root,
                                    output, reviewer=args.reviewer), indent=2))


if __name__ == "__main__":
    main()
