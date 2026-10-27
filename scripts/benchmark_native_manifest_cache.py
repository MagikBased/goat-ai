"""Compare complete native self-play duels with cached and direct asset hashes."""

import argparse
import json
import platform
import subprocess
from pathlib import Path
from time import perf_counter

import torch

from goat_ai.agents import RandomAgent
from goat_ai.engine import restricted_adapter
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training.checkpoint import load_policy_agent
from goat_ai.training.self_play import run_learning_episode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--deck-a", type=Path,
                        default=Path("examples/decks/control_probe.ydk"))
    parser.add_argument("--deck-b", type=Path,
                        default=Path("examples/decks/chaos_probe.ydk"))
    parser.add_argument("--seed", type=int, default=13000)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    if args.games < 1 or args.rounds < 1:
        parser.error("games and rounds must be positive")
    torch.set_num_threads(1)
    agent = load_policy_agent(args.checkpoint)
    cached = restricted_adapter.sha256_unchanged_file
    rounds = []
    try:
        for index in range(args.rounds):
            modes = ("direct", "cached") if index % 2 == 0 else ("cached", "direct")
            timings = {}
            trajectories = {}
            for mode in modes:
                restricted_adapter.sha256_unchanged_file = (
                    sha256_file if mode == "direct" else cached)
                started = perf_counter()
                episodes = [run_learning_episode(
                    agent.model, agent.vocabulary, RandomAgent(seed + 1),
                    (str(args.deck_a), str(args.deck_b)), seed, seed % 2,
                    lambda: ExperimentalOcgcoreEngine(args.native_root),
                    torch.Generator().manual_seed(seed),
                ) for seed in range(args.seed, args.seed + args.games)]
                timings[mode] = perf_counter() - started
                trajectories[mode] = [episode.trajectory for episode in episodes]
            if trajectories["direct"] != trajectories["cached"]:
                raise AssertionError("native trajectories differed")
            rounds.append({
                "order": modes,
                "direct_seconds": timings["direct"],
                "cached_seconds": timings["cached"],
                "speedup": timings["direct"] / timings["cached"],
                "decisions": [len(t.decisions) for t in trajectories["cached"]],
                "winners": [t.winner for t in trajectories["cached"]],
                "matched_trajectories": True,
            })
    finally:
        restricted_adapter.sha256_unchanged_file = cached
    print(json.dumps({
        "project_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip(),
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "deck_sha256": [sha256_file(args.deck_a), sha256_file(args.deck_b)],
        "seed": args.seed,
        "games": args.games,
        "rounds": rounds,
    }, indent=2))


if __name__ == "__main__":
    main()
