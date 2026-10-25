"""Evaluate two baseline agents on paired, seat-swapped native GOAT fixtures."""

import argparse
import hashlib
import json
import platform
import sqlite3
from dataclasses import asdict
from functools import partial
from pathlib import Path
from time import perf_counter

from goat_ai.agents import CombatHeuristicAgent, HeuristicAgent, RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.evaluation import both_deck_assignments, run_tournament, run_tournament_parallel

FLIP_MONSTER_TYPE = 0x200000  # TYPE_FLIP in the pinned scripts/constant.lua


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def flip_monster_codes(native_root: Path) -> frozenset[int]:
    """Read public card type metadata from the pinned databases."""
    codes = set()
    for relative in ("database/cards.cdb", "database/goat-entries.cdb",
                     "database/cards-unofficial.cdb"):
        path = native_root / relative
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
            codes.update(row[0] for row in database.execute(
                "SELECT id FROM datas WHERE (type & ?) != 0", (FLIP_MONSTER_TYPE,)))
    return frozenset(codes)


def agent_factory(name: str, native_root: Path):
    if name == "random":
        return RandomAgent
    if name == "heuristic":
        return make_heuristic
    if name == "combat_heuristic":
        return make_combat_heuristic
    if name == "flip_heuristic":
        return partial(make_flip_heuristic,
                       flip_monster_codes=flip_monster_codes(native_root))
    raise ValueError(f"unknown agent: {name}")


def make_heuristic(_seed: int) -> HeuristicAgent:
    return HeuristicAgent()


def make_combat_heuristic(_seed: int) -> CombatHeuristicAgent:
    return CombatHeuristicAgent()


def make_flip_heuristic(_seed: int, *, flip_monster_codes: frozenset[int]) -> HeuristicAgent:
    return HeuristicAgent(flip_monster_codes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"),
                        default="restricted")
    parser.add_argument("--matchup", nargs=2, action="append", metavar=("DECK_A", "DECK_B"))
    parser.add_argument("--both-deck-assignments", action="store_true",
                        help="evaluate each deck pair with either agent assigned either deck")
    parser.add_argument("--agent-a", choices=("random", "heuristic", "combat_heuristic",
                                              "flip_heuristic"),
                        default="random")
    parser.add_argument("--agent-b", choices=("random", "heuristic", "combat_heuristic",
                                              "flip_heuristic"),
                        default="random")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=1,
                        help="spawn independent native duel processes")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seeds < 1 or args.workers < 1 or args.max_decisions < 1:
        parser.error("--seeds, --workers, and --max-decisions must be positive")
    fixtures = Path(__file__).resolve().parent.parent / "examples/decks"
    matchups = args.matchup or [[str(fixtures / "vanilla_probe.ydk"),
                                  str(fixtures / "vanilla_reverse.ydk")]]
    if args.both_deck_assignments:
        matchups = both_deck_assignments(matchups)
    seeds = list(range(args.seed, args.seed + args.seeds))
    runner = run_tournament_parallel if args.workers > 1 else run_tournament
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    started = perf_counter()
    report = runner(
        matchups, seeds, agent_factory(args.agent_a, args.native_root),
        agent_factory(args.agent_b, args.native_root),
        partial(engine_type, args.native_root), args.max_decisions,
        **({"workers": args.workers} if args.workers > 1 else {}),
    )
    wall_seconds = perf_counter() - started
    assets = {
        name: sha256(args.native_root / relative)
        for name, relative in {
            "core_library": "build/libocgcore.so",
            "cards_database": "database/cards.cdb",
            "goat_database": "database/goat-entries.cdb",
            "goat_whitelist": "banlist/GOAT.lflist.conf",
            "global_constants": "scripts/constant.lua",
            "global_utility": "scripts/utility.lua",
        }.items()
    }
    deck_hashes = {
        deck: sha256(Path(deck)) for matchup in matchups for deck in matchup
    }
    result = {
        "agent_a": args.agent_a, "agent_b": args.agent_b,
        "ruleset_scope": f"{args.engine} GOAT-mode native adapter",
        "core": "edo9300/ygopro-core baa3881d0bae48e9994f915f5c931be53c1ba8ef",
        "platform": platform.platform(), "cpu": platform.processor(),
        "workers": args.workers, "wall_seconds_tournament": wall_seconds,
        "duels_per_second": len(report.games) / wall_seconds,
        "decisions_per_second": sum(game.decisions for game in report.games) / wall_seconds,
        "asset_sha256": assets, "deck_sha256": deck_hashes,
        "seeds": seeds, "both_deck_assignments": args.both_deck_assignments,
        "summary": report.summary(),
        "games": [asdict(game) | {"a_outcome": game.a_outcome} for game in report.games],
    }
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
