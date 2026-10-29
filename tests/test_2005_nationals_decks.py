"""Published U.S. Nationals 2005 Top 8 lists used as independent GOAT decks.

Source: https://www.goatformat.com/home/us-nationals-top-8-decklists
Only the printed Main Deck and Max Suffridge's printed Fusion Deck are known.
"""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents.card_metadata import load_card_names
from goat_ai.engine.decks import read_goat_whitelist, read_ydk, validate_goat_deck

ROOT = Path(__file__).resolve().parents[1]
DECKS = {
    "max": ROOT / "examples/decks/goat_control_max_suffridge_nationals_2005.ydk",
    "jonathan": ROOT / "examples/decks/chaos_jonathan_labounty_nationals_2005.ydk",
}
MAIN = {
    "max": Counter({
        "Sinister Serpent": 1, "Magician of Faith": 2,
        "Gravekeeper's Spy": 2, "Sangan": 1,
        "Tribe-Infecting Virus": 1, "D.D. Warrior Lady": 1,
        "Tsukuyomi": 1, "Jinzo": 1, "Airknight Parshath": 1,
        "Black Luster Soldier - Envoy of the Beginning": 1,
        "Gravekeeper's Guard": 1, "Blade Knight": 1,
        "Morphing Jar": 1, "Breaker the Magical Warrior": 1,
        "Swords of Revealing Light": 1, "Mystical Space Typhoon": 1,
        "Heavy Storm": 1, "Graceful Charity": 1, "Pot of Greed": 1,
        "Snatch Steal": 1, "Premature Burial": 1,
        "Delinquent Duo": 1, "Scapegoat": 3, "Metamorphosis": 2,
        "Book of Moon": 2, "Nobleman of Crossout": 2,
        "Ring of Destruction": 1, "Mirror Force": 1,
        "Sakuretsu Armor": 2, "Torrential Tribute": 1,
        "Call of the Haunted": 1, "Ceasefire": 1, "Dust Tornado": 1,
    }),
    "jonathan": Counter({
        "Black Luster Soldier - Envoy of the Beginning": 1,
        "Chaos Sorcerer": 1, "Jinzo": 1, "Airknight Parshath": 1,
        "Tribe-Infecting Virus": 1, "Sinister Serpent": 1,
        "D.D. Assailant": 1, "Exiled Force": 1,
        "Morphing Jar": 1, "Blade Knight": 1,
        "D.D. Warrior Lady": 1, "Magician of Faith": 2,
        "Breaker the Magical Warrior": 1,
        "Kycoo the Ghost Destroyer": 1, "Don Zaloog": 1,
        "Apprentice Magician": 2, "Pot of Greed": 1,
        "Graceful Charity": 1, "Delinquent Duo": 1,
        "Enemy Controller": 1, "Reinforcement of the Army": 1,
        "Heavy Storm": 1, "Snatch Steal": 1,
        "Lightning Vortex": 1, "Premature Burial": 1,
        "Mystical Space Typhoon": 1,
        "Swords of Revealing Light": 1,
        "Nobleman of Crossout": 2, "Book of Moon": 2,
        "Scapegoat": 2, "Ring of Destruction": 1,
        "Torrential Tribute": 1, "Magic Cylinder": 1,
        "Call of the Haunted": 1, "Mirror Force": 1,
    }),
}
MAX_EXTRA = Counter({
    "Thousand-Eyes Restrict": 3, "Dark Balter the Terrible": 3,
    "Reaper on the Nightmare": 2, "Ryu Senshi": 2,
    "Flame Ghost": 2, "Darkfire Dragon": 2,
    "Karbonala Warrior": 1, "Fusionist": 1,
    "Gatling Dragon": 1, "Black Skull Dragon": 1,
    "Ojama King": 1, "Dark Blade the Dragon Knight": 1,
    "King Dragun": 2, "Gaia the Dragon Champion": 1,
})


@pytest.mark.parametrize(("name", "main_size", "extra_size"), [
    ("max", 41, 23), ("jonathan", 40, 0),
])
def test_nationals_deck_sizes(name, main_size, extra_size):
    deck = read_ydk(DECKS[name])
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (
        main_size, extra_size, 0)
    assert sum(MAIN[name].values()) == main_size
    if name == "max":
        assert sum(MAX_EXTRA.values()) == extra_size


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("name", DECKS)
def test_nationals_printed_names_and_goat_legality(name):
    native = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(DECKS[name])
    validate_goat_deck(deck, read_goat_whitelist(native / "banlist/GOAT.lflist.conf"),
                       native / "database/cards.cdb", native / "database/goat-entries.cdb",
                       native / "database/cards-unofficial.cdb")
    names = load_card_names(native)
    def title(code):
        return names[code].removesuffix(" (GOAT)").removesuffix(" (Pre-Errata)")
    assert Counter(title(code) for code in deck.main) == MAIN[name]
    if name == "max":
        assert Counter(title(code) for code in deck.extra) == MAX_EXTRA
