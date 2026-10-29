"""Convert explicit local rejections into replay-verified masked-parent preferences.

A rejection says only that the recorded action was bad. Every other legal
action remains eligible, with relative weights supplied by the parent policy.
"""

import argparse
import json
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import (
    read_decision_annotations,
    read_decision_preferences,
    read_trajectory,
    verify_trajectory,
)
from goat_ai.replay.fingerprint import sha256_file
from scripts.validate_review_queue_labels import queue_sources, verify_queue_items

ROOT = Path(__file__).resolve().parents[1]


def validate_rejection_provenance(preferences_path: Path, replay_path: Path,
                                  trajectory, preferences) -> tuple[str, str]:
    """Recheck the original saved human finding before a training update."""
    raw = json.loads(preferences_path.read_text(encoding="utf-8"))
    digest = sha256_file(replay_path)
    queue_name = raw.get("source_review_queue_path")
    notes_name = raw.get("source_review_notes_path")
    if (preferences.preference_kind != "reject_recorded"
            or not isinstance(queue_name, str) or not isinstance(notes_name, str)
            or not Path(queue_name).is_absolute() or not Path(notes_name).is_absolute()):
        raise ValueError("rejection lacks saved queue and note paths")
    queue_path = Path(queue_name)
    notes_path = Path(notes_name)
    queue_hash = sha256_file(queue_path)
    notes_hash = sha256_file(notes_path)
    if (raw.get("source_review_queue_sha256") != queue_hash
            or raw.get("source_review_notes_sha256") != notes_hash
            or notes_path.name != f"{digest}.json"
            or notes_path.parent.name != "notes"
            or notes_path.parent.parent.name != "_review_state"):
        raise ValueError("saved rejection provenance changed")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    sources = queue_sources(queue, queue_path)
    if digest not in sources or sources[digest][0] != replay_path.resolve():
        raise ValueError("rejection queue does not offer this replay")
    verify_queue_items(trajectory, sources[digest][1], queue["checkpoint_sha256"])
    identity = json.loads((notes_path.parent.parent / "queue_identity.json").read_text(
        encoding="utf-8"))
    if (identity.get("schema_version") != 1
            or identity.get("queue_sha256") != queue_hash
            or identity.get("queue_path") != str(queue_path.relative_to(ROOT))
            or identity.get("reviewer") != preferences.reviewer):
        raise ValueError("saved rejection reviewer or queue identity changed")
    notes = json.loads(notes_path.read_text(encoding="utf-8"))
    if (notes.get("schema_version") != 1
            or notes.get("source_trajectory_sha256") != digest
            or notes.get("reviewer") != preferences.reviewer
            or not isinstance(notes.get("notes"), list)):
        raise ValueError("saved rejection notes do not match this review")
    rejected = []
    seen = set()
    offered = sources[digest][1]
    for note in notes["notes"]:
        if (not isinstance(note, dict)
                or set(note) != {"decision_index", "kind", "text"}
                or type(note["decision_index"]) is not int
                or note["decision_index"] not in offered
                or note["decision_index"] in seen
                or note["kind"] not in ("context", "upstream_mistake",
                                        "reject_recorded")
                or not isinstance(note["text"], str)
                or len(note["text"]) > 2000):
            raise ValueError("saved rejection note is invalid or outside the queue")
        seen.add(note["decision_index"])
        if note["kind"] == "reject_recorded":
            rejected.append(note["decision_index"])
    if set(rejected) != {item.decision_index for item in preferences.preferences}:
        raise ValueError("preference decisions differ from saved rejections")
    choice_path = notes_path.parent.parent.parent / f"{digest}.json"
    if choice_path.is_file():
        annotations, _ = read_decision_annotations(choice_path, digest, trajectory)
        if (annotations.reviewer != preferences.reviewer
                or set(rejected) & {index for index, _ in annotations.choices}):
            raise ValueError("rejection conflicts with saved action choices")
    return queue_hash, notes_hash


