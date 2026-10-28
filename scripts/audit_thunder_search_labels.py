"""Count Thunder Dragon search labels in a checkpoint's exact source replays.

Checks the checkpoint's recorded trajectory SHA-256 values. This is a label
audit, not a substitute for native replay or visibility verification.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import torch

from goat_ai.evaluation.thunder_search_audit import thunder_search_choice
from goat_ai.replay import read_trajectory
from goat_ai.replay.fingerprint import sha256_file


def audit(checkpoint: Path) -> dict:
    metadata = torch.load(checkpoint, map_location="cpu", weights_only=True)
    sources = metadata.get("trajectory_sha256")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("checkpoint has no trajectory SHA-256 provenance")
    counts = Counter()
    zero_examples = []
    for name, expected_sha256 in sources.items():
        path = Path(name)
        if sha256_file(path) != expected_sha256:
            raise ValueError(f"checkpoint trajectory hash mismatch: {path}")
        trajectory = read_trajectory(path)
        info = trajectory.skill_metadata or {}
        seat = info.get("demonstrator_seat")
        version = info.get("teacher_version")
        if (trajectory.source != "tactical" or type(seat) is not int
                or seat not in (0, 1) or type(version) is not int):
            raise ValueError(f"unsupported demonstrator provenance: {path}")
        for index, record in enumerate(trajectory.decisions):
            choice = thunder_search_choice(record, seat)
            if choice is None:
                continue
            counts[(version, choice)] += 1
            if choice == "take_zero":
                zero_examples.append({"trajectory": str(path),
                                      "decision_index": index,
                                      "viewer_frame": index + 1})
    versions = sorted({version for version, _ in counts})
    return {"schema_version": 1, "checkpoint": str(checkpoint),
            "checkpoint_sha256": sha256_file(checkpoint),
            "source_trajectories": len(sources),
            "counts_by_teacher_version": {
                str(version): {choice: count for (v, choice), count in counts.items()
                               if v == version} for version in versions},
            "zero_copy_examples": zero_examples}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.checkpoint)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
