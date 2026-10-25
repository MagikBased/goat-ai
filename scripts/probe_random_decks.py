"""Generate reproducible whitelist-legal decks and probe native decision coverage.

This is protocol triage, not evidence that a sampled duel is GOAT-correct.
Decks and reports are written under the ignored .cache directory by default.
"""

import argparse
import json
import random
import sqlite3
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import Decklist, read_goat_whitelist, validate_goat_deck
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
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


def probe(root: Path, output: Path, first_seed: int, seeds: int,
          max_decisions: int) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    games = []
    for seed in range(first_seed, first_seed + seeds):
        deck = generate_deck(root, seed)
        path = output / f"seed_{seed}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, deck.main)) + "\n#extra\n!side\n")
        decisions = 0
        kinds = set()
        try:
            with GoatEnvironment(str(path), str(path), seed,
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
            error = None
        except (OSError, RuntimeError, ValueError) as exc:
            terminal, winner = False, None
            error = f"{type(exc).__name__}: {exc}"
        games.append({"seed": seed, "deck": str(path), "deck_sha256": sha256_file(path),
                      "decisions": decisions, "terminal": terminal, "winner": winner,
                      "action_kinds": sorted(kinds), "error": error})
    report = {"max_decisions": max_decisions, "games": games}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path, default=Path(".cache/goat-ai/random-probe"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--max-decisions", type=int, default=500)
    args = parser.parse_args()
    if args.seeds < 1 or args.max_decisions < 1:
        parser.error("--seeds and --max-decisions must be positive")
    report = probe(args.native_root, args.output, args.seed, args.seeds,
                   args.max_decisions)
    for game in report["games"]:
        status = "error" if game["error"] else "terminal" if game["terminal"] else "limit"
        suffix = f" error={game['error']}" if game["error"] else ""
        print(f"seed={game['seed']} decisions={game['decisions']} status={status}{suffix}")
    print(f"report={args.output / 'report.json'}")
    if any(game["error"] for game in report["games"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
