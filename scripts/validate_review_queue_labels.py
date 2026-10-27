"""Validate offline viewer labels against a verified policy-review queue.

This command checks provenance and legal choices. It does not train a policy
or treat a reviewer's action as a proven optimal move.
"""

import argparse
import json
import re
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_decision_annotations, read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file


def queue_sources(queue: dict, queue_path: Path) -> dict[str, tuple[Path, set[int]]]:
    """Index the exact replay bytes and decision indices offered for review."""
    if (queue.get("schema_version") != 1
            or queue.get("purpose") != "human_review_candidates_not_training_labels"
            or not isinstance(queue.get("selected"), list)):
        raise ValueError("expected a policy-review queue with selected decisions")
    sources: dict[str, tuple[Path, set[int]]] = {}
    for item in queue["selected"]:
        if not isinstance(item, dict):
            raise ValueError("invalid queue decision")
        digest = item.get("trajectory_sha256")
        path = item.get("trajectory")
        index = item.get("decision_index")
        if (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or not isinstance(path, str) or not path
                or type(index) is not int or index < 0):
            raise ValueError("queue decision lacks replay identity or index")
        replay = Path(path)
        if not replay.is_absolute():
            replay = queue_path.parent / replay
        replay = replay.resolve()
        if digest in sources:
            prior, indices = sources[digest]
            if replay != prior or index in indices:
                raise ValueError("queue has conflicting or duplicate replay decisions")
            indices.add(index)
        else:
            sources[digest] = (replay, {index})
    if not sources:
        raise ValueError("review queue has no selected decisions")
    return sources


def validate_labels(queue_path: Path, label_paths: list[Path],
                    native_root: Path) -> dict:
    """Check each export against current native assets and its shortlisted frame."""
    if not label_paths:
        raise ValueError("at least one label export is required")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    sources = queue_sources(queue, queue_path)
    checked = set()
    cases = []
    for label_path in label_paths:
        raw = json.loads(label_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"{label_path}: label export must be an object")
        digest = raw.get("source_trajectory_sha256")
        if digest not in sources:
            raise ValueError(f"{label_path}: source replay is absent from review queue")
        if digest in checked:
            raise ValueError(f"{label_path}: duplicate export for one source replay")
        checked.add(digest)
        replay_path, offered = sources[digest]
        if sha256_file(replay_path) != digest:
            raise ValueError(f"{replay_path}: source replay SHA-256 changed")
        trajectory = read_trajectory(replay_path)
        verified = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
        audit_trajectory_visibility(trajectory)
        labels, records = read_decision_annotations(label_path, digest, trajectory)
        if labels.authorization != "policy_review":
            raise ValueError(f"{label_path}: expected policy_review authorization")
        if any(index not in offered for index, _ in labels.choices):
            raise ValueError(f"{label_path}: label is outside shortlisted decisions")
        cases.append({
            "trajectory": str(replay_path),
            "trajectory_sha256": digest,
            "labels": str(label_path.resolve()),
            "labels_sha256": sha256_file(label_path),
            "reviewer": labels.reviewer,
            "reviewed_seat": trajectory.skill_metadata["demonstrator_seat"],
            "verified_decisions": verified,
            "reviewed_decisions": len(records),
            "changed_choices": sum(record.selected_action != trajectory.decisions[index].selected_action
                                   for (index, _), record in zip(labels.choices, records, strict=True)),
        })
    return {"schema_version": 1, "queue_sha256": sha256_file(queue_path),
            "authorization": "policy_review", "cases": cases,
            "verified_decisions": sum(case["verified_decisions"] for case in cases),
            "reviewed_decisions": sum(case["reviewed_decisions"] for case in cases)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path)
    parser.add_argument("labels", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_labels(args.queue, args.labels, args.native_root)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(json.dumps({"output": str(args.output), "cases": len(result["cases"]),
                          "reviewed_decisions": result["reviewed_decisions"]}))
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
