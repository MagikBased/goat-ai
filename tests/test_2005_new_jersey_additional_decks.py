"""Two independently published New Jersey Top 8 Main Deck transcriptions."""

import os
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_goat_whitelist, read_ydk, validate_goat_deck

ROOT = Path(__file__).resolve().parents[1]
DECKS = {
    "mary": ROOT / "examples/decks/warrior_mary_triatafilidi_new_jersey_2005.ydk",
    "bryan": ROOT / "examples/decks/chaos_bryan_coronel_new_jersey_2005.ydk",
}
EXPECTED = {
    "mary": Counter({
        "D.D. Warrior Lady": 1, "Sinister Serpent": 1,
        "Breaker the Magical Warrior": 1,
        "Black Luster Soldier - Envoy of the Beginning": 1,
        "Airknight Parshath": 1, "Sangan": 1,
        "Tribe-Infecting Virus": 1, "Jinzo": 1,
        "Spirit Reaper": 2, "Magician of Faith": 2,
        "D.D. Assailant": 3, "Blade Knight": 2,
        "Lightning Vortex": 1, "Graceful Charity": 1,
        "Mystical Space Typhoon": 1, "Premature Burial": 1,
        "Smashing Ground": 1, "Pot of Greed": 1,
        "Delinquent Duo": 1, "Snatch Steal": 1,
        "Heavy Storm": 1, "Enemy Controller": 1,
        "Nobleman of Crossout": 2, "Scapegoat": 2,
        "Book of Moon": 2, "Ring of Destruction": 1,
        "Torrential Tribute": 1, "Mirror Force": 1,
        "Call of the Haunted": 1, "Dust Tornado": 1,
        "Bottomless Trap Hole": 2,
    }),
    "bryan": Counter({
        "Breaker the Magical Warrior": 1, "Spirit Reaper": 1,
        "Magician of Faith": 2, "D.D. Assailant": 2,
        "Apprentice Magician": 1,
        "Black Luster Soldier - Envoy of the Beginning": 1,
        "Jinzo": 1, "Airknight Parshath": 1,
        "Tribe-Infecting Virus": 1, "Sangan": 1,
        "D.D. Warrior Lady": 1, "Sinister Serpent": 1,
        "Morphing Jar": 1, "Kycoo the Ghost Destroyer": 1,
        "Heavy Storm": 1, "Delinquent Duo": 1,
        "Premature Burial": 1, "Scapegoat": 2,
        "Graceful Charity": 1, "Swords of Revealing Light": 1,
        "Snatch Steal": 1, "Nobleman of Crossout": 2,
        "Lightning Vortex": 1, "Smashing Ground": 1,
        "Mystical Space Typhoon": 1, "Pot of Greed": 1,
        "Creature Swap": 1, "Book of Moon": 2,
        "Mirror Force": 1, "Ring of Destruction": 1,
        "Sakuretsu Armor": 1, "Bottomless Trap Hole": 2,
        "Ceasefire": 1, "Call of the Haunted": 1,
        "Torrential Tribute": 1,
    }),
}


@pytest.mark.parametrize("name,main_size", [("mary", 40), ("bryan", 41)])
def test_published_main_sizes(name, main_size):
    deck = read_ydk(DECKS[name])
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (main_size, 0, 0)
    assert sum(EXPECTED[name].values()) == main_size


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("name", DECKS)
def test_published_names_and_pinned_goat_legality(name):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(DECKS[name])
    validate_goat_deck(deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
                       root / "database/cards.cdb", root / "database/goat-entries.cdb",
                       root / "database/cards-unofficial.cdb")
    names = {}
    for database in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        with sqlite3.connect(root / "database" / database) as connection:
            for code in set(deck.main) - names.keys():
                row = connection.execute("SELECT name FROM texts WHERE id=?", (code,)).fetchone()
                if row:
                    names[code] = (row[0].removesuffix(" (GOAT)")
                                   .removesuffix(" (Pre-Errata)"))
    assert names.keys() >= set(deck.main)
    assert Counter(names[code] for code in deck.main) == EXPECTED[name]
