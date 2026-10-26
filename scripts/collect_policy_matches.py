"""Record a reproducible, seat-swapped batch of native policy duels."""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory
from goat_ai.replay.fingerprint import sha256_file


@dataclass(frozen=True)
class MatchTask:
    matchup_index: int
    seed: int
    policy_seat: int
    deck1: Path
    deck2: Path
    output: Path


def schedule_matches(matchups: list[tuple[Path, Path]], first_seed: int,
                     seeds: int, output_dir: Path) -> tuple[MatchTask, ...]:
    """Keep matchup, seed, and seat ordering stable across worker counts."""
    if not matchups or seeds < 1 or first_seed < 0:
        raise ValueError("matchups, nonnegative first seed, and positive seeds required")
    return tuple(
        MatchTask(index, seed, seat, deck1, deck2,
                  output_dir / f"matchup_{index:02d}_seed_{seed}_seat_{seat}.json")
        for index, (deck1, deck2) in enumerate(matchups)
        for seed in range(first_seed, first_seed + seeds)
        for seat in (0, 1)
    )


def record_task(task: MatchTask, *, checkpoint: Path, native_root: Path,
                opponent: str, max_decisions: int,
                checkpoint_sha256: str) -> dict:
    """Use the single-duel recorder so both paths have identical provenance."""
    command = [sys.executable, str(Path(__file__).with_name("record_policy_match.py")),
               str(checkpoint), "--deck1", str(task.deck1), "--deck2", str(task.deck2),
               "--native-root", str(native_root), "--seed", str(task.seed),
               "--policy-seat", str(task.policy_seat), "--opponent", opponent,
               "--max-decisions", str(max_decisions), "--output", str(task.output)]
    environment = os.environ.copy()
    environment.setdefault("OMP_NUM_THREADS", "1")
    repo = Path(__file__).resolve().parent.parent
    local_path = os.pathsep.join((str(repo / "src"), str(repo)))
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, (
        local_path, environment.get("PYTHONPATH", ""))))
    process = subprocess.run(command, capture_output=True, text=True,
                             cwd=repo, env=environment, check=False)
    if process.returncode:
        raise RuntimeError(f"seed={task.seed}, matchup={task.matchup_index}, "
                           f"seat={task.policy_seat}: recorder failed: "
                           f"{process.stderr[-2000:]}")
    result = json.loads(process.stdout)
    if result.get("trajectory") != str(task.output) or result.get("source") != "policy_evaluation":
        raise ValueError(f"{task.output}: recorder returned unexpected provenance")
    trajectory_sha256 = sha256_file(task.output)
    trajectory = read_trajectory(task.output)
    audit_trajectory_visibility(trajectory)
    deck_sha256 = (sha256_file(task.deck1), sha256_file(task.deck2))
    if (trajectory.deck_sha256 != deck_sha256
            or trajectory.decks != (str(task.deck1), str(task.deck2))
            or trajectory.seed != task.seed
            or trajectory.source != "policy_evaluation"
            or trajectory.winner != result.get("winner")
            or len(trajectory.decisions) != result.get("verified_decisions")
            or (trajectory.skill_metadata or {}).get("demonstrator_seat") != task.policy_seat
            or (trajectory.skill_metadata or {}).get("policy_checkpoint_sha256")
            != checkpoint_sha256
            or sha256_file(task.output) != trajectory_sha256):
        raise ValueError(f"{task.output}: recorded trajectory provenance changed")
    return {
        "matchup_index": task.matchup_index,
        "seed": task.seed,
        "policy_seat": task.policy_seat,
        "deck1": str(task.deck1),
        "deck2": str(task.deck2),
        "deck_sha256": list(deck_sha256),
        "trajectory": str(task.output),
        "trajectory_sha256": trajectory_sha256,
        "winner": result["winner"],
        "verified_decisions": result["verified_decisions"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--matchup", nargs=2, type=Path, action="append",
                        required=True, metavar=("DECK1", "DECK2"))
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--opponent", choices=("combat_heuristic", "combat_flip",
                                               "tactical", "heuristic", "random"),
                        default="tactical")
    parser.add_argument("--seed", type=int, default=12000)
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--max-decisions", type=int, default=3000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.workers < 1 or args.max_decisions < 1:
        parser.error("workers and max decisions must be positive")
    if not args.checkpoint.is_file() or any(not deck.is_file()
                                            for pair in args.matchup for deck in pair):
        parser.error("checkpoint and matchup deck files must exist")
    if args.output_dir.exists() and (
            not args.output_dir.is_dir() or any(args.output_dir.iterdir())):
        parser.error("output directory must be empty to protect recorded trajectories")
    try:
        tasks = schedule_matches(args.matchup, args.seed, args.seeds,
                                 args.output_dir.resolve())
    except ValueError as exc:
        parser.error(str(exc))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = args.checkpoint.resolve()
    checkpoint_sha256 = sha256_file(checkpoint)
    native_root = args.native_root.resolve()
    tasks = tuple(MatchTask(task.matchup_index, task.seed, task.policy_seat,
                            task.deck1.resolve(), task.deck2.resolve(), task.output)
                  for task in tasks)
    def record(task: MatchTask) -> dict:
        return record_task(task, checkpoint=checkpoint, native_root=native_root,
                           opponent=args.opponent, max_decisions=args.max_decisions,
                           checkpoint_sha256=checkpoint_sha256)

    with ThreadPoolExecutor(max_workers=args.workers) as workers:
        games = list(workers.map(record, tasks))
    if sha256_file(checkpoint) != checkpoint_sha256:
        raise ValueError("checkpoint changed during collection")
    report = {
        "schema_version": 1,
        "checkpoint_sha256": checkpoint_sha256,
        "opponent": args.opponent,
        "max_decisions": args.max_decisions,
        "seeds": [args.seed, args.seed + args.seeds - 1],
        "workers": args.workers,
        "games": games,
        "verified_games": len(games),
        "verified_decisions": sum(game["verified_decisions"] for game in games),
    }
    manifest = args.output_dir / "manifest.json"
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(json.dumps({"manifest": str(manifest), "verified_games": len(games),
                      "verified_decisions": report["verified_decisions"]}, indent=2))


if __name__ == "__main__":
    main()
