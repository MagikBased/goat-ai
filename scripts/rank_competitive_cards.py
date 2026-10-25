"""Rank Main Deck cards across the six documented competitive example lists.

This counts local examples, not tournament usage or metagame share.
"""

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from goat_ai.engine.decks import read_ydk

ROOT = Path(__file__).resolve().parents[1]
DECKS = (
    "goat_control_lolmarcus_2020.ydk",
    "chaos_turbo_riclar_2020.ydk",
    "warrior_montague_clash.ydk",
    "chaos_control_insids_worlds_2022.ydk",
    "flip_control_goatformat_guide.ydk",
    "chaos_return_dingosig_worlds_2022.ydk",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--cards-db", type=Path, action="append", default=[],
                        help="Optional card database; repeat for GOAT and pre-errata names")
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be positive")
    for path in args.cards_db:
        if not path.is_file():
            parser.error(f"card database does not exist: {path}")

    prevalence: Counter[int] = Counter()
    copies: Counter[int] = Counter()
    for name in DECKS:
        main_cards = Counter(read_ydk(ROOT / "examples" / "decks" / name).main)
        prevalence.update(main_cards.keys())
        copies.update(main_cards)

    databases = [sqlite3.connect(path) for path in args.cards_db]
    try:
        writer = csv.writer(sys.stdout)
        writer.writerow(("lists", "copies", "code", "name"))
        ranked = sorted(prevalence, key=lambda code: (-prevalence[code], -copies[code], code))
        for code in ranked[:args.top]:
            name = ""
            for database in databases:
                row = database.execute("SELECT name FROM texts WHERE id = ?", (code,)) \
                    .fetchone()
                if row is not None:
                    name = row[0]
                    break
            writer.writerow((prevalence[code], copies[code], code, name))
    finally:
        for database in databases:
            database.close()


if __name__ == "__main__":
    main()
