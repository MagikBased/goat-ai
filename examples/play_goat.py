"""Play a headless GOAT duel yourself and save a verified local demonstration."""

import argparse
import os
import tempfile
from dataclasses import replace
from pathlib import Path

from goat_ai.agents import (
    HumanAgent,
    RandomAgent,
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.agents.card_metadata import load_card_names
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck1", type=Path, required=True)
    parser.add_argument("--deck2", type=Path, required=True)
    parser.add_argument("--human-seat", type=int, choices=(0, 1), default=0)
    parser.add_argument("--opponent", choices=("random", "tactical", "policy"),
                        default="tactical")
    parser.add_argument("--checkpoint", type=Path,
                        help="required when --opponent policy")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-decisions", type=int, default=3000)
    parser.add_argument("--trajectory", type=Path, required=True)
    args = parser.parse_args()
    if args.max_decisions < 1 or args.seed < 0:
        parser.error("seed must be nonnegative and decision limit positive")
    if (args.opponent == "policy") != (args.checkpoint is not None):
        parser.error("--checkpoint is required only with --opponent policy")
    if args.trajectory.exists():
        parser.error("trajectory path already exists; choose a new file")
    checkpoint_hash = sha256_file(args.checkpoint) if args.checkpoint else None
    if args.opponent == "random":
        opponent = RandomAgent(args.seed + 1)
    elif args.opponent == "tactical":
        opponent = TacticalHeuristicAgent(
            load_flip_monster_codes(args.native_root),
            load_card_races(args.native_root),
            card_facts=load_card_facts(args.native_root))
    else:
        opponent = load_policy_agent(args.checkpoint)
    human = HumanAgent(card_names=load_card_names(args.native_root))
    agents = (human, opponent) if args.human_seat == 0 else (opponent, human)
    with GoatEnvironment(str(args.deck1), str(args.deck2), args.seed,
                         ExperimentalOcgcoreEngine(args.native_root)) as env:
        observation = env.reset()
        for _ in range(args.max_decisions):
            action = agents[observation.acting_player].select_action(
                observation, env.legal_actions())
            observation = env.step(action)
            if env.is_terminal():
                if args.checkpoint and sha256_file(args.checkpoint) != checkpoint_hash:
                    raise ValueError("opponent checkpoint changed during the duel")
                trajectory = replace(
                    env.trajectory(), source="human_cli",
                    skill_metadata={"demonstrator_seat": args.human_seat,
                                    "authorization": "self_recorded",
                                    "opponent": type(opponent).__name__,
                                    **({"opponent_version": opponent.teacher_version}
                                       if hasattr(opponent, "teacher_version") else {}),
                                    **({"opponent_checkpoint_sha256": checkpoint_hash}
                                       if checkpoint_hash else {})},
                )
                args.trajectory.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                        dir=args.trajectory.parent,
                        prefix=f".{args.trajectory.name}.", suffix=".tmp",
                        delete=False) as temporary:
                    pending = Path(temporary.name)
                try:
                    write_trajectory(pending, trajectory)
                    saved = read_trajectory(pending)
                    verify_trajectory(saved, ExperimentalOcgcoreEngine(args.native_root))
                    audit_trajectory_visibility(saved)
                    if args.trajectory.exists():
                        parser.error("trajectory path appeared during verification")
                    os.replace(pending, args.trajectory)
                finally:
                    pending.unlink(missing_ok=True)
                print(f"winner={env.result()} decisions={len(saved.decisions)}")
                print(f"verified_trajectory={args.trajectory}")
                return
    raise SystemExit(f"duel did not finish within {args.max_decisions} decisions")


if __name__ == "__main__":
    main()
