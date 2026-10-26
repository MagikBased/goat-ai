"""Verify policy replays and shortlist visible-state decisions for human review."""

import argparse
import json
from pathlib import Path

from goat_ai.agents import load_card_races
from goat_ai.agents.card_metadata import load_weak_flip_monster_attack
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.replay_review import category_counts, review_candidates
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path,
                        help="complete policy_evaluation trajectory JSON files")
    parser.add_argument("--checkpoint", type=Path, required=True,
                        help="verify every policy decision against these saved weights")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checkpoint_sha256 = sha256_file(args.checkpoint)
    card_races = load_card_races(args.native_root)
    weak_flip_attacks = load_weak_flip_monster_attack(args.native_root)
    reports = []
    for path in args.replays:
        trajectory = read_trajectory(path)
        verified = verify_trajectory(
            trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        candidates = review_candidates(trajectory, card_races, weak_flip_attacks)
        metadata = trajectory.skill_metadata or {}
        if metadata.get("policy_checkpoint_sha256") != checkpoint_sha256:
            raise ValueError(f"{path}: checkpoint SHA-256 differs from recording")
        if metadata.get("policy_inference_version") != POLICY_INFERENCE_VERSION:
            raise ValueError(f"{path}: policy inference version differs")
        inference = metadata.get("policy_inference")
        if inference not in ("greedy", "greedy_tactical_guard_v3"):
            raise ValueError(f"{path}: unsupported policy inference {inference!r}")
        guarded = inference == "greedy_tactical_guard_v3"
        policy = load_policy_agent(
            args.checkpoint, tactical_guard=guarded,
            card_races=card_races if guarded else None)
        if metadata.get("policy_feature_version") != policy.model.feature_version:
            raise ValueError(f"{path}: policy feature version differs")
        policy_seat = metadata["demonstrator_seat"]
        policy_choices = 0
        for index, decision in enumerate(trajectory.decisions):
            if decision.observation.acting_player != policy_seat:
                continue
            chosen = policy.select_action(decision.observation,
                                          decision.legal_actions)
            if chosen != decision.selected_action:
                raise ValueError(f"{path}: policy choice differs at decision {index}")
            policy_choices += 1
        reports.append({
            "trajectory": str(path),
            "trajectory_sha256": sha256_file(path),
            "checkpoint_sha256": checkpoint_sha256,
            "policy_seat": policy_seat,
            "verified_policy_choices": policy_choices,
            "seed": trajectory.seed,
            "winner": trajectory.winner,
            "verified_decisions": verified,
            "category_counts": category_counts(candidates),
            "candidates": [candidate.to_dict() for candidate in candidates],
        })
    result = {"schema_version": 1, "replays": reports}
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(json.dumps({"output": str(args.output), "replays": len(reports),
                          "candidates": sum(len(r["candidates"]) for r in reports)}))
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
