"""Compare matched greedy-policy duels with and without forced-choice forwards."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import torch

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training.checkpoint import load_policy_agent
from goat_ai.training.policy import encode_decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--deck-a", type=Path,
                        default=Path("examples/decks/control_probe.ydk"))
    parser.add_argument("--deck-b", type=Path,
                        default=Path("examples/decks/chaos_probe.ydk"))
    parser.add_argument("--seed", type=int, default=12000)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--max-decisions", type=int, default=5000)
    args = parser.parse_args()
    if min(args.games, args.rounds, args.max_decisions) < 1:
        parser.error("games, rounds, and max-decisions must be positive")

    def run_schedule(reference: bool):
        started = perf_counter()
        trajectories = []
        forced = 0
        for seed in range(args.seed, args.seed + args.games):
            agent = load_policy_agent(args.checkpoint)
            agents = (agent, RandomAgent(seed + 1)) if seed % 2 == 0 else (
                RandomAgent(seed + 1), agent)
            with GoatEnvironment(str(args.deck_a), str(args.deck_b), seed=seed,
                                 engine=ExperimentalOcgcoreEngine(args.native_root)) as env:
                observation = env.reset()
                for _ in range(args.max_decisions):
                    legal = env.legal_actions()
                    if observation.acting_player == seed % 2 and len(legal) == 1:
                        forced += 1
                        if reference:
                            features = encode_decision(observation, legal,
                                                       agent.vocabulary,
                                                       agent.model.feature_version)
                            with torch.inference_mode():
                                agent.model(features.to(next(agent.model.parameters()).device))
                    action = agents[observation.acting_player].select_action(
                        observation, legal)
                    observation = env.step(action)
                    if env.is_terminal():
                        trajectories.append(env.trajectory())
                        break
                else:
                    raise RuntimeError(f"duel exceeded {args.max_decisions} decisions: {seed}")
        return perf_counter() - started, trajectories, forced

    rounds = []
    for index in range(args.rounds):
        order = ("reference", "shortcut") if index % 2 == 0 else (
            "shortcut", "reference")
        measurements = {}
        trajectories = {}
        for mode in order:
            elapsed, trajectories[mode], forced = run_schedule(mode == "reference")
            measurements[mode] = elapsed
        if trajectories["reference"] != trajectories["shortcut"]:
            raise AssertionError("forced-choice shortcut changed native trajectories")
        rounds.append({"order": order,
                       "reference_seconds": measurements["reference"],
                       "shortcut_seconds": measurements["shortcut"],
                       "speedup": measurements["reference"] / measurements["shortcut"],
                       "decisions": [len(t.decisions) for t in trajectories["shortcut"]],
                       "forced_greedy_choices": forced,
                       "matched_trajectories": True})
    print(json.dumps({"checkpoint_sha256": sha256_file(args.checkpoint),
                      "deck_sha256": [sha256_file(args.deck_a), sha256_file(args.deck_b)],
                      "torch_version": str(torch.__version__),
                      "torch_threads": torch.get_num_threads(),
                      "seed": args.seed, "games": args.games,
                      "rounds": rounds}, indent=2))


if __name__ == "__main__":
    main()
