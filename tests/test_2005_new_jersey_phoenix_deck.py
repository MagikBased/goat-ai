"""Published New Jersey 2005 Phoenix Control deck and native duel coverage."""

import os
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ROOT = Path(__file__).resolve().parents[1]
PHOENIX = ROOT / "examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk"
MATT = ROOT / "examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk"

EXPECTED_MAIN = Counter({
    "Airknight Parshath": 1, "D.D. Warrior Lady": 1, "Sangan": 1,
    "Breaker the Magical Warrior": 1, "Exiled Force": 1,
    "Tribe-Infecting Virus": 1, "Apprentice Magician": 3,
    "Black Luster Soldier - Envoy of the Beginning": 1, "Morphing Jar": 1,
    "Reflect Bounder": 1, "Sinister Serpent": 1, "Hand of Nephthys": 1,
    "Magician of Faith": 2, "Sacred Phoenix of Nephthys": 1, "Jinzo": 1,
    "Enemy Controller": 2, "Scapegoat": 2, "Swords of Revealing Light": 1,
    "Nobleman of Crossout": 2, "Pot of Greed": 1, "Graceful Charity": 1,
    "Delinquent Duo": 1, "Book of Moon": 2, "Heavy Storm": 1,
    "Mystical Space Typhoon": 1, "Snatch Steal": 1, "Lightning Vortex": 1,
    "Premature Burial": 1, "Ring of Destruction": 1, "Mirror Force": 1,
    "Call of the Haunted": 1, "Magic Cylinder": 1, "Torrential Tribute": 1,
})
EXPECTED_EXTRA = Counter({
    "Fiend Skull Dragon": 3, "Dark Blade the Dragon Knight": 3,
    "Thousand-Eyes Restrict": 3, "Ryu Senshi": 3,
    "Dark Balter the Terrible": 3, "King Dragun": 3,
})


def test_published_new_jersey_deck_has_40_main_and_18_fusions():
    deck = read_ydk(PHOENIX)
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (40, 18, 0)
    assert sum(EXPECTED_MAIN.values()) == 40
    assert sum(EXPECTED_EXTRA.values()) == 18


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_published_new_jersey_deck_matches_pinned_card_names():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(PHOENIX)
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb",
    )
    names = {}
    for database in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        with sqlite3.connect(root / "database" / database) as connection:
            for code in set(deck.main + deck.extra) - names.keys():
                row = connection.execute("SELECT name FROM texts WHERE id=?", (code,)).fetchone()
                if row:
                    names[code] = row[0].removesuffix(" (GOAT)").removesuffix(" (Pre-Errata)")
    assert names.keys() >= set(deck.main + deck.extra)
    assert Counter(names[code] for code in deck.main) == EXPECTED_MAIN
    assert Counter(names[code] for code in deck.extra) == EXPECTED_EXTRA


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("phoenix_seat", [0, 1])
def test_new_jersey_phoenix_completes_visible_replay_verified_duel(tmp_path, phoenix_seat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = (PHOENIX, MATT) if phoenix_seat == 0 else (MATT, PHOENIX)
    seed = 16200 + phoenix_seat
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        assert env.is_terminal(), "Phoenix Control duel exceeded 3000 decisions"
        trajectory = env.trajectory()
    path = tmp_path / "phoenix_2005.json"
    write_trajectory(path, trajectory)
    assert verify_trajectory(read_trajectory(path), ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(trajectory)["decisions"] == len(
        trajectory.decisions)
