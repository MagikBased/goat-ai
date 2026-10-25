"""Rank sourced GOAT Main Deck cards and list historical fixture references.

A code appearing in a test is only a pointer for human review, never a claim
that the card's historical rulings have been validated.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from goat_ai.engine.decks import read_ydk
from goat_ai.evaluation.competitive_corpus import TOURNAMENT_MAIN_DECKS
from scripts.probe_competitive_card_actions import card_names

ROOT = Path(__file__).resolve().parents[1]


def priority_rows(deck_paths: tuple[Path, ...], fixture_paths: tuple[Path, ...],
                  names: dict[int, str]) -> list[dict]:
    """Count Main Deck presence and find exact numeric ID references in fixtures."""
    if not deck_paths:
        raise ValueError("at least one deck is required")
    prevalence: Counter[int] = Counter()
    copies: Counter[int] = Counter()
    for path in deck_paths:
        main = Counter(read_ydk(path).main)
        prevalence.update(main.keys())
        copies.update(main)
    fixture_text = {path: path.read_text(encoding="utf-8") for path in fixture_paths}
    rows = []
    for code in prevalence:
        pattern = re.compile(rf"(?<!\d){code}(?!\d)")
        references = sorted(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT)
                            else str(path) for path, content in fixture_text.items()
                            if pattern.search(content))
        rows.append({"code": code, "name": names.get(code),
                     "main_deck_count": prevalence[code],
                     "main_copies": copies[code],
                     "fixture_references": references})
    return sorted(rows, key=lambda row: (-row["main_deck_count"],
                                         -row["main_copies"],
                                         len(row["fixture_references"]), row["code"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, required=True,
                        help="pinned native assets with the card database")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="emit all rows as JSON")
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be positive")
    deck_paths = tuple(ROOT / "examples/decks" / name
                       for name in TOURNAMENT_MAIN_DECKS)
    codes = {code for path in deck_paths for code in read_ydk(path).main}
    names = card_names(args.native_root, codes)
    fixtures = tuple(sorted((ROOT / "tests").glob("test_historical_*.py")))
    rows = priority_rows(deck_paths, fixtures, names)
    if args.json:
        print(json.dumps({"scope": f"{len(TOURNAMENT_MAIN_DECKS)} sourced tournament "
                                    "Main Decks; numeric fixture references are not "
                                    "historical correctness evidence",
                          "decks": [str(path.relative_to(ROOT)) for path in deck_paths],
                          "cards": rows}, indent=2))
        return
    print("Sourced Main Deck presence; fixture references require review")
    print("| Card | Lists | Copies | Fixture files |")
    print("| --- | ---: | ---: | ---: |")
    for row in rows[:args.top]:
        print(f"| {row['name'] or row['code']} ({row['code']}) | "
              f"{row['main_deck_count']} | {row['main_copies']} | "
              f"{len(row['fixture_references'])} |")


if __name__ == "__main__":
    main()
