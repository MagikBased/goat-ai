"""Verify greedy or sampled replays and shortlist visible decisions for review."""

import argparse
import json
from pathlib import Path

from goat_ai.agents import (
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.agents.card_metadata import load_weak_flip_monster_attack
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.replay_review import (
    category_counts,
    compare_parent_greedy_candidates,
    review_candidates,
    sampled_self_play_provenance,
)
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path,
                        help="complete policy_evaluation, sampled self_play_rl, or tactical trajectories")
    parser.add_argument("--checkpoint", type=Path,
                        help="required for greedy policy replays; optionally checks a sampled replay's parent hash")
    parser.add_argument("--compare-parent-greedy", action="store_true",
                        help="for sampled self-play, test flagged states with the frozen parent checkpoint")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--include-opponent", action="store_true",
                        help="also shortlist the evaluation opponent's visible decisions; "
                             "native replay verified, but agent choices are not reproduced")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.compare_parent_greedy and args.checkpoint is None:
        parser.error("--compare-parent-greedy requires --checkpoint")
    checkpoint_sha256 = sha256_file(args.checkpoint) if args.checkpoint else None
    card_races = load_card_races(args.native_root)
    weak_flip_attacks = load_weak_flip_monster_attack(args.native_root)
    card_facts = load_card_facts(args.native_root)
    parent_policy = (load_policy_agent(args.checkpoint)
                     if args.compare_parent_greedy else None)
    reports = []
    for path in args.replays:
        trajectory = read_trajectory(path)
        if args.compare_parent_greedy and trajectory.source != "self_play_rl":
            raise ValueError("--compare-parent-greedy requires sampled self-play replays")
        verified = verify_trajectory(
            trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        if trajectory.source == "self_play_rl":
            provenance = sampled_self_play_provenance(trajectory, checkpoint_sha256)
        elif trajectory.source == "policy_evaluation":
            if checkpoint_sha256 is None:
                raise ValueError(f"{path}: --checkpoint is required for greedy policy replays")
            metadata = trajectory.skill_metadata or {}
            if metadata.get("policy_checkpoint_sha256") != checkpoint_sha256:
                raise ValueError(f"{path}: checkpoint SHA-256 differs from recording")
            if metadata.get("policy_inference_version") != POLICY_INFERENCE_VERSION:
                raise ValueError(f"{path}: policy inference version differs")
            inference = metadata.get("policy_inference")
            if inference not in ("greedy", "greedy_tactical_guard_v3",
                                 "greedy_tactical_guard_v4", "greedy_tactical_guard_v5",
                                 "greedy_position_guard_v1", "greedy_position_guard_v2"):
                raise ValueError(f"{path}: unsupported policy inference {inference!r}")
            guarded = inference in ("greedy_tactical_guard_v3", "greedy_tactical_guard_v4",
                                    "greedy_tactical_guard_v5")
            policy = load_policy_agent(
                args.checkpoint, tactical_guard=guarded,
                card_races=card_races if guarded else None,
                weak_flip_attacks=(weak_flip_attacks
                                   if inference == "greedy_tactical_guard_v4" else None),
                self_target_guard=inference == "greedy_tactical_guard_v5",
                position_guard=inference in ("greedy_position_guard_v1",
                                             "greedy_position_guard_v2"),
                position_guard_version=(1 if inference == "greedy_position_guard_v1" else 2))
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
            provenance = {"policy_seat": policy_seat,
                          "checkpoint_sha256": checkpoint_sha256,
                          "selection_mode": inference,
                          "selection_temperature": None,
                          "choice_verification": "reproduced_greedy",
                          "verified_policy_choices": policy_choices}
        elif trajectory.source == "tactical":
            metadata = trajectory.skill_metadata or {}
            version = metadata.get("teacher_version")
            if (metadata.get("teacher") != "TacticalHeuristicAgent"
                    or type(version) is not int or version not in (7, 8, 9, 10, 11, 12, 13, 14)):
                raise ValueError(f"{path}: unsupported tactical teacher version")
            teacher_seat = metadata.get("demonstrator_seat")
            if type(teacher_seat) is not int or teacher_seat not in (0, 1):
                raise ValueError(f"{path}: tactical replay lacks a valid teacher seat")
            teacher = TacticalHeuristicAgent(load_flip_monster_codes(args.native_root),
                                             card_races,
                                             card_facts=(load_card_facts(args.native_root)
                                                         if version >= 9 else None),
                                             v8_guards=version >= 8,
                                             v9_guards=version >= 9,
                                             v10_guards=version >= 10,
                                             v11_guards=version >= 11,
                                             v12_guards=version >= 12,
                                             v13_guards=version >= 13,
                                             v14_guards=version >= 14)
            teacher_choices = 0
            for index, decision in enumerate(trajectory.decisions):
                if decision.observation.acting_player != teacher_seat:
                    continue
                chosen = teacher.select_action(decision.observation,
                                               decision.legal_actions)
                if chosen != decision.selected_action:
                    raise ValueError(f"{path}: tactical choice differs at decision {index}")
                teacher_choices += 1
            provenance = {"teacher_seat": teacher_seat,
                          "teacher": metadata["teacher"],
                          "teacher_version": metadata["teacher_version"],
                          "choice_verification": "reproduced_tactical_teacher",
                          "verified_teacher_choices": teacher_choices}
        else:
            raise ValueError(f"{path}: unsupported trajectory source {trajectory.source!r}")
        candidates = review_candidates(trajectory, card_races, weak_flip_attacks,
                                       card_facts=card_facts)
        parent_greedy_review = (compare_parent_greedy_candidates(
            trajectory, candidates, parent_policy, card_races, weak_flip_attacks,
            card_facts)
            if parent_policy is not None else None)
        opponent_review = None
        if args.include_opponent:
            if trajectory.source != "policy_evaluation":
                raise ValueError("--include-opponent requires policy_evaluation replays")
            other_seat = 1 - provenance["policy_seat"]
            other_candidates = review_candidates(
                trajectory, card_races, weak_flip_attacks, review_seat=other_seat,
                card_facts=card_facts)
            opponent_review = {
                "seat": other_seat,
                "agent": metadata.get("opponent"),
                "agent_version": metadata.get("opponent_version"),
                "choice_verification": "native_replay_only_not_agent_reproduced",
                "category_counts": category_counts(other_candidates),
                "candidates": [candidate.to_dict() for candidate in other_candidates],
            }
        reports.append({
            "trajectory": str(path),
            "trajectory_sha256": sha256_file(path),
            "source": trajectory.source,
            **provenance,
            "seed": trajectory.seed,
            "winner": trajectory.winner,
            "verified_decisions": verified,
            "category_counts": category_counts(candidates),
            "candidates": [candidate.to_dict() for candidate in candidates],
            **({"parent_greedy_review": parent_greedy_review}
               if parent_policy is not None else {}),
            "opponent_review": opponent_review,
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
