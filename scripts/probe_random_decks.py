"""Generate reproducible whitelist-legal decks and probe native decision coverage.

This is protocol triage, not evidence that a sampled duel is GOAT-correct.
Decks and reports are written under the ignored .cache directory by default.
"""

import argparse
import json
import random
import sqlite3
from collections import Counter
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import (
    Decklist,
    read_goat_whitelist,
    read_ydk,
    validate_goat_deck,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.card_actions import count_chain_response, count_source_actions
from goat_ai.evaluation.competitive_corpus import TOURNAMENT_MAIN_DECKS
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory
from goat_ai.replay.fingerprint import sha256_file


def generate_deck(root: Path, seed: int) -> Decklist:
    """Choose 40 distinct canonical Main Deck cards from the pinned GOAT list."""
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    database = root / "database/cards.cdb"
    goat = root / "database/goat-entries.cdb"
    unofficial = root / "database/cards-unofficial.cdb"
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as connection:
        connection.execute("ATTACH DATABASE ? AS goat", (f"file:{goat.resolve()}?mode=ro",))
        connection.execute("ATTACH DATABASE ? AS unofficial",
                           (f"file:{unofficial.resolve()}?mode=ro",))
        candidates = []
        for code, limit in sorted(limits.items()):
            if not limit:
                continue
            row = None
            for schema in ("goat", "main", "unofficial"):
                row = connection.execute(f"SELECT alias, type FROM {schema}.datas WHERE id=?",
                                         (code,)).fetchone()
                if row is not None:
                    break
            if row is not None and not row[1] & 0x40 and not row[1] & 0x4000:
                candidates.append((code, row[0] or code))
    random.Random(seed).shuffle(candidates)
    chosen = []
    canonical = set()
    for code, name_code in candidates:
        if name_code in canonical:
            continue
        chosen.append(code)
        canonical.add(name_code)
        if len(chosen) == 40:
            break
    if len(chosen) != 40:
        raise ValueError("GOAT card pool contains fewer than 40 distinct Main Deck cards")
    deck = Decklist(tuple(chosen))
    validate_goat_deck(deck, limits, database, goat, unofficial)
    return deck


def generate_tournament_mix(root: Path, seed: int) -> Decklist:
    """Sample legal 40-card lists from copies in six sourced tournament decks."""
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    sources = tuple(read_ydk(fixtures / name) for name in TOURNAMENT_MAIN_DECKS)
    candidates = [code for deck in sources for code in deck.main]
    random.Random(seed).shuffle(candidates)
    chosen = []
    counts: Counter[int] = Counter()
    for code in candidates:
        if counts[code] >= limits.get(code, 0):
            continue
        chosen.append(code)
        counts[code] += 1
        if len(chosen) == 40:
            break
    if len(chosen) != 40:
        raise ValueError("tournament corpus cannot supply a legal 40-card Main Deck")
    deck = Decklist(tuple(chosen), sources[seed % len(sources)].extra)
    validate_goat_deck(deck, limits, root / "database/cards.cdb",
                       root / "database/goat-entries.cdb",
                       root / "database/cards-unofficial.cdb")
    return deck


def write_deck(path: Path, deck: Decklist) -> None:
    path.write_text("#main\n" + "\n".join(map(str, deck.main))
                    + "\n#extra\n"
                    + "".join(f"{code}\n" for code in deck.extra)
                    + "!side\n")


def probe(root: Path, output: Path, first_seed: int, seeds: int,
          max_decisions: int, card_pool: str = "whitelist",
          verify_replays: bool = False,
          distinct_opponents: bool = False,
          count_card_actions: bool = False,
          repeat_seeds: bool = False) -> dict:
    if card_pool not in ("whitelist", "tournament"):
        raise ValueError("unknown card pool")
    output.mkdir(parents=True, exist_ok=True)
    games = []
    offered: Counter[tuple[int, str]] = Counter()
    selected: Counter[tuple[int, str]] = Counter()
    responses: Counter[tuple[int, int]] = Counter()
    visibility_counts: Counter[str] = Counter()
    visibility_games = 0
    repeated_games = 0
    repeated_decisions = 0
    loaded_assets: dict[str, str] = {}
    rules_profile = None
    for seed in range(first_seed, first_seed + seeds):
        generator = generate_deck if card_pool == "whitelist" else generate_tournament_mix
        deck = generator(root, seed)
        path = output / f"seed_{seed}.ydk"
        write_deck(path, deck)
        opponent_path = path
        if distinct_opponents:
            opponent_path = output / f"seed_{seed}_opponent.ydk"
            write_deck(opponent_path, generator(root, seed + 1_000_000))
        decisions = 0
        kinds = set()
        try:
            with GoatEnvironment(str(path), str(opponent_path), seed,
                                 ExperimentalOcgcoreEngine(root)) as env:
                observation = env.reset()
                agent = RandomAgent(seed)
                while not env.is_terminal() and decisions < max_decisions:
                    actions = env.legal_actions()
                    kinds.update(action.kind for action in actions)
                    observation = env.step(agent.select_action(observation, actions))
                    decisions += 1
                terminal = env.is_terminal()
                winner = env.result() if terminal else None
                trajectory = env.trajectory() if terminal else None
                verified = (verify_trajectory(trajectory,
                                              ExperimentalOcgcoreEngine(root))
                            if trajectory is not None and verify_replays else None)
                if verified is not None and verified != decisions:
                    raise RuntimeError("replay verifier returned a partial decision count")
                if verified is not None:
                    visibility_counts.update(audit_trajectory_visibility(trajectory))
                    visibility_games += 1
                if trajectory is not None and (card_pool == "tournament"
                                               or verify_replays):
                    if rules_profile is None:
                        rules_profile = trajectory.rules_profile
                    elif rules_profile != trajectory.rules_profile:
                        raise RuntimeError("rules profile changed within probe")
                    for asset, digest in (trajectory.asset_sha256 or {}).items():
                        if asset in loaded_assets and loaded_assets[asset] != digest:
                            raise RuntimeError(f"native asset changed within probe: {asset}")
                        loaded_assets[asset] = digest
                if trajectory is not None and count_card_actions:
                    for record in trajectory.decisions:
                        count_source_actions(record.legal_actions,
                                             record.selected_action, offered, selected)
                        count_chain_response(record.observation,
                                             record.selected_action, responses)
            if repeat_seeds:
                if trajectory is None:
                    raise RuntimeError("cannot repeat a duel that did not reach terminal")
                with GoatEnvironment(str(path), str(opponent_path), seed,
                                     ExperimentalOcgcoreEngine(root)) as repeated:
                    repeated_observation = repeated.reset()
                    repeated_agent = RandomAgent(seed)
                    for _ in range(decisions):
                        if repeated.is_terminal():
                            raise RuntimeError("seeded repeat ended before the original duel")
                        repeated_actions = repeated.legal_actions()
                        repeated_observation = repeated.step(
                            repeated_agent.select_action(repeated_observation,
                                                         repeated_actions))
                    repeated_trajectory = repeated.trajectory() if repeated.is_terminal() else None
                    if (repeated_trajectory is None
                            or repeated_trajectory.decisions != trajectory.decisions
                            or repeated_trajectory.terminal_observation
                            != trajectory.terminal_observation
                            or repeated.result() != winner):
                        raise RuntimeError("seeded repeat changed decisions, state, or outcome")
                repeated_games += 1
                repeated_decisions += decisions
            error = None
        except (OSError, RuntimeError, ValueError) as exc:
            terminal, winner = False, None
            error = f"{type(exc).__name__}: {exc}"
        game = {"seed": seed, "deck": str(path), "deck_sha256": sha256_file(path),
                "decisions": decisions, "terminal": terminal, "winner": winner,
                "action_kinds": sorted(kinds), "error": error}
        if distinct_opponents:
            game["opponent_deck"] = str(opponent_path)
            game["opponent_deck_sha256"] = sha256_file(opponent_path)
        if verify_replays:
            game["replay_verified_decisions"] = verified if error is None else None
        if repeat_seeds:
            game["deterministic_repeat"] = error is None
        games.append(game)
    report = {"max_decisions": max_decisions, "games": games}
    if card_pool != "whitelist":
        report["card_pool"] = card_pool
    if distinct_opponents:
        report["distinct_opponents"] = True
        report["opponent_seed_offset"] = 1_000_000
    if card_pool == "tournament" or verify_replays:
        report["rules_profile"] = rules_profile
        report["loaded_asset_sha256"] = dict(sorted(loaded_assets.items()))
        report["asset_sha256"] = {
            name: sha256_file(root / relative)
            for name, relative in {
                "core_library": "build/libocgcore.so",
                "cards_database": "database/cards.cdb",
                "goat_database": "database/goat-entries.cdb",
                "goat_whitelist": "banlist/GOAT.lflist.conf",
                "global_constants": "scripts/constant.lua",
                "global_utility": "scripts/utility.lua",
            }.items()
        }
    if card_pool == "tournament":
        source_root = Path(__file__).resolve().parents[1] / "examples/decks"
        report["source_deck_sha256"] = {
            name: sha256_file(source_root / name) for name in TOURNAMENT_MAIN_DECKS
        }
    if verify_replays:
        report["replay_verification"] = {
            "verified_games": sum(game["replay_verified_decisions"] is not None
                                  for game in games),
            "verified_decisions": sum(game["replay_verified_decisions"] or 0
                                      for game in games),
        }
        report["visibility_audit"] = {
            "audited_games": visibility_games,
            **dict(sorted(visibility_counts.items())),
        }
    if repeat_seeds:
        report["determinism"] = {"repeated_games": repeated_games,
                                 "identical_decisions": repeated_decisions}
    if count_card_actions:
        report["card_actions"] = [
            {"code": code, "kind": kind, "offered_decisions": offered[code, kind],
             "selected_decisions": selected[code, kind]}
            for code, kind in sorted(offered)
        ]
        report["chain_responses"] = [
            {"responder_code": responder, "preceding_link_code": preceding,
             "selected_decisions": count}
            for (responder, preceding), count in sorted(
                responses.items(), key=lambda item: (-item[1], item[0]))
        ]
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path, default=Path(".cache/goat-ai/random-probe"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--max-decisions", type=int, default=500)
    parser.add_argument("--card-pool", choices=("whitelist", "tournament"),
                        default="whitelist")
    parser.add_argument("--verify-replays", action="store_true")
    parser.add_argument("--distinct-opponents", action="store_true",
                        help="generate an independent legal opponent deck per seed")
    parser.add_argument("--count-card-actions", action="store_true",
                        help="count source-card options and selected chain responses")
    parser.add_argument("--repeat-seeds", action="store_true",
                        help="rerun each complete duel and require identical decisions, terminal state, and outcome")
    args = parser.parse_args()
    if args.seeds < 1 or args.max_decisions < 1:
        parser.error("--seeds and --max-decisions must be positive")
    report = probe(args.native_root, args.output, args.seed, args.seeds,
                   args.max_decisions, args.card_pool, args.verify_replays,
                   args.distinct_opponents, args.count_card_actions,
                   args.repeat_seeds)
    for game in report["games"]:
        status = "error" if game["error"] else "terminal" if game["terminal"] else "limit"
        suffix = f" error={game['error']}" if game["error"] else ""
        print(f"seed={game['seed']} decisions={game['decisions']} status={status}{suffix}")
    print(f"report={args.output / 'report.json'}")
    if any(game["error"] or ((args.verify_replays or args.repeat_seeds)
                             and not game["terminal"])
           for game in report["games"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
