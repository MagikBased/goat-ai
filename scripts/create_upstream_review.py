"""Make a separate review queue for an earlier decision that caused a bad prompt.

For example, a forced MST target choice may follow an avoidable activation.
The source queue and its saved labels are never changed.
"""

import argparse
import json
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.shortlist_policy_disagreements import action_summary, write_review_index
from scripts.validate_review_queue_labels import queue_sources, verify_queue_items


def create_upstream_review(queue_path: Path, item_number: int, upstream_index: int,
                           output: Path, native_root: Path) -> Path:
    """Offer an earlier legal pass as a human-review candidate, not a label."""
    queue_path = queue_path.resolve()
    output = output.resolve()
    if output == queue_path or output.with_suffix(".html") == queue_path.with_suffix(".html"):
        raise ValueError("upstream output must not replace the source queue")
    if output.parent != queue_path.parent:
        raise ValueError("upstream queue must share the source queue's viewer directory")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    sources = queue_sources(queue, queue_path)
    if type(item_number) is not int or not 1 <= item_number <= len(queue["selected"]):
        raise ValueError("review item number is outside the source queue")
    item = queue["selected"][item_number - 1]
    digest = item["trajectory_sha256"]
    replay_path, offered = sources[digest]
    if sha256_file(replay_path) != digest:
        raise ValueError("source replay changed")
    trajectory = read_trajectory(replay_path)
    verify_queue_items(trajectory, offered, queue["checkpoint_sha256"])
    verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
    audit_trajectory_visibility(trajectory)
    if (type(upstream_index) is not int or upstream_index < 0
            or upstream_index >= item["decision_index"]):
        raise ValueError("upstream decision must precede the reviewed prompt")
    prior = trajectory.decisions[upstream_index]
    target = trajectory.decisions[item["decision_index"]]
    if prior.observation.acting_player != target.observation.acting_player:
        raise ValueError("upstream and target decisions belong to different players")
    passes = [action for action in prior.legal_actions if action.kind == "pass"]
    if len(passes) != 1 or prior.selected_action.kind == "pass":
        raise ValueError("upstream decision must have a distinct legal pass")
    viewer_path, _ = item["viewer"].split("#", 1)
    viewer = Path(viewer_path).resolve()
    if not viewer.is_file() or not viewer.is_relative_to(queue_path.parent):
        raise ValueError("source viewer is missing or outside the queue directory")
    candidate = {
        "trajectory": str(replay_path), "trajectory_sha256": digest,
        "decision_index": upstream_index, "viewer_frame": upstream_index + 1,
        "seat": prior.observation.acting_player,
        "turn": prior.observation.turn, "phase": prior.observation.phase,
        "legal_action_count": len(prior.legal_actions),
        "policy_action": action_summary(prior.selected_action),
        "teacher_action": action_summary(passes[0]),
        "teacher_disagrees": True,
        "audit_flags": ["review_upstream_activation"],
        "viewer": f"{viewer}#decision={upstream_index + 1}",
    }
    result = {
        "schema_version": 1,
        "purpose": "human_review_candidates_not_training_labels",
        "checkpoint_sha256": queue["checkpoint_sha256"],
        "source_queue_sha256": sha256_file(queue_path),
        "source_item_number": item_number,
        "selected": [candidate],
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != rendered:
        raise ValueError("upstream queue already exists with different contents")
    output.write_text(rendered, encoding="utf-8")
    write_review_index([candidate], output, native_root, comparison_label="Pass candidate")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path)
    parser.add_argument("item_number", type=int, help="one-based number shown in queue")
    parser.add_argument("upstream_index", type=int, help="zero-based source decision index")
    parser.add_argument("--output", type=Path,
                        help="new JSON beside the source queue; defaults to upstream_N.json")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    args = parser.parse_args()
    output = args.output or args.queue.parent / f"upstream_{args.item_number}.json"
    print(create_upstream_review(args.queue, args.item_number, args.upstream_index,
                                 output, args.native_root))


if __name__ == "__main__":
    main()
