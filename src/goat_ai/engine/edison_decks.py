"""Edison-era deck constraints, conditional on an independently audited card pool.

The March 2010 restrictions do not establish release eligibility. Callers must
provide the exact card IDs allowed by a separately audited TCG cutoff list.
This validator does not certify card scripts or enable Edison simulation.
"""

import sqlite3
from collections import Counter
from collections.abc import Collection, Mapping
from pathlib import Path

from goat_ai.engine.decks import Decklist

FUSION = 0x40
SYNCHRO = 0x2000
TOKEN = 0x4000
XYZ = 0x800000
PENDULUM = 0x1000000
LINK = 0x4000000


def validate_edison_deck(deck: Decklist, eligible_ids: Collection[int],
                         restrictions: Mapping[int, int], database: Path) -> None:
    """Check 2009 deck construction using an explicit, audited release pool.

    ``restrictions`` maps canonical card IDs to the official March 2010 copy
    caps. IDs absent from it have the ordinary three-copy cap. Printed variants
    share one cap across Main, Extra, and Side Decks.
    """
    if not eligible_ids or any(code <= 0 for code in eligible_ids):
        raise ValueError("Edison requires a nonempty audited eligible-card ID set")
    if any(code <= 0 or cap not in (0, 1, 2) for code, cap in restrictions.items()):
        raise ValueError("invalid Edison restriction map")
    if not 40 <= len(deck.main) <= 60:
        raise ValueError("Edison Main Deck must contain 40 to 60 cards")
    if len(deck.extra) > 15 or len(deck.side) > 15:
        raise ValueError("Edison Extra and Side Decks cannot exceed 15 cards")

    eligible = set(eligible_ids)
    counts: Counter[int] = Counter()
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as connection:
        for zone, cards in (("main", deck.main), ("extra", deck.extra),
                            ("side", deck.side)):
            for code in cards:
                if code not in eligible:
                    raise ValueError(f"card {code} is outside the audited Edison pool")
                row = connection.execute("SELECT alias, type FROM datas WHERE id=?",
                                         (code,)).fetchone()
                if row is None:
                    raise ValueError(f"card {code} is absent from the pinned database")
                alias, card_type = row
                canonical = alias or code
                if alias and connection.execute("SELECT 1 FROM datas WHERE id=?",
                                                (alias,)).fetchone() is None:
                    raise ValueError(f"card {code} has an unresolved canonical alias")
                if card_type & (TOKEN | XYZ | PENDULUM | LINK):
                    raise ValueError(f"card {code} has a type unavailable in Edison")
                is_extra = bool(card_type & (FUSION | SYNCHRO))
                if zone == "extra" and not is_extra:
                    raise ValueError(f"card {code} is not a Fusion or Synchro monster")
                if zone == "main" and is_extra:
                    raise ValueError(f"Fusion or Synchro monster {code} cannot be in Main")
                counts[canonical] += 1
                cap = restrictions.get(canonical, 3)
                if counts[canonical] > cap:
                    raise ValueError(f"card {code} exceeds Edison copy limit {cap}")
