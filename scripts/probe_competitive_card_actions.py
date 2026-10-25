"""Measure card-source actions in complete native duels from sourced GOAT decks.

Counts describe this seeded agent sample, not historical ruling correctness or
metagame play rates. Target-selection card codes are deliberately excluded.
"""

import argparse
import json
import sqlite3
from collections import Counter
from itertools import combinations
from pathlib import Path

from goat_ai.agents import CombatHeuristicAgent, HeuristicAgent, RandomAgent
from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.competitive_corpus import TOURNAMENT_MAIN_DECKS
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATCHUPS = (
    ("goat_control_lolmarcus_2020.ydk", "chaos_turbo_riclar_2020.ydk"),
    ("warrior_montague_clash.ydk", "chaos_control_insids_worlds_2022.ydk"),
    ("chaos_return_dingosig_worlds_2022.ydk",
     "flip_control_goatformat_guide.ydk"),
)


def tournament_matchups(fixtures: Path) -> tuple[tuple[Path, Path], ...]:
    """Pair each of the six sourced tournament Main Decks once."""
    return tuple(combinations((fixtures / name for name in TOURNAMENT_MAIN_DECKS), 2))


def make_agent(name: str, seed: int):
    """Construct a baseline using only the public observation/action interface."""
    if name == "random":
        return RandomAgent(seed)
    if name == "heuristic":
        return HeuristicAgent()
    if name == "combat_heuristic":
        return CombatHeuristicAgent()
    raise ValueError(f"unknown baseline agent: {name}")
SOURCE_KINDS = frozenset({
    "activate", "chain", "normal_summon", "flip_summon", "special_summon",
    "set_monster", "set_spell_trap", "attack", "change_position",
})


def deck_label(path: Path) -> str:
    """Use checkout-independent paths for the repository's example decks."""
    absolute = path.resolve()
    try:
        return str(absolute.relative_to(ROOT))
    except ValueError:
        return str(absolute)


def count_source_actions(legal_actions, selected_action,
                         offered: Counter, selected: Counter) -> None:
    """Count a card once per decision where its source action is offered."""
    choices = {(action.parameters["code"], action.kind)
               for action in legal_actions
               if action.kind in SOURCE_KINDS
               and isinstance(action.parameters.get("code"), int)}
    offered.update(choices)
    choice = (selected_action.parameters.get("code"), selected_action.kind)
    if choice in choices:
        selected[choice] += 1


def count_chain_response(observation, selected_action,
                         responses: Counter) -> None:
    """Count a chosen card response to the currently latest public chain link."""
    if selected_action.kind != "chain" or not observation.chain:
        return
    code = selected_action.parameters.get("code")
    if isinstance(code, int):
        responses[code, observation.chain[-1].card_code] += 1


def card_names(native_root: Path, codes: set[int]) -> dict[int, str]:
    database = native_root / "database/cards.cdb"
    names = {}
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as db:
        for schema, filename in (("goat", "goat-entries.cdb"),
                                 ("unofficial", "cards-unofficial.cdb")):
            db.execute(f"ATTACH DATABASE ? AS {schema}",
                       (f"file:{(native_root / 'database' / filename).resolve()}?mode=ro",))
        for code in codes:
            for schema in ("goat", "main", "unofficial"):
                row = db.execute(
                    f"SELECT name FROM {schema}.texts WHERE id=?", (code,)).fetchone()
                if row is not None:
                    names[code] = row[0]
                    break
    return names


