"""Turn verified changed review choices into explicit pairwise preferences.

Only a changed choice asserts a preference over the policy's recorded action.
Matching choices and other unselected legal actions make no pairwise claim.
"""

import argparse
import json
from pathlib import Path

from goat_ai.replay import (
    read_decision_annotations,
    read_decision_preferences,
    read_trajectory,
)
from goat_ai.replay.fingerprint import sha256_file
from scripts.validate_review_queue_labels import validate_labels


def convert(queue: Path, labels: list[Path], native_root: Path,
            output_dir: Path) -> dict:
    report = validate_labels(queue, labels, native_root)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"preference output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for case in report["cases"]:
        replay = Path(case["trajectory"])
        trajectory = read_trajectory(replay)
        annotations, _ = read_decision_annotations(
            Path(case["labels"]), case["trajectory_sha256"], trajectory)
        preferences = []
        for decision_index, preferred_index in annotations.choices:
            record = trajectory.decisions[decision_index]
            recorded_index = record.legal_actions.index(record.selected_action)
            if preferred_index != recorded_index:
                preferences.append({
                    "decision_index": decision_index,
                    "preferred_action_indices": [preferred_index],
                    "disfavored_action_indices": [recorded_index],
                })
        entry = {
            "trajectory": str(replay),
            "trajectory_sha256": case["trajectory_sha256"],
            "source_labels": case["labels"],
            "source_labels_sha256": case["labels_sha256"],
            "reviewed_decisions": len(annotations.choices),
            "changed_choices": len(preferences),
            "preferences": None,
        }
        if preferences:
            payload = {
                "schema_version": 1,
                "source_trajectory_sha256": case["trajectory_sha256"],
                "authorization": "policy_review",
                "reviewer": annotations.reviewer,
                "reviewed_seat": case["reviewed_seat"],
                "source_labels_sha256": case["labels_sha256"],
                "preferences": preferences,
            }
            path = output_dir / f"{case['trajectory_sha256']}.preferences.json"
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
            read_decision_preferences(path, case["trajectory_sha256"], trajectory)
            entry["preferences"] = str(path.resolve())
            entry["preferences_sha256"] = sha256_file(path)
        cases.append(entry)
    manifest = {
        "schema_version": 1,
        "queue_sha256": report["queue_sha256"],
        "authorization": "policy_review",
        "cases": cases,
        "reviewed_decisions": sum(case["reviewed_decisions"] for case in cases),
        "changed_preferences": sum(case["changed_choices"] for case in cases),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path)
    parser.add_argument("labels", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = convert(args.queue, args.labels, args.native_root,
                       args.output_dir)
    print(json.dumps({"output_dir": str(args.output_dir),
                      "cases": len(manifest["cases"]),
                      "changed_preferences": manifest["changed_preferences"]}))


if __name__ == "__main__":
    main()
