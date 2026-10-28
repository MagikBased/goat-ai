"""Published 2005 SJC Seattle Top 8 lists used as held-out evaluation decks.

Source: https://www.goatformat.com/home/top-8-decklists9351056
Side Decks are omitted because single-duel evaluation does not sideboard.
"""

import os
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_goat_whitelist, read_ydk, validate_goat_deck

ROOT = Path(__file__).resolve().parents[1]
DECKS = {
    "theeresak": ROOT / "examples/decks/goat_control_theeresak_poonsombat_seattle_2005.ydk",
    "christian": ROOT / "examples/decks/goat_control_christian_martinez_seattle_2005.ydk",
}
MAIN = {
    "theeresak": Counter({
        "D.D. Assailant": 3, "Magician of Faith": 1,
        "Airknight Parshath": 2,
        "Black Luster Soldier - Envoy of the Beginning": 1,
        "Breaker the Magical Warrior": 1, "Spirit Reaper": 1,
        "Tribe-Infecting Virus": 1, "D.D. Survivor": 1,
        "D.D. Warrior Lady": 1, "Sinister Serpent": 1,
        "Asura Priest": 1, "Sangan": 1, "Tsukuyomi": 1,
        "Smashing Ground": 1, "Nobleman of Crossout": 2,
        "Heavy Storm": 1, "Book of Moon": 1, "Delinquent Duo": 1,
        "Pot of Greed": 1, "Lightning Vortex": 1,
        "Premature Burial": 1, "Snatch Steal": 1,
        "Metamorphosis": 1, "Scapegoat": 2,
        "D.D. Designator": 1, "Graceful Charity": 1,
        "Mystical Space Typhoon": 1, "Reinforcement of the Army": 1,
        "Ring of Destruction": 1, "Dust Tornado": 2,
        "Mirror Force": 1, "Sakuretsu Armor": 1,
        "Waboku": 1, "Call of the Haunted": 1,
        "Torrential Tribute": 1,
    }),
    "christian": Counter({
        "D.D. Assailant": 2, "Magician of Faith": 2,
        "Tsukuyomi": 2, "Airknight Parshath": 2,
        "D.D. Warrior Lady": 1, "Asura Priest": 1,
        "Sangan": 1, "Spirit Reaper": 1,
        "Tribe-Infecting Virus": 1, "Breaker the Magical Warrior": 1,
        "Sinister Serpent": 1,
        "Black Luster Soldier - Envoy of the Beginning": 1,
        "Scapegoat": 2, "Metamorphosis": 2,
        "Nobleman of Crossout": 2, "Pot of Greed": 1,
        "Graceful Charity": 1, "Premature Burial": 1,
        "Book of Moon": 1, "Swords of Revealing Light": 1,
        "Smashing Ground": 1, "Delinquent Duo": 1,
        "Heavy Storm": 1, "Lightning Vortex": 1,
        "Mystical Space Typhoon": 1,
        "Dust Tornado": 2, "Mirror Force": 1, "Waboku": 1,
        "Torrential Tribute": 1, "Sakuretsu Armor": 1,
        "Ring of Destruction": 1, "Call of the Haunted": 1,
    }),
}
EXTRA = {
    "theeresak": Counter({
        "Fusionist": 1, "Thousand-Eyes Restrict": 3,
        "Ryu Senshi": 3, "Dark Balter the Terrible": 3,
        "Dark Flare Knight": 2, "Fiend Skull Dragon": 2,
        "Ojama King": 1, "Sanwitch": 2, "Darkfire Dragon": 1,
        "Giltia the D. Knight": 2, "Musician King": 1,
        "Reaper on the Nightmare": 1,
        "Dragoness the Wicked Knight": 1, "Flame Ghost": 1,
        "Gatling Dragon": 2, "Twin-Headed Thunder Dragon": 1,
        "The Last Warrior from Another Planet": 1,
        "St. Joan": 1, "King Dragun": 1,
    }),
    "christian": Counter({
        "Thousand-Eyes Restrict": 3, "Gatling Dragon": 1,
        "Dark Balter the Terrible": 2, "Ryu Senshi": 2,
        "Dark Blade the Dragon Knight": 1,
        "Reaper on the Nightmare": 1, "St. Joan": 1,
        "Musician King": 1, "Giltia the D. Knight": 1,
        "King Dragun": 1, "Master of Oz": 1,
        "Ojama King": 1,
        "The Last Warrior from Another Planet": 1,
        "Darkfire Dragon": 1,
        "Dragoness the Wicked Knight": 1,
        "Charubin the Fire Knight": 1, "Fusionist": 1,
    }),
}


@pytest.mark.parametrize("name,main_size,extra_size", [
    ("theeresak", 41, 30), ("christian", 40, 21),
])
def test_published_deck_sizes(name, main_size, extra_size):
    deck = read_ydk(DECKS[name])
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (main_size, extra_size, 0)
    assert (sum(MAIN[name].values()), sum(EXTRA[name].values())) == (main_size, extra_size)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("name", DECKS)
def test_printed_names_and_pinned_goat_legality(name):
    native = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(DECKS[name])
    validate_goat_deck(deck, read_goat_whitelist(native / "banlist/GOAT.lflist.conf"),
                       native / "database/cards.cdb", native / "database/goat-entries.cdb",
                       native / "database/cards-unofficial.cdb")
    names = {}
    for database in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        with sqlite3.connect(native / "database" / database) as connection:
            for code in set(deck.main + deck.extra) - names.keys():
                row = connection.execute("SELECT name FROM texts WHERE id=?", (code,)).fetchone()
                if row:
                    names[code] = row[0].removesuffix(" (GOAT)").removesuffix(" (Pre-Errata)")
    assert names.keys() >= set(deck.main + deck.extra)
    assert Counter(names[code] for code in deck.main) == MAIN[name]
    assert Counter(names[code] for code in deck.extra) == EXTRA[name]
