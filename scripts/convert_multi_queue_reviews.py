"""Combine independently verified review queues into replay-bound preferences.

An upstream activation review may share a replay with a target-choice queue.
Each queue/label pair is validated against its own exact shortlisted frames
before compatible choices are combined. Matching AI plays make no preference.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from goat_ai.replay import (read_decision_annotations, read_decision_preferences,
                            read_trajectory)
from goat_ai.replay.fingerprint import sha256_file
from scripts.validate_review_queue_labels import validate_labels


def convert_pairs(pairs: list[tuple[Path, Path]], native_root: Path,
                  output_dir: Path) -> dict:
    if not pairs:
        raise ValueError("at least one queue and label pair is required")
    if len({label.resolve() for _, label in pairs}) != len(pairs):
        raise ValueError("duplicate label file")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("preference output directory is not empty")
    decisions: dict[str, dict[int, tuple[int, str]]] = defaultdict(dict)
    replays = {}
    seats = {}
    reviewers: dict[str, set[str]] = defaultdict(set)
    inputs: dict[str, list[dict]] = defaultdict(list)
    queue_hashes = {}
    input_reviewed_decisions = 0
    duplicate_review_decisions = 0
    for queue, label in pairs:
        queue_hash = sha256_file(queue)
        report = validate_labels(queue, [label], native_root)
        if sha256_file(queue) != queue_hash:
            raise ValueError("review queue changed during conversion")
        case = report["cases"][0]
        label_hash = case["labels_sha256"]
        digest = case["trajectory_sha256"]
        replay = Path(case["trajectory"])
        if sha256_file(replay) != digest:
            raise ValueError("source replay changed during conversion")
        trajectory = read_trajectory(replay)
        annotation, _ = read_decision_annotations(label, digest, trajectory)
        if sha256_file(label) != label_hash:
            raise ValueError("review label changed during conversion")
        if digest in replays and replays[digest] != replay.resolve():
            raise ValueError("same replay hash has conflicting paths")
        replays[digest] = replay.resolve()
        seat = case["reviewed_seat"]
        if digest in seats and seats[digest] != seat:
            raise ValueError("same replay has conflicting reviewed seats")
        seats[digest] = seat
        reviewers[digest].add(annotation.reviewer)
        for index, action in annotation.choices:
            input_reviewed_decisions += 1
            prior = decisions[digest].get(index)
            if prior is not None and prior[0] != action:
                raise ValueError(f"conflicting review choices for replay {digest} "
                                 f"decision {index}")
            if prior is not None:
                duplicate_review_decisions += 1
            decisions[digest][index] = (action, annotation.reviewer)
        input_record = {"queue": str(queue.resolve()),
                        "queue_sha256": queue_hash,
                        "labels": str(label.resolve()),
                        "labels_sha256": label_hash,
                        "reviewer": annotation.reviewer}
        inputs[digest].append(input_record)
        queue_hashes[str(queue.resolve())] = queue_hash

    for queue_path, queue_hash in queue_hashes.items():
        if sha256_file(Path(queue_path)) != queue_hash:
            raise ValueError("review queue changed during conversion")
    for digest, source_inputs in inputs.items():
        if sha256_file(replays[digest]) != digest:
            raise ValueError("source replay changed during conversion")
        for item in source_inputs:
            if sha256_file(Path(item["labels"])) != item["labels_sha256"]:
                raise ValueError("review label changed during conversion")

    cases = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for digest, indexed in sorted(decisions.items()):
        trajectory = read_trajectory(replays[digest])
        preferences = []
        for index, (preferred, _) in sorted(indexed.items()):
            record = trajectory.decisions[index]
            recorded = record.legal_actions.index(record.selected_action)
            if preferred != recorded:
                preferences.append({"decision_index": index,
                                    "preferred_action_indices": [preferred],
                                    "disfavored_action_indices": [recorded]})
        entry = {"trajectory": str(replays[digest]),
                 "trajectory_sha256": digest,
                 "reviewed_decisions": len(indexed),
                 "changed_preferences": len(preferences),
                 "inputs": sorted(inputs[digest], key=lambda item: (
                     item["queue"], item["labels"])),
                 "preferences": None}
        if preferences:
            payload = {"schema_version": 1,
                       "source_trajectory_sha256": digest,
                       "authorization": "policy_review",
                       "reviewer": ", ".join(sorted(reviewers[digest])),
                       "reviewed_seat": seats[digest],
                       "source_review_inputs": entry["inputs"],
                       "preferences": preferences}
            path = output_dir / f"{digest}.preferences.json"
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
            read_decision_preferences(path, digest, trajectory)
            entry["preferences"] = str(path.resolve())
            entry["preferences_sha256"] = sha256_file(path)
        cases.append(entry)
    manifest = {"schema_version": 1,
                "authorization": "policy_review",
                "queue_sha256": queue_hashes,
                "cases": cases,
                "input_reviewed_decisions": input_reviewed_decisions,
                "duplicate_review_decisions": duplicate_review_decisions,
                "reviewed_decisions": sum(item["reviewed_decisions"] for item in cases),
                "changed_preferences": sum(item["changed_preferences"] for item in cases)}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", nargs=2, action="append", required=True,
                        metavar=("QUEUE", "LABEL"))
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = convert_pairs([(Path(queue), Path(label)) for queue, label in args.case],
                             args.native_root, args.output_dir)
    print(json.dumps({"reviewed_decisions": manifest["reviewed_decisions"],
                      "input_reviewed_decisions": manifest["input_reviewed_decisions"],
                      "duplicate_review_decisions": manifest["duplicate_review_decisions"],
                      "changed_preferences": manifest["changed_preferences"],
                      "output_dir": str(args.output_dir)}))


if __name__ == "__main__":
    main()
