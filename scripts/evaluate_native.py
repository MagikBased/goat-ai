"""Evaluate two baseline agents on paired, seat-swapped native GOAT fixtures."""

import argparse
import hashlib
import json
import platform
from dataclasses import asdict
from functools import partial
from itertools import combinations
from pathlib import Path
from time import perf_counter

from goat_ai.agents import (
    CombatFlipHeuristicAgent,
    CombatHeuristicAgent,
    HeuristicAgent,
    RandomAgent,
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.evaluation import both_deck_assignments, run_tournament, run_tournament_parallel
from goat_ai.evaluation.competitive_corpus import (
    INDIANAPOLIS_2005_MAIN_DECKS,
    TOURNAMENT_MAIN_DECKS,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def published_2005_matchups(fixtures: Path) -> list[tuple[str, str]]:
    """Pair the playable published 2005 YDK fixtures in deterministic order."""
    decks = sorted(fixtures.glob("*2005.ydk"))
    if len(decks) < 2:
        raise ValueError("at least two published 2005 Deck files are required")
    return [(str(a), str(b)) for a, b in combinations(decks, 2)]


def file_set_sha256(root: Path, paths) -> str:
    """Fingerprint a file set, including relative names as well as contents."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        contents = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(contents).to_bytes(8, "big"))
        digest.update(contents)
    return digest.hexdigest()


def source_code_sha256(repository: Path) -> str:
    """Fingerprint the evaluator and installed project Python source."""
    sources = list((repository / "src/goat_ai").rglob("*.py"))
    sources.extend((repository / "scripts/evaluate_native.py",
                    repository / "pyproject.toml"))
    return file_set_sha256(repository, sources)


def card_scripts_sha256(native_root: Path) -> str:
    """Fingerprint pinned Lua scripts; card scripts affect native outcomes."""
    return file_set_sha256(native_root, (native_root / "scripts").rglob("*.lua"))


def tournament_matchups(fixtures: Path, *, indianapolis_2005: bool = False
                        ) -> tuple[tuple[str, str], ...]:
    """Each unordered pairing of the sourced tournament Main Deck corpus."""
    corpus = (INDIANAPOLIS_2005_MAIN_DECKS if indianapolis_2005
              else TOURNAMENT_MAIN_DECKS)
    decks = (str(fixtures / name) for name in corpus)
    return tuple(combinations(decks, 2))


def flip_monster_codes(native_root: Path) -> frozenset[int]:
    return load_flip_monster_codes(native_root)


def agent_factory(name: str, native_root: Path):
    if name == "random":
        return RandomAgent
    if name == "heuristic":
        return make_heuristic
    if name == "combat_heuristic":
        return make_combat_heuristic
    if name == "combat_flip":
        return partial(make_combat_flip,
                       flip_monster_codes=flip_monster_codes(native_root))
    if name in ("tactical_call_end_phase", "tactical_main2_set", "tactical_mof_readiness", "tactical_thunder_search", "tactical_card_advantage", "tactical_reaper_set", "tactical", "tactical_v13", "tactical_v12", "tactical_v11", "tactical_v10", "tactical_v9",
                "tactical_v8", "tactical_v7"):
        version = (15 if name in ("tactical_call_end_phase", "tactical_main2_set", "tactical_mof_readiness", "tactical_reaper_set", "tactical_card_advantage",
                                  "tactical_thunder_search")
                   else 14 if name == "tactical"
                   else int(name.removeprefix("tactical_v")))
        return partial(make_tactical,
                       flip_monster_codes=flip_monster_codes(native_root),
                       card_races=load_card_races(native_root),
                       card_facts=load_card_facts(native_root) if version >= 9 else {},
                       v8_guards=version >= 8,
                       v9_guards=version >= 9,
                       v10_guards=version >= 10,
                       v11_guards=version >= 11,
                       v12_guards=version >= 12,
                       v13_guards=version >= 13,
                       v14_guards=version >= 14,
                       reaper_set_guard=name == "tactical_reaper_set",
                       card_advantage_guard=name == "tactical_card_advantage",
                       thunder_search_guard=name == "tactical_thunder_search",
                       mof_readiness_guard=name == "tactical_mof_readiness",
                       main2_set_guard=name == "tactical_main2_set",
                       call_end_phase_guard=name == "tactical_call_end_phase")
    if name == "flip_heuristic":
        return partial(make_flip_heuristic,
                       flip_monster_codes=flip_monster_codes(native_root))
    raise ValueError(f"unknown agent: {name}")


def agent_version(name: str) -> int:
    """Record the underlying teacher version; variant flags stay in the name."""
    if name in ("tactical", "tactical_call_end_phase", "tactical_main2_set", "tactical_mof_readiness", "tactical_reaper_set", "tactical_card_advantage",
                "tactical_thunder_search"):
        return TacticalHeuristicAgent.teacher_version
    if name in ("tactical_v13", "tactical_v12", "tactical_v11", "tactical_v10",
                "tactical_v9", "tactical_v8", "tactical_v7"):
        return int(name.removeprefix("tactical_v"))
    if name == "combat_heuristic":
        return CombatHeuristicAgent.teacher_version
    if name == "combat_flip":
        return CombatFlipHeuristicAgent.teacher_version
    if name in ("heuristic", "flip_heuristic"):
        return HeuristicAgent.teacher_version
    if name == "random":
        return 1
    raise ValueError(f"unknown agent: {name}")


def make_heuristic(_seed: int) -> HeuristicAgent:
    return HeuristicAgent()


def make_combat_heuristic(_seed: int) -> CombatHeuristicAgent:
    return CombatHeuristicAgent()


def make_combat_flip(_seed: int, *, flip_monster_codes: frozenset[int]) -> CombatFlipHeuristicAgent:
    return CombatFlipHeuristicAgent(flip_monster_codes)


def make_flip_heuristic(_seed: int, *, flip_monster_codes: frozenset[int]) -> HeuristicAgent:
    return HeuristicAgent(flip_monster_codes)


def make_tactical(_seed: int, *, flip_monster_codes: frozenset[int],
                  card_races: dict[int, int],
                  card_facts: dict[int, tuple[int, int, int]] | None = None,
                  v8_guards: bool = True, v9_guards: bool = True,
                  v10_guards: bool = True,
                  v11_guards: bool = True,
                  v12_guards: bool = True, v13_guards: bool = True,
                  v14_guards: bool = True,
                  reaper_set_guard: bool = False,
                  card_advantage_guard: bool = False,
                  thunder_search_guard: bool = False,
                  mof_readiness_guard: bool = False,
                  main2_set_guard: bool = False,
                  call_end_phase_guard: bool = False) -> TacticalHeuristicAgent:
    return TacticalHeuristicAgent(flip_monster_codes, card_races,
                                  card_facts=card_facts,
                                  v8_guards=v8_guards, v9_guards=v9_guards,
                                  v10_guards=v10_guards, v11_guards=v11_guards,
                                  v12_guards=v12_guards, v13_guards=v13_guards,
                                  v14_guards=v14_guards,
                                  reaper_set_guard=reaper_set_guard,
                                  card_advantage_guard=card_advantage_guard,
                                  thunder_search_guard=thunder_search_guard,
                                  mof_readiness_guard=mof_readiness_guard,
                                  main2_set_guard=main2_set_guard,
                                  call_end_phase_guard=call_end_phase_guard)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"),
                        default="restricted")
    corpus = parser.add_mutually_exclusive_group()
    corpus.add_argument("--matchup", nargs=2, action="append",
                        metavar=("DECK_A", "DECK_B"))
    corpus.add_argument("--tournament-corpus", action="store_true",
                        help="pair every sourced tournament Main Deck once")
    corpus.add_argument("--indianapolis-2005", action="store_true",
                        help="pair the five executable Indianapolis 2005 Top 8 Main Decks")
    corpus.add_argument("--published-2005-corpus", action="store_true",
                        help="pair all playable published 2005 YDK examples once")
    parser.add_argument("--both-deck-assignments", action="store_true",
                        help="evaluate each deck pair with either agent assigned either deck")
    parser.add_argument("--agent-a", choices=("random", "heuristic", "combat_heuristic",
                                              "combat_flip", "flip_heuristic", "tactical",
                                              "tactical_call_end_phase", "tactical_main2_set", "tactical_reaper_set", "tactical_card_advantage",
                                              "tactical_thunder_search", "tactical_mof_readiness",
                                              "tactical_v13", "tactical_v12", "tactical_v11", "tactical_v10", "tactical_v9",
                                              "tactical_v8", "tactical_v7"),
                        default="random")
    parser.add_argument("--agent-b", choices=("random", "heuristic", "combat_heuristic",
                                              "combat_flip", "flip_heuristic", "tactical",
                                              "tactical_call_end_phase", "tactical_main2_set", "tactical_reaper_set", "tactical_card_advantage",
                                              "tactical_thunder_search", "tactical_mof_readiness",
                                              "tactical_v13", "tactical_v12", "tactical_v11", "tactical_v10", "tactical_v9",
                                              "tactical_v8", "tactical_v7"),
                        default="random")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=1,
                        help="spawn independent native duel processes")
    parser.add_argument("--verify-replays", action="store_true",
                        help="replay-verify and visibility-audit every terminal duel")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seeds < 1 or args.workers < 1 or args.max_decisions < 1:
        parser.error("--seeds, --workers, and --max-decisions must be positive")
    fixtures = Path(__file__).resolve().parent.parent / "examples/decks"
    if args.published_2005_corpus:
        matchups = published_2005_matchups(fixtures)
    elif args.tournament_corpus or args.indianapolis_2005:
        matchups = tournament_matchups(fixtures, indianapolis_2005=args.indianapolis_2005)
    else:
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
        verify_replays=args.verify_replays,
        **({"workers": args.workers} if args.workers > 1 else {}),
    )
    wall_seconds = perf_counter() - started
    assets = {
        name: sha256(args.native_root / relative)
        for name, relative in {
            "core_library": "build/libocgcore.so",
            "cards_database": "database/cards.cdb",
            "goat_database": "database/goat-entries.cdb",
            "unofficial_database": "database/cards-unofficial.cdb",
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
        "agent_a_version": agent_version(args.agent_a),
        "agent_b_version": agent_version(args.agent_b),
        "ruleset_scope": f"{args.engine} GOAT-mode native adapter",
        "core": "edo9300/ygopro-core baa3881d0bae48e9994f915f5c931be53c1ba8ef",
        "platform": platform.platform(), "cpu": platform.processor(),
        "workers": args.workers, "wall_seconds_tournament": wall_seconds,
        "duels_per_second": len(report.games) / wall_seconds,
        "decisions_per_second": sum(game.decisions for game in report.games) / wall_seconds,
        "asset_sha256": assets, "deck_sha256": deck_hashes,
        "main_deck_composition_sha256": {
            deck: main_deck_composition_sha256(read_ydk(deck))
            for deck in deck_hashes
        },
        "source_code_sha256": source_code_sha256(Path(__file__).resolve().parents[1]),
        "card_scripts_sha256": card_scripts_sha256(args.native_root),
        "replay_verification": ({
            "verified_games": sum(game.replay_verified_decisions is not None
                                  for game in report.games),
            "verified_decisions": sum(game.replay_verified_decisions or 0
                                      for game in report.games),
            "visibility_audited_games": sum(game.visibility_audited_decisions is not None
                                            for game in report.games),
            "visibility_audited_decisions": sum(
                game.visibility_audited_decisions or 0 for game in report.games),
        } if args.verify_replays else None),
        "seeds": seeds, "both_deck_assignments": args.both_deck_assignments,
        "tournament_corpus": args.tournament_corpus,
        "indianapolis_2005_corpus": args.indianapolis_2005,
        "published_2005_corpus": args.published_2005_corpus,
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
