"""Compare native field-summary observations with the full-query reference.

Both schedules receive the same deck, seed, and RandomAgent choices. The
complete trajectories must match; timing excludes replay verification.
"""

import argparse
import json
import platform
import resource
import subprocess
from pathlib import Path
from time import perf_counter, process_time

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import OcgcoreProbe
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory
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

    original_query = OcgcoreProbe._query_location
    original_mode = OcgcoreProbe.use_field_summary_queries
    query_calls = 0

    def counted_query(self, player, location):
        nonlocal query_calls
        query_calls += 1
        return original_query(self, player, location)

    OcgcoreProbe._query_location = counted_query

    def run_schedule(optimized):
        nonlocal query_calls
        OcgcoreProbe.use_field_summary_queries = optimized
        query_calls = 0
        wall_started = perf_counter()
        cpu_started = process_time()
        trajectories = []
        for seed in range(args.seed, args.seed + args.games):
            with GoatEnvironment(str(args.deck_a), str(args.deck_b), seed,
                                 ExperimentalOcgcoreEngine(args.native_root)) as env:
                observation = env.reset()
                agents = (RandomAgent(seed), RandomAgent(seed + 1))
                for _ in range(args.max_decisions):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        break
                else:
                    raise RuntimeError(f"seed {seed} exceeded decision cap")
                trajectories.append(env.trajectory())
        return {
            "wall_seconds": perf_counter() - wall_started,
            "cpu_seconds": process_time() - cpu_started,
            "location_queries": query_calls,
            "decisions": [len(item.decisions) for item in trajectories],
            "winners": [item.winner for item in trajectories],
        }, trajectories

    rounds = []
    verified_decisions = 0
    try:
        for index in range(args.rounds):
            order = (False, True) if index % 2 == 0 else (True, False)
            reports = {}
            trajectories = {}
            for mode in order:
                name = "optimized" if mode else "reference"
                reports[name], trajectories[name] = run_schedule(mode)
            if trajectories["reference"] != trajectories["optimized"]:
                raise AssertionError("field-summary queries changed a complete trajectory")
            for trajectory in trajectories["optimized"]:
                verified = verify_trajectory(
                    trajectory, ExperimentalOcgcoreEngine(args.native_root))
                audit_trajectory_visibility(trajectory)
                verified_decisions += verified
            rounds.append({
                "order": ["optimized" if mode else "reference" for mode in order],
                **reports,
                "cpu_speedup": (reports["reference"]["cpu_seconds"]
                                / reports["optimized"]["cpu_seconds"]),
                "matched_trajectories": True,
            })
    finally:
        OcgcoreProbe._query_location = original_query
        OcgcoreProbe.use_field_summary_queries = original_mode

    print(json.dumps({
        "project_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip(),
        "worktree_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain"], text=True).strip()),
        "source_sha256": {
            name: sha256_file(Path(name)) for name in (
                "src/goat_ai/engine/native_queries.py",
                "src/goat_ai/engine/ocgcore_probe.py",
                "scripts/benchmark_native_field_summary.py",
            )
        },
        "platform": platform.platform(),
        "cpu": next((line.split(":", 1)[1].strip()
                     for line in Path("/proc/cpuinfo").read_text().splitlines()
                     if line.startswith("model name")), platform.processor()),
        "core_sha256": sha256_file(args.native_root / "build/libocgcore.so"),
        "deck_sha256": [sha256_file(args.deck_a), sha256_file(args.deck_b)],
        "seed": args.seed,
        "games": args.games,
        "rounds": rounds,
        "replay_verified_decisions": verified_decisions,
        "peak_process_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }, indent=2))


if __name__ == "__main__":
    main()
