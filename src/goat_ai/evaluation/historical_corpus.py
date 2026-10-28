"""Published 2005 Indianapolis Top 8 Main Decks for audit prioritization.

The source has several non-40-card totals. Preserve the published entries;
this corpus is evidence of listed cards, not validated playable deck files.
"""

import csv
from collections import Counter
from pathlib import Path

CORPUS_PATH = (Path(__file__).resolve().parents[3] / "configs" / "historical"
               / "sjc_indianapolis_2005_top8_main.csv")


def historical_main_decks(path: Path = CORPUS_PATH) -> dict[str, Counter[str]]:
    decks: dict[str, Counter[str]] = {}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            copies = int(row["copies"])
            if copies < 1 or copies > 3:
                raise ValueError(f"invalid copies for {row['player']}: {copies}")
            deck = decks.setdefault(row["player"], Counter())
            if row["card"] in deck:
                raise ValueError(f"duplicate card for {row['player']}: {row['card']}")
            deck[row["card"]] = copies
    return decks


def historical_card_counts(path: Path = CORPUS_PATH) -> list[tuple[str, int, int]]:
    """Return (card name, listed decks, total copies), sorted by prevalence."""
    prevalence: Counter[str] = Counter()
    copies: Counter[str] = Counter()
    for deck in historical_main_decks(path).values():
        prevalence.update(deck.keys())
        copies.update(deck)
    return sorted(((name, count, copies[name]) for name, count in prevalence.items()),
                  key=lambda row: (-row[1], -row[2], row[0]))
