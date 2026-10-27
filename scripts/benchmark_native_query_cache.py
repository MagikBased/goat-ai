"""Measure native duels with cached and uncached location decoding.

Both paths receive exactly the same native query bytes and random-agent
choices. Each matched pair must produce identical complete trajectories.
"""

import argparse
import hashlib
import json
import platform
import resource
import subprocess
from pathlib import Path
from time import perf_counter, process_time

from goat_ai.agents import RandomAgent
from goat_ai.engine import native_queries
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay.fingerprint import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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

    cached = native_queries.decode_location
    if not hasattr(cached, "__wrapped__"):
        parser.error("location decoder does not expose the uncached reference path")
    reference = cached.__wrapped__

    def run_schedule(decoder):
        native_queries.decode_location = decoder
        if decoder is cached:
            cached.cache_clear()
        wall_started = perf_counter()
        cpu_started = process_time()
        trajectories = []
        for seed in range(args.seed, args.seed + args.games):
            with GoatEnvironment(str(args.deck_a), str(args.deck_b), seed,
                                 engine=ExperimentalOcgcoreEngine(args.native_root)) as env:
                observation = env.reset()
                agents = (RandomAgent(seed), RandomAgent(seed + 1))
                for _ in range(args.max_decisions):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        break
                else:
                    raise RuntimeError(f"seed {seed} exceeded {args.max_decisions} decisions")
                trajectories.append(env.trajectory())
        return {
            "cpu_seconds": process_time() - cpu_started,
            "wall_seconds": perf_counter() - wall_started,
            "decisions": [len(trajectory.decisions) for trajectory in trajectories],
            "winners": [trajectory.winner for trajectory in trajectories],
            "cache_info": str(cached.cache_info()) if decoder is cached else None,
        }, trajectories

    rounds = []
    asset_manifest_sha256 = None
    try:
        for index in range(args.rounds):
            modes = ("uncached", "cached") if index % 2 == 0 else (
                "cached", "uncached")
            reports = {}
            trajectories = {}
            for mode in modes:
                reports[mode], trajectories[mode] = run_schedule(
                    reference if mode == "uncached" else cached)
            if trajectories["uncached"] != trajectories["cached"]:
                raise AssertionError("cached decoding changed a native trajectory")
            manifest = trajectories["cached"][0].asset_sha256
            digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
            if asset_manifest_sha256 is not None and digest != asset_manifest_sha256:
                raise AssertionError("native asset manifest changed across rounds")
            asset_manifest_sha256 = digest
            rounds.append({
                "order": modes,
                **reports,
                "cpu_speedup": (reports["uncached"]["cpu_seconds"]
                                / reports["cached"]["cpu_seconds"]),
                "matched_trajectories": True,
            })
    finally:
        native_queries.decode_location = cached

    print(json.dumps({
        "project_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip(),
        "platform": platform.platform(),
        "cpu": next((line.split(":", 1)[1].strip()
                     for line in Path("/proc/cpuinfo").read_text().splitlines()
                     if line.startswith("model name")), platform.processor()),
        "native_root": str(args.native_root),
        "core_sha256": sha256_file(args.native_root / "build/libocgcore.so"),
        "card_database_sha256": sha256_file(args.native_root / "database/cards.cdb"),
        "asset_manifest_sha256": asset_manifest_sha256,
        "decks": [str(args.deck_a), str(args.deck_b)],
        "deck_sha256": [sha256_file(args.deck_a), sha256_file(args.deck_b)],
        "seed": args.seed,
        "games": args.games,
        "rounds": rounds,
        "peak_process_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }, indent=2))


if __name__ == "__main__":
    main()
