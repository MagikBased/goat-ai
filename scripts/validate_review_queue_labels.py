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


def queue_sources(queue: dict, queue_path: Path) -> dict[str, tuple[Path, dict[int, dict]]]:
    """Index the exact replay bytes and decision indices offered for review."""
    if (queue.get("schema_version") != 1
            or queue.get("purpose") != "human_review_candidates_not_training_labels"
            or not isinstance(queue.get("selected"), list)
            or not isinstance(queue.get("checkpoint_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", queue["checkpoint_sha256"]) is None):
        raise ValueError("expected a policy-review queue with selected decisions")
    sources: dict[str, tuple[Path, dict[int, dict]]] = {}
    for item in queue["selected"]:
        if not isinstance(item, dict):
            raise TypeError("invalid queue decision")
        digest = item.get("trajectory_sha256")
        path = item.get("trajectory")
        index = item.get("decision_index")
        if (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or not isinstance(path, str) or not path
                or type(index) is not int or index < 0
                or type(item.get("seat")) is not int
                or item["seat"] not in (0, 1)
                or type(item.get("viewer_frame")) is not int
                or item["viewer_frame"] != index + 1
                or type(item.get("turn")) is not int or item["turn"] < 1
                or not isinstance(item.get("phase"), str)
                or type(item.get("legal_action_count")) is not int
                or item["legal_action_count"] < 2
                or not isinstance(item.get("policy_action"), dict)
                or not isinstance(item.get("teacher_action"), dict)):
            raise ValueError("queue decision lacks replay identity or index")
        replay = Path(path)
        if not replay.is_absolute():
            replay = queue_path.parent / replay
        replay = replay.resolve()
        if digest in sources:
            prior, indices = sources[digest]
            if replay != prior or index in indices:
                raise ValueError("queue has conflicting or duplicate replay decisions")
            indices[index] = item
        else:
            sources[digest] = (replay, {index: item})
    if not sources:
        raise ValueError("review queue has no selected decisions")
    return sources


def _action_summary(action) -> dict:
    """Compare JSON queue actions to the replay's structured legal actions."""
    return {"kind": action.kind,
            "parameters": json.loads(json.dumps(action.parameters))}


def verify_queue_items(trajectory, offered: dict[int, dict], checkpoint_sha256: str) -> None:
    """Reject stale display metadata before trusting a shortlisted frame."""
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("demonstrator_seat")
    if (trajectory.source != "policy_evaluation" or seat not in (0, 1)
            or metadata.get("policy_checkpoint_sha256") != checkpoint_sha256):
        raise ValueError("queue replay differs from its declared policy checkpoint")
    for index, item in offered.items():
        if index >= len(trajectory.decisions):
            raise ValueError("queue decision index exceeds source replay")
        record = trajectory.decisions[index]
        if (record.observation.acting_player != seat
                or item["seat"] != seat
                or item["turn"] != record.observation.turn
                or item["phase"] != record.observation.phase
                or item["legal_action_count"] != len(record.legal_actions)
                or item["policy_action"] != _action_summary(record.selected_action)
                or item["teacher_action"] not in [
                    _action_summary(action) for action in record.legal_actions]):
            raise ValueError("queue decision metadata differs from source replay")


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
            raise TypeError(f"{label_path}: label export must be an object")
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
        verify_queue_items(trajectory, offered, queue["checkpoint_sha256"])
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
            "policy_checkpoint_sha256": queue["checkpoint_sha256"],
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
