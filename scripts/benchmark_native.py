"""Measure complete duels through the real native adapter."""

import argparse
import json
import platform
import subprocess
from pathlib import Path
from time import perf_counter

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay.fingerprint import sha256_file


def process_peak_rss_kb() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1])
    raise RuntimeError("Linux /proc/self/status lacks VmHWM")


def cpu_model() -> str:
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--games", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--engine", choices=("restricted", "experimental"),
                        default="restricted")
    parser.add_argument("--deck-a", type=Path)
    parser.add_argument("--deck-b", type=Path)
    parser.add_argument("--max-decisions", type=int, default=5000)
    args = parser.parse_args()
    if args.games < 1 or args.max_decisions < 1:
        parser.error("--games and --max-decisions must be positive")
    if (args.deck_a is None) != (args.deck_b is None):
        parser.error("--deck-a and --deck-b must be supplied together")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    deck1 = args.deck_a or decks / "vanilla_probe.ydk"
    deck2 = args.deck_b or decks / "vanilla_reverse.ydk"
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    started = perf_counter()
    initial_peak_rss_kb = process_peak_rss_kb()
    reset_seconds = 0.0
    decisions = 0
    results = []
    for game in range(args.games):
        seed = args.seed + game
        with GoatEnvironment(str(deck1), str(deck2), seed,
                             engine=engine_type(args.native_root)) as env:
            before_reset = perf_counter()
            observation = env.reset()
            reset_seconds += perf_counter() - before_reset
            agents = (RandomAgent(seed), RandomAgent(seed + 1))
            for _ in range(args.max_decisions):
                action = agents[observation.acting_player].select_action(
                    observation, env.legal_actions())
                observation = env.step(action)
                decisions += 1
                if env.is_terminal():
                    results.append(env.result())
                    break
            else:
                raise RuntimeError(f"game seed {seed} exceeded {args.max_decisions} decisions")
    elapsed = perf_counter() - started
    print(json.dumps({
        "project_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True,
            cwd=Path(__file__).resolve().parent.parent).strip(),
        "games": args.games, "seed_start": args.seed,
        "ruleset_scope": f"{args.engine} GOAT-mode native adapter",
        "core": "edo9300/ygopro-core baa3881d0bae48e9994f915f5c931be53c1ba8ef",
        "platform": platform.platform(), "cpu": cpu_model(),
        "decks": [str(deck1), str(deck2)],
        "deck_sha256": [sha256_file(deck1), sha256_file(deck2)],
        "max_decisions": args.max_decisions,
        "elapsed_seconds": elapsed, "reset_seconds_total": reset_seconds,
        "reset_seconds_per_duel": reset_seconds / args.games,
        "duels_per_second": args.games / elapsed,
        "decisions": decisions, "decisions_per_second": decisions / elapsed,
        "average_decisions_per_duel": decisions / args.games,
        "initial_peak_rss_kb": initial_peak_rss_kb,
        "peak_process_rss_kb": process_peak_rss_kb(),
        "winners": results,
    }, indent=2))


if __name__ == "__main__":
    main()
