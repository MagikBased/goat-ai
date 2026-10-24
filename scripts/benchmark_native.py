"""Measure complete vanilla-fixture duels through the real native adapter."""

import argparse
import json
import platform
from pathlib import Path
from time import perf_counter

from goat_ai.agents import RandomAgent
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments import GoatEnvironment


def process_peak_rss_kb() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1])
    raise RuntimeError("Linux /proc/self/status lacks VmHWM")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--games", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.games < 1:
        parser.error("--games must be positive")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    deck1, deck2 = str(decks / "vanilla_probe.ydk"), str(decks / "vanilla_reverse.ydk")
    started = perf_counter()
    initial_peak_rss_kb = process_peak_rss_kb()
    reset_seconds = 0.0
    decisions = 0
    results = []
    for game in range(args.games):
        seed = args.seed + game
        with GoatEnvironment(deck1, deck2, seed,
                             engine=RestrictedOcgcoreEngine(args.native_root)) as env:
            before_reset = perf_counter()
            observation = env.reset()
            reset_seconds += perf_counter() - before_reset
            agents = (RandomAgent(seed), RandomAgent(seed + 1))
            for _ in range(5000):
                action = agents[observation.acting_player].select_action(
                    observation, env.legal_actions())
                observation = env.step(action)
                decisions += 1
                if env.is_terminal():
                    results.append(env.result())
                    break
            else:
                raise RuntimeError(f"game seed {seed} exceeded 5000 decisions")
    elapsed = perf_counter() - started
    print(json.dumps({
        "games": args.games, "seed_start": args.seed,
        "ruleset_scope": "GOAT-mode normal-monster fixture only",
        "core": "edo9300/ygopro-core baa3881d0bae48e9994f915f5c931be53c1ba8ef",
        "platform": platform.platform(), "cpu": platform.processor(),
        "elapsed_seconds": elapsed, "reset_seconds_total": reset_seconds,
        "duels_per_second": args.games / elapsed,
        "decisions": decisions, "decisions_per_second": decisions / elapsed,
        "average_decisions_per_duel": decisions / args.games,
        "initial_peak_rss_kb": initial_peak_rss_kb,
        "peak_process_rss_kb": process_peak_rss_kb(),
        "winners": results,
    }, indent=2))


if __name__ == "__main__":
    main()