def convert(queue_path: Path, review_dir: Path, output_dir: Path,
            native_root: Path) -> list[dict]:
    """Require queue identity, exact replay bytes, and explicit reviewer notes."""
    queue_path = queue_path.resolve()
    review_dir = review_dir.resolve()
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    sources = queue_sources(queue, queue_path)
    identity_path = review_dir / "_review_state" / "queue_identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if (identity.get("schema_version") != 1
            or identity.get("queue_sha256") != sha256_file(queue_path)
            or identity.get("queue_path") != str(queue_path.relative_to(ROOT))
            or not isinstance(identity.get("reviewer"), str)
            or not identity["reviewer"].strip()):
        raise ValueError("review folder identity does not match this queue")
    results = []
    for digest, (replay_path, offered) in sources.items():
        note_path = review_dir / "_review_state" / "notes" / f"{digest}.json"
        if not note_path.is_file():
            continue
        notes = json.loads(note_path.read_text(encoding="utf-8"))
        if (notes.get("schema_version") != 1
                or notes.get("source_trajectory_sha256") != digest
                or notes.get("reviewer") != identity["reviewer"]
                or not isinstance(notes.get("notes"), list)):
            raise ValueError(f"invalid review notes: {note_path}")
        seen_notes = set()
        for note in notes["notes"]:
            if (not isinstance(note, dict)
                    or set(note) != {"decision_index", "kind", "text"}
                    or type(note["decision_index"]) is not int
                    or note["decision_index"] not in offered
                    or note["decision_index"] in seen_notes
                    or note["kind"] not in ("context", "upstream_mistake",
                                            "reject_recorded")
                    or not isinstance(note["text"], str)
                    or len(note["text"]) > 2000):
                raise ValueError("invalid review note or decision outside this queue")
            seen_notes.add(note["decision_index"])
        rejected = [note for note in notes["notes"]
                    if note["kind"] == "reject_recorded"]
        if not rejected:
            continue
        if sha256_file(replay_path) != digest:
            raise ValueError("review source replay changed")
        trajectory = read_trajectory(replay_path)
        verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
        audit_trajectory_visibility(trajectory)
        verify_queue_items(trajectory, offered, queue["checkpoint_sha256"])
        choices_path = review_dir / f"{digest}.json"
        choices = set()
        if choices_path.is_file():
            annotations, _ = read_decision_annotations(choices_path, digest, trajectory)
            if annotations.reviewer != identity["reviewer"]:
                raise ValueError("choice reviewer differs from note reviewer")
            choices = {index for index, _ in annotations.choices}
        preferences = []
        seen = set()
        for note in rejected:
            if (set(note) != {"decision_index", "kind", "text"}
                    or type(note["decision_index"]) is not int
                    or note["decision_index"] not in offered
                    or note["decision_index"] in seen
                    or note["decision_index"] in choices
                    or not isinstance(note["text"], str)
                    or len(note["text"]) > 2000):
                raise ValueError("rejection conflicts with a choice or is outside this queue")
            index = note["decision_index"]
            seen.add(index)
            record = trajectory.decisions[index]
            bad = record.legal_actions.index(record.selected_action)
            preferences.append({
                "decision_index": index,
                "preferred_action_indices": [i for i in range(len(record.legal_actions))
                                             if i != bad],
                "disfavored_action_indices": [bad],
            })
        payload = {
            "schema_version": 1,
            "source_trajectory_sha256": digest,
            "authorization": "policy_review",
            "preference_kind": "reject_recorded",
            "reviewer": identity["reviewer"],
            "reviewed_seat": trajectory.skill_metadata["demonstrator_seat"],
            "preferences": sorted(preferences, key=lambda item: item["decision_index"]),
            "source_review_queue_path": str(queue_path),
            "source_review_queue_sha256": identity["queue_sha256"],
            "source_review_notes_path": str(note_path),
            "source_review_notes_sha256": sha256_file(note_path),
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"{digest}.preferences.json"
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        parsed = read_decision_preferences(output, digest, trajectory)
        validate_rejection_provenance(output, replay_path, trajectory, parsed)
        results.append({"trajectory": str(replay_path), "preferences": str(output),
                        "rejected_decisions": len(preferences)})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path)
    parser.add_argument("review_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    args = parser.parse_args()
    results = convert(args.queue, args.review_dir, args.output_dir, args.native_root)
    print(json.dumps({"cases": results,
                      "rejected_decisions": sum(case["rejected_decisions"]
                                                for case in results)}, indent=2))


if __name__ == "__main__":
    main()
