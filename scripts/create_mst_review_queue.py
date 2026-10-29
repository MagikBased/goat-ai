"""Create a no-label MST activation queue from verified greedy policy replays."""

import argparse
import json
from collections import Counter
from pathlib import Path

from goat_ai.agents import load_card_facts
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION
from scripts.catalog_mst_contexts import catalog_trajectory
from scripts.render_replay import render_replay
from scripts.shortlist_policy_disagreements import (
    action_summary,
    recorded_policy_options,
    write_review_index,
)
from scripts.validate_review_queue_labels import queue_sources, verify_queue_items


def select_mst_items(candidates: list[dict], limit: int,
                     per_replay: int) -> list[dict]:
    """Spread review across contexts and games without assigning play labels."""
    if limit < 1 or per_replay < 1:
        raise ValueError("review limits must be positive")
    selected = []
    per_path = Counter()
    order = {"own_only": 0, "enemy_only": 1, "mixed": 2, "none": 3}
    for item in sorted(candidates, key=lambda x: (
            order[x["visible_backrow_distribution"]], x["trajectory"],
            x["decision_index"])):
        path = item["trajectory"]
        if per_path[path] >= per_replay:
            continue
        selected.append(item)
        per_path[path] += 1
        if len(selected) >= limit:
            break
    return selected


def create_queue(checkpoint: Path, replay_paths: list[Path], output: Path,
                 native_root: Path, *, limit: int = 24, per_replay: int = 2) -> dict:
    """Verify exact visible decisions and render a locally reviewable queue."""
    output = output.resolve()
    checkpoint_hash = sha256_file(checkpoint)
    facts = load_card_facts(native_root)
    candidates = []
    source_replays = {}
    agents = {}
    for path in replay_paths:
        path = path.resolve()
        trajectory = read_trajectory(path)
        metadata = trajectory.skill_metadata or {}
        seat = metadata.get("demonstrator_seat")
        inference = metadata.get("policy_inference")
        if (trajectory.source != "policy_evaluation" or type(seat) is not int
                or seat not in (0, 1)
                or metadata.get("policy_checkpoint_sha256") != checkpoint_hash
                or metadata.get("policy_inference_version") != POLICY_INFERENCE_VERSION):
            raise ValueError(f"{path}: expected a replay from this greedy checkpoint")
        if inference not in agents:
            agents[inference] = load_policy_agent(
                checkpoint, **recorded_policy_options(inference, facts))
        agent = agents[inference]
        verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
        audit_trajectory_visibility(trajectory)
        for index, record in enumerate(trajectory.decisions):
            if record.observation.acting_player == seat and agent.select_action(
                    record.observation, record.legal_actions) != record.selected_action:
                raise ValueError(f"{path}: saved policy choice differs at {index}")
        source_replays[str(path)] = trajectory
        digest = sha256_file(path)
        for row in catalog_trajectory(trajectory, facts):
            index = row["decision_index"]
            record = trajectory.decisions[index]
            if len(record.legal_actions) < 2:
                continue
            candidates.append({
                "trajectory": str(path), "trajectory_sha256": digest,
                "decision_index": index, "viewer_frame": index + 1,
                "seat": seat, "turn": row["turn"], "phase": row["phase"],
                "legal_action_count": len(record.legal_actions),
                "policy_action": action_summary(record.selected_action),
                "teacher_action": action_summary(record.selected_action),
                "teacher_disagrees": False,
                "audit_flags": ["mst_context_" + row["visible_backrow_distribution"]],
                "visible_backrow_distribution": row["visible_backrow_distribution"],
                "pass_offered": row["pass_offered"],
            })
    selected = select_mst_items(candidates, limit, per_replay)
    if not selected:
        raise ValueError("no reviewable selected MST activation was found")
    viewer_dir = output.parent / (output.stem + "_viewers")
    viewer_dir.mkdir(parents=True, exist_ok=True)
    viewers = {}
    for item in selected:
        path = item["trajectory"]
        if path not in viewers:
            digest = item["trajectory_sha256"]
            viewer = viewer_dir / f"{Path(path).stem}_{digest[:12]}.html"
            render_replay(Path(path), viewer, native_root)
            render_replay(Path(path), viewer.with_suffix(".review.html"),
                          native_root, reviewer_reveal=True)
            viewers[path] = viewer.resolve()
        item["viewer"] = f"{viewers[path]}#decision={item['viewer_frame']}"
    result = {
        "schema_version": 1,
        "purpose": "human_review_candidates_not_training_labels",
        "checkpoint_sha256": checkpoint_hash,
        "selected": selected,
    }
    sources = queue_sources(result, output)
    for digest, (path, offered) in sources.items():
        if sha256_file(path) != digest:
            raise ValueError("source replay changed while building queue")
        verify_queue_items(source_replays[str(path)], offered, checkpoint_hash)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != rendered:
        raise ValueError("queue already exists with different contents")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    write_review_index(selected, output, native_root,
                       comparison_label="No recommendation")
    return {"queue": str(output), "items": len(selected),
            "contexts": dict(sorted(Counter(
                item["visible_backrow_distribution"] for item in selected).items())),
            "queue_sha256": sha256_file(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--per-replay", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(create_queue(args.checkpoint, args.replays, args.output,
                                  args.native_root, limit=args.limit,
                                  per_replay=args.per_replay)))


if __name__ == "__main__":
    main()