def probe(native_root: Path, matchups: tuple[tuple[Path, Path], ...],
          first_seed: int, seeds: int, max_decisions: int,
          agent_name: str = "random", *, verify_replays: bool = False,
          record_dir: Path | None = None) -> dict:
    if seeds < 1 or max_decisions < 1 or not matchups:
        raise ValueError("positive seeds/max_decisions and nonempty matchups required")
    offered: Counter[tuple[int, str]] = Counter()
    selected: Counter[tuple[int, str]] = Counter()
    responses: Counter[tuple[int, int]] = Counter()
    deck_paths = sorted({path.resolve() for matchup in matchups for path in matchup})
    prevalence: Counter[int] = Counter()
    copies: Counter[int] = Counter()
    for path in deck_paths:
        main = Counter(read_ydk(path).main)
        prevalence.update(main.keys())
        copies.update(main)
    games = []
    verified_decisions = 0
    if record_dir is not None:
        record_dir.mkdir(parents=True, exist_ok=True)
    loaded_assets: dict[str, str] = {}
    rules_profile = None
    for left, right in matchups:
        for seed in range(first_seed, first_seed + seeds):
            for swapped in (False, True):
                decks = (right, left) if swapped else (left, right)
                with GoatEnvironment(*(str(path) for path in decks), seed=seed,
                                     engine=ExperimentalOcgcoreEngine(native_root)) as env:
                    observation = env.reset()
                    agents = (make_agent(agent_name, seed * 2),
                              make_agent(agent_name, seed * 2 + 1))
                    for decision_index in range(max_decisions):
                        if env.is_terminal():
                            break
                        action = agents[observation.acting_player].select_action(
                            observation, env.legal_actions())
                        try:
                            observation = env.step(action)
                        except Exception as error:
                            raise RuntimeError(
                                f"probe failed: decks={tuple(map(deck_label, decks))}, "
                                f"seed={seed}, swapped={swapped}, "
                                f"decision={decision_index}"
                            ) from error
                    else:
                        if not env.is_terminal():
                            raise RuntimeError(f"duel exceeded {max_decisions} decisions: "
                                               f"{decks}, seed={seed}")
                    trajectory = env.trajectory()
                    game = {"decks": [deck_label(path) for path in decks],
                            "seed": seed, "decisions": len(trajectory.decisions),
                            "winner": env.result()}
                    if record_dir is not None:
                        trajectory_path = record_dir / (
                            f"game_{len(games):05d}_seed_{seed}.json")
                        write_trajectory(trajectory_path, trajectory)
                        game["trajectory_file"] = trajectory_path.name
                        game["trajectory_sha256"] = sha256_file(trajectory_path)
                    if verify_replays:
                        replay = (read_trajectory(trajectory_path)
                                  if record_dir is not None else trajectory)
                        try:
                            count = verify_trajectory(
                                replay, ExperimentalOcgcoreEngine(native_root))
                        except Exception as error:
                            raise RuntimeError(
                                f"replay verification failed: "
                                f"decks={tuple(map(deck_label, decks))}, seed={seed}, "
                                f"game={len(games)}") from error
                        if count != len(trajectory.decisions):
                            raise RuntimeError("replay verifier returned a partial decision count")
                        game["replay_verified_decisions"] = count
                        verified_decisions += count
                    if rules_profile is None:
                        rules_profile = trajectory.rules_profile
                    elif trajectory.rules_profile != rules_profile:
                        raise RuntimeError("rules profile changed within probe")
                    for path, digest in (trajectory.asset_sha256 or {}).items():
                        if path in loaded_assets and loaded_assets[path] != digest:
                            raise RuntimeError(f"native asset changed within probe: {path}")
                        loaded_assets[path] = digest
                    for record in trajectory.decisions:
                        count_source_actions(record.legal_actions,
                                             record.selected_action, offered, selected)
                        count_chain_response(record.observation,
                                             record.selected_action, responses)
                    games.append(game)
    names = card_names(native_root, set(prevalence) | {code for code, _ in offered}
                       | {code for pair in responses for code in pair})
    cards = []
    for code in sorted(set(prevalence) | {code for code, _ in offered},
                       key=lambda value: (-prevalence[value],
                                          -sum(count for (card, _), count in offered.items()
                                               if card == value), value)):
        offered_by_kind = {kind: offered[code, kind] for kind in sorted(SOURCE_KINDS)
                           if offered[code, kind]}
        selected_by_kind = {kind: selected[code, kind] for kind in sorted(SOURCE_KINDS)
                            if selected[code, kind]}
        cards.append({"code": code, "name": names.get(code),
                      "deck_lists": prevalence[code], "deck_copies": copies[code],
                      "offered_decisions": sum(offered_by_kind.values()),
                      "selected_decisions": sum(selected_by_kind.values()),
                      "offered_by_kind": offered_by_kind,
                      "selected_by_kind": selected_by_kind})
    asset_paths = {
        "core_library": "build/libocgcore.so",
        "cards_database": "database/cards.cdb",
        "goat_database": "database/goat-entries.cdb",
        "goat_whitelist": "banlist/GOAT.lflist.conf",
        "global_constants": "scripts/constant.lua",
        "global_utility": "scripts/utility.lua",
    }
    result = {
        "scope": f"seeded {agent_name.replace('_', '-')}-agent source-action sample; "
                 "not GOAT correctness or play rate",
        "seeds": list(range(first_seed, first_seed + seeds)),
        "max_decisions": max_decisions,
        "asset_sha256": {name: sha256_file(native_root / relative)
                         for name, relative in asset_paths.items()},
        "loaded_asset_sha256": dict(sorted(loaded_assets.items())),
        "rules_profile": rules_profile,
        "deck_sha256": {deck_label(path): sha256_file(path) for path in deck_paths},
        "games": games,
        "cards": cards,
        "chain_responses": [
            {"responder_code": responder,
             "responder_name": names.get(responder),
             "preceding_link_code": preceding,
             "preceding_link_name": names.get(preceding),
             "selected_decisions": count}
            for (responder, preceding), count in sorted(
                responses.items(), key=lambda item: (-item[1], item[0]))
        ],
    }
    if agent_name != "random":
        result["agent"] = agent_name
    if verify_replays:
        result["replay_verification"] = {
            "verified_games": len(games), "verified_decisions": verified_decisions,
            "serialized_round_trip": record_dir is not None,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    schedule = parser.add_mutually_exclusive_group()
    schedule.add_argument("--matchup", nargs=2, action="append", type=Path,
                          metavar=("DECK_A", "DECK_B"))
    schedule.add_argument("--tournament-corpus", action="store_true",
                          help="probe all 15 pairs of six sourced tournament decks")
    parser.add_argument("--seed", type=int, default=9700)
    parser.add_argument("--agent", choices=("random", "heuristic", "combat_heuristic"),
                        default="random")
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--max-decisions", type=int, default=3000)
    parser.add_argument("--verify-replays", action="store_true",
                        help="replay every complete duel against fresh pinned native engines")
    parser.add_argument("--record-dir", type=Path,
                        help="optional ignored directory for exact duel trajectories")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    fixtures = ROOT / "examples/decks"
    if args.tournament_corpus:
        matchups = tournament_matchups(fixtures)
    elif args.matchup is None:
        matchups = tuple((fixtures / a, fixtures / b) for a, b in DEFAULT_MATCHUPS)
    else:
        matchups = tuple(tuple(pair) for pair in args.matchup)
    report = probe(args.native_root, matchups, args.seed, args.seeds,
                   args.max_decisions, args.agent,
                   verify_replays=args.verify_replays, record_dir=args.record_dir)
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
