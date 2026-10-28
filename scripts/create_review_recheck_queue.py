"""Make a fresh review queue for decisions with ambiguous earlier choices.

Old choices identify frames to revisit; their action selections are never copied.
The source queue and labels must pass the normal replay and provenance checks.
"""

import argparse
import json
from pathlib import Path

from goat_ai.replay.fingerprint import sha256_file
from scripts.refresh_review_queue import refresh_review_queue
from scripts.render_replay import render_replay
from scripts.validate_review_queue_labels import queue_sources, validate_labels


def create_recheck_queue(source_queue: Path, labels_dir: Path, output: Path,
                         native_root: Path, *, refresh: bool = True) -> int:
    source_queue = source_queue.resolve()
    labels_dir = labels_dir.resolve()
    output = output.resolve()
    label_paths = sorted(labels_dir.glob("*.json"))
    if not label_paths:
        raise ValueError("no saved review choices found")
    if output == source_queue:
        raise ValueError("recheck queue must not replace the source queue")

    source = json.loads(source_queue.read_text(encoding="utf-8"))
    sources = queue_sources(source, source_queue)
    # This also replay-verifies every referenced duel, audits player visibility,
    # and checks that each saved choice is legal and within the offered queue.
    validate_labels(source_queue, label_paths, native_root)
    selected_keys = set()
    for path in label_paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        digest = raw["source_trajectory_sha256"]
        selected_keys.update((digest, choice["decision_index"])
                             for choice in raw["choices"])

    selected = []
    for item in source["selected"]:
        digest = item["trajectory_sha256"]
        if (digest, item["decision_index"]) not in selected_keys:
            continue
        replay, _ = sources[digest]
        viewer = output.parent / "queue_viewers" / f"{replay.stem}_{digest[:12]}.html"
        selected.append({**item, "viewer": f"{viewer}#decision={item['viewer_frame']}"})
    if len(selected) != len(selected_keys):
        raise ValueError("saved choices do not match distinct source queue frames")

    recheck = {"schema_version": 1,
               "purpose": "human_review_candidates_not_training_labels",
               "checkpoint_sha256": source["checkpoint_sha256"],
               "selection": "ambiguous_saved_choice_recheck",
               "source_queue_sha256": sha256_file(source_queue),
               "selected": selected}
    encoded = json.dumps(recheck, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != encoded:
        raise ValueError("recheck queue already exists with different contents")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding="utf-8")
    if refresh:
        refresh_review_queue(output, native_root)
        # The separate reveal view helps diagnose a play without granting the
        # label view or future training data access to hidden information.
        rendered = set()
        for item in selected:
            viewer = Path(item["viewer"].split("#", 1)[0])
            if viewer in rendered:
                continue
            rendered.add(viewer)
            render_replay(Path(item["trajectory"]), viewer.with_suffix(".review.html"),
                          native_root, reviewer_reveal=True)
        refresh_review_queue(output, native_root, index_only=True)
    return len(selected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_queue", type=Path)
    parser.add_argument("labels_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    args = parser.parse_args()
    count = create_recheck_queue(args.source_queue, args.labels_dir,
                                 args.output, args.native_root)
    print(f"{args.output.resolve()}: {count} decisions ready for fresh review")


if __name__ == "__main__":
    main()
