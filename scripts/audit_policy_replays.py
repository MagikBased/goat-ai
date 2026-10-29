"""Verify greedy or sampled replays and shortlist visible decisions for review."""

import argparse
import json
from collections import Counter
from pathlib import Path

from goat_ai.agents import (
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.agents.card_metadata import load_weak_flip_monster_attack
from goat_ai.agents.tactical_guard import (
    BLACK_LUSTER_SOLDIER,
    BREAKER_THE_MAGICAL_WARRIOR,
    CHAOS_SORCERER,
    safe_idle_own_ring_indices,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.replay_review import (
    HEAVY_STORM,
    MYSTICAL_SPACE_TYPHOON,
    NOBLEMAN_OF_CROSSOUT,
    RAIGEKI_BREAK,
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

VISIBLE_OWN_CARD_LOSSES = frozenset({
    "nobleman_only_own_set_monster",
    "heavy_storm_only_own_backrow",
    "heavy_storm_negative_visible_trade",
    # The forced target remains a review prompt; count its optional activation.
    "breaker_targets_own_card_with_enemy_option",
    "bls_targets_itself_with_enemy_option",
    "chaos_sorcerer_targets_itself_with_enemy_option",
    "mst_targets_own_card_with_enemy_option",
    "raigeki_break_targets_own_card_with_enemy_option",
    "tribe_race_hits_only_own_with_enemy_option",
    "tribe_race_hits_only_own_no_enemy_option",
    "mst_idle_only_own_backrow",
    "raigeki_break_idle_only_own_field",
    "ring_idle_only_own_faceup",
    "ring_targets_own_with_safe_enemy_option",
    "breaker_activates_with_only_own_backrow",
    "owned_chaos_boss_activates_without_enemy_monster",
})

ACTIVATION_OPPORTUNITY_CATEGORIES = (
    "nobleman_only_own_set_monster", "heavy_storm_only_own_backrow",
    "mst_idle_only_own_backrow", "raigeki_break_idle_only_own_field",
    "ring_idle_only_own_faceup", "breaker_activates_with_only_own_backrow",
    "owned_chaos_boss_activates_without_enemy_monster")


def own_card_activation_opportunities(trajectory, seat: int) -> dict[str, int]:
    """Count distinct visible own-only removal opportunities in visited states."""
    seen: set[tuple[str, int, str]] = set()
    for record in trajectory.decisions:
        obs = record.observation
        if obs.acting_player != seat or obs.turn_player != seat:
            continue
        own_sets = any(card.controller == seat and card.zone == "monster"
                       and card.position == "facedown" for card in obs.field)
        enemy_sets = any(card.controller != seat and card.zone == "monster"
                         and card.position == "facedown" for card in obs.field)
        own_backrow = [card for card in obs.field
                       if card.controller == seat and card.zone == "spell_trap"]
        enemy_backrow = any(card.controller != seat and card.zone == "spell_trap"
                            for card in obs.field)
        own_monsters = any(card.controller == seat and card.zone == "monster"
                           for card in obs.field)
        enemy_monsters = any(card.controller != seat and card.zone == "monster"
                             for card in obs.field)
        can_pass = any(action.kind == "pass" for action in record.legal_actions)
        if (len(safe_idle_own_ring_indices(
                obs, record.legal_actions, range(len(record.legal_actions))))
                < len(record.legal_actions)):
            seen.add(("ring_idle_only_own_faceup", obs.turn, obs.phase))
        for action in record.legal_actions:
            if action.kind not in ("activate", "chain"):
                continue
            code = action.parameters.get("code")
            if (action.kind == "activate" and code == NOBLEMAN_OF_CROSSOUT
                    and own_sets and not enemy_sets):
                seen.add(("nobleman_only_own_set_monster", obs.turn, obs.phase))
            elif (action.kind in ("activate", "chain") and can_pass
                  and code == BREAKER_THE_MAGICAL_WARRIOR
                  and own_backrow and not enemy_backrow):
                seen.add(("breaker_activates_with_only_own_backrow",
                          obs.turn, obs.phase))
            elif (action.kind in ("activate", "chain") and can_pass
                  and code in (BLACK_LUSTER_SOLDIER, CHAOS_SORCERER)
                  and not enemy_monsters
                  and any(card.controller == seat and card.zone == "monster"
                          and card.sequence == action.parameters.get("sequence")
                          and card.code == code and card.owner == seat
                          for card in obs.field)):
                seen.add(("owned_chaos_boss_activates_without_enemy_monster",
                          obs.turn, obs.phase))
            elif action.kind == "activate" and code == HEAVY_STORM and not enemy_backrow:
                source_is_set = action.parameters.get("location") == 8 and any(
                    card.sequence == action.parameters.get("sequence")
                    and card.code == HEAVY_STORM for card in own_backrow)
                if len(own_backrow) - int(source_is_set) > 0:
                    seen.add(("heavy_storm_only_own_backrow", obs.turn, obs.phase))
            elif (len(record.legal_actions) > 1 and not obs.chain
                  and code in (MYSTICAL_SPACE_TYPHOON, RAIGEKI_BREAK)):
                source_is_set = action.parameters.get("location") == 8 and any(
                    card.sequence == action.parameters.get("sequence")
                    and card.code == code for card in own_backrow)
                own_other_backrow = len(own_backrow) - int(source_is_set)
                if (code == MYSTICAL_SPACE_TYPHOON and own_other_backrow > 0
                        and not enemy_backrow):
                    seen.add(("mst_idle_only_own_backrow", obs.turn, obs.phase))
                elif (code == RAIGEKI_BREAK
                      and own_other_backrow + int(own_monsters) > 0
                      and not (enemy_backrow or enemy_monsters)):
                    seen.add(("raigeki_break_idle_only_own_field", obs.turn, obs.phase))
    return dict(sorted(Counter(category for category, _, _ in seen).items()))


def summarize_visible_own_card_losses(reports: list[dict]) -> dict:
    """Count conservative review flags with a policy-decision denominator.

    Review candidates are deduplicated by category, turn, and phase within a
    replay. The rate is for flagged instances, not all raw activations or
    opportunities. It must not be interpreted as an optimal-play error rate.
    """
    if not reports or any("verified_policy_choices" not in report
                          for report in reports):
        return {"available": False,
                "reason": "requires verified policy_evaluation reports"}
    decisions = sum(report["verified_policy_choices"] for report in reports)
    counts = Counter(candidate["category"] for report in reports
                     for candidate in report["candidates"]
                     if candidate["category"] in VISIBLE_OWN_CARD_LOSSES)
    total = sum(counts.values())
    opportunities = Counter()
    for report in reports:
        opportunities.update(report.get("visible_own_card_loss_opportunities", {}))
    rates = {category: (counts[category] / opportunities[category]
                        if opportunities[category] else None)
             for category in ACTIVATION_OPPORTUNITY_CATEGORIES}
    return {"available": True, "replays": len(reports),
            "verified_policy_choices": decisions,
            "flagged_instances": total,
            "flagged_instances_per_1000_policy_choices": (
                1000 * total / decisions if decisions else None),
            "category_counts": dict(sorted(counts.items())),
            "activation_opportunity_counts": dict(sorted(opportunities.items())),
            "flagged_per_activation_opportunity": rates,
            "counting_note": "review flags and activation opportunities deduplicated "
                             "per category, turn, and phase; not an "
                             "optimal-play error rate"}


def tactical_agent(version: int, native_root: Path, card_races):
    """Rebuild a recorded Tactical version without changing earlier guards."""
    if type(version) is not int or version not in (7, 8, 9, 10, 11, 12, 13, 14):
        raise ValueError(f"unsupported tactical teacher version: {version!r}")
    return TacticalHeuristicAgent(
        load_flip_monster_codes(native_root), card_races,
        card_facts=(load_card_facts(native_root) if version >= 9 else None),
        v8_guards=version >= 8, v9_guards=version >= 9,
        v10_guards=version >= 10, v11_guards=version >= 11,
        v12_guards=version >= 12, v13_guards=version >= 13,
        v14_guards=version >= 14)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path,
                        help="complete policy_evaluation, sampled self_play_rl, or tactical trajectories")
    parser.add_argument("--checkpoint", type=Path,
                        help="required for greedy policy replays; optionally checks a sampled replay's parent hash")
    parser.add_argument("--opponent-checkpoint", type=Path,
                        help="also reproduce the recorded opponent policy's greedy choices")
    parser.add_argument("--compare-parent-greedy", action="store_true",
                        help="for sampled self-play, test flagged states with the frozen parent checkpoint")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--include-opponent", action="store_true",
                        help="also shortlist the evaluation opponent's visible decisions; "
                             "reproduce Tactical choices or use --opponent-checkpoint")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.compare_parent_greedy and args.checkpoint is None:
        parser.error("--compare-parent-greedy requires --checkpoint")
    checkpoint_sha256 = sha256_file(args.checkpoint) if args.checkpoint else None
    opponent_sha256 = (sha256_file(args.opponent_checkpoint)
                       if args.opponent_checkpoint else None)
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
            if opponent_sha256 is not None:
                raise ValueError("--opponent-checkpoint requires a policy_evaluation replay")
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
                                 "greedy_position_guard_v1", "greedy_position_guard_v2",
                                 "greedy_own_loss_guard_v1", "greedy_own_loss_guard_v2",
                                 "greedy_own_loss_guard_v3",
                                 "greedy_own_loss_guard_v4"):
                raise ValueError(f"{path}: unsupported policy inference {inference!r}")
            guarded = inference in ("greedy_tactical_guard_v3", "greedy_tactical_guard_v4",
                                    "greedy_tactical_guard_v5")
            policy = load_policy_agent(
                args.checkpoint, tactical_guard=guarded,
                card_races=card_races if guarded else None,
                weak_flip_attacks=(weak_flip_attacks
                                   if inference == "greedy_tactical_guard_v4" else None),
                self_target_guard=inference == "greedy_tactical_guard_v5",
                own_loss_guard=inference in ("greedy_own_loss_guard_v1",
                                             "greedy_own_loss_guard_v2",
                                             "greedy_own_loss_guard_v3",
                                             "greedy_own_loss_guard_v4"),
                own_loss_guard_version=(2 if inference == "greedy_own_loss_guard_v2"
                                        else 4 if inference == "greedy_own_loss_guard_v4"
                                        else 3 if inference == "greedy_own_loss_guard_v3"
                                        else 1),
                card_facts=(card_facts if inference == "greedy_own_loss_guard_v2" else None),
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
            own_card_opportunities = own_card_activation_opportunities(
                trajectory, policy_seat)
            if opponent_sha256 is not None:
                if metadata.get("opponent_checkpoint_sha256") != opponent_sha256:
                    raise ValueError(f"{path}: opponent checkpoint SHA-256 differs from recording")
                opponent_policy = load_policy_agent(args.opponent_checkpoint)
                opponent_choices = 0
                for index, decision in enumerate(trajectory.decisions):
                    if decision.observation.acting_player == policy_seat:
                        continue
                    chosen = opponent_policy.select_action(
                        decision.observation, decision.legal_actions)
                    if chosen != decision.selected_action:
                        raise ValueError(f"{path}: opponent choice differs at decision {index}")
                    opponent_choices += 1
                provenance["opponent_checkpoint_sha256"] = opponent_sha256
                provenance["verified_opponent_choices"] = opponent_choices
            elif args.include_opponent and metadata.get("opponent") == "TacticalHeuristicAgent":
                opponent_teacher = tactical_agent(metadata.get("opponent_version"),
                                                  args.native_root, card_races)
                opponent_choices = 0
                for index, decision in enumerate(trajectory.decisions):
                    if decision.observation.acting_player == policy_seat:
                        continue
                    chosen = opponent_teacher.select_action(decision.observation,
                                                            decision.legal_actions)
                    if chosen != decision.selected_action:
                        raise ValueError(f"{path}: tactical opponent choice differs at "
                                         f"decision {index}")
                    opponent_choices += 1
                provenance["verified_opponent_choices"] = opponent_choices
        elif trajectory.source == "tactical":
            if opponent_sha256 is not None:
                raise ValueError("--opponent-checkpoint requires a policy_evaluation replay")
            metadata = trajectory.skill_metadata or {}
            version = metadata.get("teacher_version")
            if metadata.get("teacher") != "TacticalHeuristicAgent":
                raise ValueError(f"{path}: unsupported tactical teacher version")
            teacher_seat = metadata.get("demonstrator_seat")
            if type(teacher_seat) is not int or teacher_seat not in (0, 1):
                raise ValueError(f"{path}: tactical replay lacks a valid teacher seat")
            teacher = tactical_agent(version, args.native_root, card_races)
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
                "choice_verification": ("reproduced_greedy" if opponent_sha256 is not None
                                        else "reproduced_tactical_teacher"
                                        if "verified_opponent_choices" in provenance
                                        else "native_replay_only_not_agent_reproduced"),
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
            **({"visible_own_card_loss_opportunities": own_card_opportunities}
               if trajectory.source == "policy_evaluation" else {}),
            "candidates": [candidate.to_dict() for candidate in candidates],
            **({"parent_greedy_review": parent_greedy_review}
               if parent_policy is not None else {}),
            "opponent_review": opponent_review,
        })
    result = {"schema_version": 1, "replays": reports,
              "visible_own_card_losses": summarize_visible_own_card_losses(reports)}
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
