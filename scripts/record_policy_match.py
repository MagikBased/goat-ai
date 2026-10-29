"""Record a greedy checkpoint against a baseline or another checkpoint."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from goat_ai.agents import (
    CombatFlipHeuristicAgent,
    CombatHeuristicAgent,
    HeuristicAgent,
    RandomAgent,
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.agents.card_metadata import load_weak_flip_monster_attack
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--deck1", type=Path, required=True)
    parser.add_argument("--deck2", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=2202)
    parser.add_argument("--policy-seat", type=int, choices=(0, 1), default=0)
    opponents = parser.add_mutually_exclusive_group()
    opponents.add_argument("--opponent", choices=("combat_heuristic", "combat_flip", "tactical",
                                                   "heuristic", "random", "mirror_policy"),
                           default="combat_heuristic")
    opponents.add_argument("--opponent-checkpoint", type=Path,
                           help="play a distinct saved policy and fingerprint it in the replay")
    parser.add_argument("--opponent-own-loss-guard", action="store_true",
                        help="apply the experimental own-loss filter to a checkpoint opponent")
    parser.add_argument("--opponent-own-loss-guard-version", type=int,
                        choices=(1, 2, 3, 4, 5, 6, 7, 8), default=1)
    parser.add_argument("--max-decisions", type=int, default=3000)
    parser.add_argument("--tactical-guard", action="store_true",
                        help="apply experimental visible-state action filter to policy")
    parser.add_argument("--weak-flip-guard", action="store_true",
                        help="also prefer setting low-ATK Flip monsters; requires tactical guard")
    parser.add_argument("--self-target-guard", action="store_true",
                        help="avoid observed BLS and MST self-target losses; requires tactical guard")
    parser.add_argument("--position-guard", action="store_true",
                        help="filter defending Sheep Token switches and empty-field "
                             "attack-to-weaker-defense switches")
    parser.add_argument("--own-loss-guard", action="store_true",
                        help="experimental visible own-card-loss filter")
    parser.add_argument("--own-loss-guard-version", type=int, choices=(1, 2, 3, 4, 5, 6, 7, 8), default=1,
                        help="v2 defers one-shot MST; v3 idle own-only Ring; "
                             "v4 prefers a safe opposing Ring target; v5 combines v2 and v3; "
                             "v7 adds chained own-only MST avoidance to v1; "
                             "v8 defers negative visible Heavy Storm trades from v1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_decisions < 1:
        parser.error("--max-decisions must be positive")
    if args.weak_flip_guard and not args.tactical_guard:
        parser.error("--weak-flip-guard requires --tactical-guard")
    if args.self_target_guard and not args.tactical_guard:
        parser.error("--self-target-guard requires --tactical-guard")
    if args.self_target_guard and args.weak_flip_guard:
        parser.error("choose one experimental extension of guard v3")
    if sum((args.position_guard, args.tactical_guard, args.own_loss_guard)) > 1:
        parser.error("choose one standalone policy guard")
    if args.own_loss_guard_version != 1 and not args.own_loss_guard:
        parser.error("--own-loss-guard-version requires --own-loss-guard")
    if args.opponent_own_loss_guard and not args.opponent_checkpoint:
        parser.error("--opponent-own-loss-guard requires --opponent-checkpoint")
    if args.opponent_own_loss_guard_version != 1 and not args.opponent_own_loss_guard:
        parser.error("--opponent-own-loss-guard-version requires --opponent-own-loss-guard")
    policy_options = {
        "tactical_guard": args.tactical_guard,
        "card_races": load_card_races(args.native_root) if args.tactical_guard else None,
        "weak_flip_attacks": (load_weak_flip_monster_attack(args.native_root)
                              if args.weak_flip_guard else None),
        "self_target_guard": args.self_target_guard,
        "position_guard": args.position_guard,
        "own_loss_guard": args.own_loss_guard,
        "own_loss_guard_version": args.own_loss_guard_version,
        "card_facts": (load_card_facts(args.native_root)
                       if args.own_loss_guard and args.own_loss_guard_version in (2, 5, 6)
                       else None),
    }
    policy = load_policy_agent(args.checkpoint, **policy_options)
    opponent_options = {
        "own_loss_guard": args.opponent_own_loss_guard,
        "own_loss_guard_version": args.opponent_own_loss_guard_version,
        "card_facts": (load_card_facts(args.native_root)
                       if args.opponent_own_loss_guard
                       and args.opponent_own_loss_guard_version in (2, 5, 6)
                       else None),
    }
    flip_codes = (load_flip_monster_codes(args.native_root)
                  if args.opponent in ("combat_flip", "tactical") else frozenset())
    opponent = (load_policy_agent(args.opponent_checkpoint, **opponent_options)
                if args.opponent_checkpoint else {
                    "combat_heuristic": lambda: CombatHeuristicAgent(),
                    "combat_flip": lambda: CombatFlipHeuristicAgent(flip_codes),
                    "tactical": lambda: TacticalHeuristicAgent(
                        flip_codes, load_card_races(args.native_root),
                        card_facts=load_card_facts(args.native_root)),
                    "heuristic": lambda: HeuristicAgent(),
                    "random": lambda: RandomAgent(args.seed),
                    "mirror_policy": lambda: load_policy_agent(args.checkpoint, **policy_options),
                }[args.opponent]())
    agents = [None, None]
    agents[args.policy_seat] = policy
    agents[1 - args.policy_seat] = opponent
    with GoatEnvironment(str(args.deck1), str(args.deck2), args.seed,
                         ExperimentalOcgcoreEngine(args.native_root)) as env:
        observation = env.reset()
        for _ in range(args.max_decisions):
            action = agents[observation.acting_player].select_action(
                observation, env.legal_actions())
            observation = env.step(action)
            if env.is_terminal():
                trajectory = replace(
                    env.trajectory(), source="policy_evaluation",
                    skill_metadata={
                        "demonstrator_seat": args.policy_seat,
                        "policy_checkpoint_sha256": sha256_file(args.checkpoint),
                        "policy_inference": ("greedy_position_guard_v2"
                                             if args.position_guard else
                                             "greedy_own_loss_guard_v1"
                                             if args.own_loss_guard and args.own_loss_guard_version == 1 else
                                             "greedy_own_loss_guard_v2"
                                             if args.own_loss_guard and args.own_loss_guard_version == 2 else
                                             f"greedy_own_loss_guard_v{args.own_loss_guard_version}"
                                             if args.own_loss_guard else
                                             "greedy_tactical_guard_v5"
                                             if args.self_target_guard else
                                             "greedy_tactical_guard_v4"
                                             if args.weak_flip_guard else
                                             "greedy_tactical_guard_v3"
                                             if args.tactical_guard else "greedy"),
                        "policy_inference_version": POLICY_INFERENCE_VERSION,
                        "policy_feature_version": policy.model.feature_version,
                        "opponent": type(opponent).__name__,
                        "opponent_version": getattr(opponent, "teacher_version", 1),
                        **({"opponent_checkpoint_sha256": sha256_file(
                            args.opponent_checkpoint or args.checkpoint)}
                           if args.opponent_checkpoint or args.opponent == "mirror_policy"
                           else {}),
                        **({"opponent_inference": (
                            f"greedy_own_loss_guard_v{args.opponent_own_loss_guard_version}"
                            if args.opponent_own_loss_guard else "greedy")}
                           if args.opponent_checkpoint else {}),
                    },
                )
                args.output.parent.mkdir(parents=True, exist_ok=True)
                write_trajectory(args.output, trajectory)
                replay = read_trajectory(args.output)
                verified = verify_trajectory(
                    replay, ExperimentalOcgcoreEngine(args.native_root))
                audit_trajectory_visibility(replay)
                opponent_choices_verified = 0
                if args.opponent_checkpoint or args.opponent == "mirror_policy":
                    replay_opponent = load_policy_agent(
                        args.opponent_checkpoint or args.checkpoint,
                        **(opponent_options if args.opponent_checkpoint else policy_options))
                    for index, record in enumerate(replay.decisions):
                        if record.observation.acting_player != 1 - args.policy_seat:
                            continue
                        chosen = replay_opponent.select_action(
                            record.observation, record.legal_actions)
                        if chosen != record.selected_action:
                            raise ValueError(f"opponent checkpoint choice differs at "
                                             f"decision {index}")
                        opponent_choices_verified += 1
                print(json.dumps({"trajectory": str(args.output),
                                  "source": trajectory.source,
                                  "policy_seat": args.policy_seat,
                                  "opponent": type(opponent).__name__,
                                  "winner": env.result(), "verified_decisions": verified,
                                  "opponent_choices_verified": opponent_choices_verified},
                                 indent=2))
                return
    raise RuntimeError(f"duel exceeded {args.max_decisions} decisions")


if __name__ == "__main__":
    main()
