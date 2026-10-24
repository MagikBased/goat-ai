"""Evaluate two baseline agents on paired, seat-swapped native GOAT fixtures."""

import argparse
import hashlib
import json
import platform
from dataclasses import asdict
from pathlib import Path

from goat_ai.agents import HeuristicAgent, RandomAgent
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.evaluation import run_tournament


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def agent_factory(name: str):
    if name == "random":
        return RandomAgent
    if name == "heuristic":
        return lambda _seed: HeuristicAgent()
    raise ValueError(f"unknown agent: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--matchup", nargs=2, action="append", metavar=("DECK_A", "DECK_B"))
    parser.add_argument("--agent-a", choices=("random", "heuristic"), default="random")
    parser.add_argument("--agent-b", choices=("random", "heuristic"), default="random")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be positive")
    fixtures = Path(__file__).resolve().parent.parent / "examples/decks"
    matchups = args.matchup or [[str(fixtures / "vanilla_probe.ydk"),
                                  str(fixtures / "vanilla_reverse.ydk")]]
    seeds = list(range(args.seed, args.seed + args.seeds))
    report = run_tournament(
        matchups, seeds, agent_factory(args.agent_a), agent_factory(args.agent_b),
        lambda: RestrictedOcgcoreEngine(args.native_root), args.max_decisions,
    )
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
        "ruleset_scope": "restricted GOAT-mode native adapter",
        "core": "edo9300/ygopro-core baa3881d0bae48e9994f915f5c931be53c1ba8ef",
        "platform": platform.platform(), "cpu": platform.processor(),
        "asset_sha256": assets, "deck_sha256": deck_hashes,
        "seeds": seeds, "summary": report.summary(),
        "games": [asdict(game) | {"a_outcome": game.a_outcome} for game in report.games],
    }
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
