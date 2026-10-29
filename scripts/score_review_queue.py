"""Score validated review prompts without treating suggestions as expert labels."""

import argparse
import json
from pathlib import Path

import torch

from goat_ai.agents import load_card_facts
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import encode_decision
from scripts.shortlist_policy_disagreements import recorded_policy_options
from scripts.validate_review_queue_labels import queue_sources, verify_queue_items


def _matches_summary(action, summary: dict) -> bool:
    return action.kind == summary.get("kind") and action.parameters == summary.get("parameters")


def score_item(agent, record, item: dict) -> dict:
    """Report action ranks for one visible state; infer no correctness label."""
    legal = record.legal_actions
    suggested = [index for index, action in enumerate(legal)
                 if _matches_summary(action, item["teacher_action"])]
    if len(suggested) != 1:
        raise ValueError("queue suggestion must match exactly one legal action")
    recorded = legal.index(record.selected_action)
    features = encode_decision(record.observation, legal, agent.vocabulary,
                               agent.model.feature_version)
    agent.model.eval()
    with torch.inference_mode():
        logits = agent.model(features)
    if logits.ndim != 1 or len(logits) != len(legal) or not torch.isfinite(logits).all():
        raise ValueError("policy returned invalid legal-action scores")
    selected = agent.select_action(record.observation, legal)
    best = legal.index(selected)
    return {
        "decision_index": item["decision_index"],
        "viewer_frame": item["viewer_frame"],
        "recorded_index": recorded,
        "suggested_index": suggested[0],
        "scored_choice_index": best,
        "scored_choice_kind": selected.kind,
        "scored_choice_is_recorded": best == recorded,
        "scored_choice_is_suggested": best == suggested[0],
        "recorded_minus_suggested_logit": float(logits[recorded] - logits[suggested[0]]),
        "suggestion_is_not_a_label": True,
    }


def score_queue(queue_path: Path, checkpoint_path: Path, native_root: Path) -> dict:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    sources = queue_sources(queue, queue_path)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict) or checkpoint.get("schema_version") != 1:
        raise ValueError("unsupported checkpoint schema")
    checkpoint_hash = sha256_file(checkpoint_path)
    training_hashes = set(checkpoint.get("trajectory_sha256", {}).values())
    training_seeds = {game["seed"] for game in checkpoint.get("training_games", ())}
    facts = load_card_facts(native_root)
    scored = []
    verified = 0
    for digest, (replay_path, offered) in sorted(sources.items()):
        if sha256_file(replay_path) != digest:
            raise ValueError(f"{replay_path}: replay changed since queue creation")
        trajectory = read_trajectory(replay_path)
        verify_queue_items(trajectory, offered, queue["checkpoint_sha256"])
        verified += verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
        audit_trajectory_visibility(trajectory)
        inference = trajectory.skill_metadata["policy_inference"]
        agent = load_policy_agent(checkpoint_path, **recorded_policy_options(inference, facts))
        if agent.model.feature_version != trajectory.skill_metadata["policy_feature_version"]:
            raise ValueError("scored checkpoint has a different feature version")
        for index, item in sorted(offered.items()):
            scored.append({
                "trajectory": str(replay_path), "trajectory_sha256": digest,
                "source_inference": inference,
                "exact_replay_in_scored_training": digest in training_hashes,
                "seed_in_scored_training": trajectory.seed in training_seeds,
                **score_item(agent, trajectory.decisions[index], item),
            })
        if sha256_file(replay_path) != digest:
            raise ValueError(f"{replay_path}: replay changed during scoring")
    return {
        "schema_version": 1,
        "scope": "fixed_visible_review_states_not_strength_or_training_labels",
        "queue_sha256": sha256_file(queue_path),
        "source_checkpoint_sha256": queue["checkpoint_sha256"],
        "scored_checkpoint_sha256": checkpoint_hash,
        "verified_source_decisions": verified,
        "items": sorted(scored, key=lambda item: (
            item["trajectory_sha256"], item["decision_index"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = score_queue(args.queue, args.checkpoint, args.native_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(args.output), "items": len(result["items"]),
                      "verified_source_decisions": result["verified_source_decisions"]}))


if __name__ == "__main__":
    main()
