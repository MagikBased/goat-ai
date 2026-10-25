"""Measure spawned native workers on sourced competitive GOAT decks.

Each worker reports its own Linux VmHWM. Their sum is a sum of per-process
high-water marks, not an instantaneous machine-wide memory peak.
"""

import argparse
import json
import os
import platform
import subprocess
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from time import perf_counter

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay.fingerprint import sha256_file


def peak_rss_kb() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1])
    raise RuntimeError("Linux /proc/self/status lacks VmHWM")


def cpu_model() -> str:
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor()


def schedule(seed: int, games: int) -> tuple[tuple[int, int], ...]:
    if games < 2 or games % 2:
        raise ValueError("games must be a positive even number")
    return tuple((seed + index // 2, index % 2) for index in range(games))


def play(task: tuple[str, str, str, int, int, int]) -> dict:
    native_root, deck_a, deck_b, seed, a_seat, max_decisions = task
    before_peak = peak_rss_kb()
    started = perf_counter()
    decks = (deck_a, deck_b) if a_seat == 0 else (deck_b, deck_a)
    with GoatEnvironment(*decks, seed=seed,
                         engine=ExperimentalOcgcoreEngine(Path(native_root))) as env:
        before_reset = perf_counter()
        observation = env.reset()
        reset_seconds = perf_counter() - before_reset
        agents = (RandomAgent(seed), RandomAgent(seed + 1))
        for decisions in range(1, max_decisions + 1):
            action = agents[observation.acting_player].select_action(
                observation, env.legal_actions())
            observation = env.step(action)
            if env.is_terminal():
                winner = env.result()
                break
        else:
            raise RuntimeError(f"seed {seed}, seat {a_seat} exceeded "
                               f"{max_decisions} decisions")
    return {
        "seed": seed, "a_seat": a_seat, "winner": winner,
        "decisions": decisions, "reset_seconds": reset_seconds,
        "game_seconds": perf_counter() - started, "pid": os.getpid(),
        "worker_initial_peak_rss_kb": before_peak,
        "worker_peak_rss_kb": peak_rss_kb(),
    }


def worker_memory(games: tuple[dict, ...]) -> dict:
    by_pid: dict[int, dict] = {}
    for game in games:
        pid = game["pid"]
        entry = by_pid.setdefault(pid, {
            "pid": pid, "games": 0,
            "initial_peak_rss_kb": game["worker_initial_peak_rss_kb"],
            "peak_rss_kb": 0,
        })
        entry["games"] += 1
        entry["initial_peak_rss_kb"] = min(
            entry["initial_peak_rss_kb"], game["worker_initial_peak_rss_kb"])
        entry["peak_rss_kb"] = max(entry["peak_rss_kb"],
                                   game["worker_peak_rss_kb"])
    workers = [by_pid[pid] for pid in sorted(by_pid)]
    return {
        "workers_observed": len(workers), "worker_processes": workers,
        "sum_worker_peak_rss_kb": sum(item["peak_rss_kb"] for item in workers),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--deck-a", type=Path,
                        default=Path("examples/decks/goat_control_lolmarcus_2020.ydk"))
    parser.add_argument("--deck-b", type=Path,
                        default=Path("examples/decks/chaos_turbo_riclar_2020.ydk"))
    parser.add_argument("--seed", type=int, default=9700)
    parser.add_argument("--games", type=int, default=8)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-decisions", type=int, default=3000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.workers < 1 or args.max_decisions < 1:
        parser.error("--workers and --max-decisions must be positive")
    try:
        jobs = schedule(args.seed, args.games)
    except ValueError as exc:
        parser.error(str(exc))
    root, deck_a, deck_b = (path.resolve() for path in (
        args.native_root, args.deck_a, args.deck_b))
    tasks = ((str(root), str(deck_a), str(deck_b), seed, seat,
              args.max_decisions) for seed, seat in jobs)
    initial_parent_peak = peak_rss_kb()
    started = perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers,
                             mp_context=get_context("spawn")) as executor:
        games = tuple(executor.map(play, tasks))
    wall_seconds = perf_counter() - started
    decisions = sum(game["decisions"] for game in games)
    memory = worker_memory(games)
    report = {
        "project_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True,
            cwd=Path(__file__).resolve().parent.parent).strip(),
        "ruleset_scope": "experimental GOAT-mode native adapter",
        "platform": platform.platform(), "cpu": cpu_model(),
        "workers_requested": args.workers, "games": args.games,
        "seed_start": args.seed, "max_decisions": args.max_decisions,
        "deck_sha256": {str(path): sha256_file(path)
                        for path in (deck_a, deck_b)},
        "asset_sha256": {
            relative: sha256_file(root / relative) for relative in (
                "build/libocgcore.so", "database/cards.cdb",
                "database/goat-entries.cdb", "database/cards-unofficial.cdb",
                "banlist/GOAT.lflist.conf", "scripts/constant.lua",
                "scripts/utility.lua")},
        "wall_seconds_including_spawn": wall_seconds,
        "duels_per_second": len(games) / wall_seconds,
        "decisions": decisions, "decisions_per_second": decisions / wall_seconds,
        "reset_seconds_total": sum(game["reset_seconds"] for game in games),
        "reset_seconds_per_duel": sum(game["reset_seconds"] for game in games) /
        len(games),
        "parent_initial_peak_rss_kb": initial_parent_peak,
        "parent_peak_rss_kb": peak_rss_kb(),
        **memory, "game_results": games,
    }
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
