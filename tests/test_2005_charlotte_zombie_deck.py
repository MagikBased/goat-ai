"""Published SJC Charlotte 2005 Zombie Main Deck and native duel coverage."""

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
ZOMBIE = ROOT / "examples/decks/zombie_jae_kim_charlotte_2005.ydk"
PHOENIX = ROOT / "examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk"

EXPECTED_MAIN = Counter({
    "Vampire Lord": 2, "Pyramid Turtle": 2, "Spirit Reaper": 2,
    "Morphing Jar": 1, "Breaker the Magical Warrior": 1,
    "Tribe-Infecting Virus": 1, "Sangan": 1, "Sinister Serpent": 1,
    "Giant Rat": 2, "Magician of Faith": 2, "Airknight Parshath": 1,
    "Exiled Force": 1, "Pot of Greed": 1, "Delinquent Duo": 1,
    "Graceful Charity": 1, "Premature Burial": 1, "Book of Life": 2,
    "Book of Moon": 3, "Mystical Space Typhoon": 1,
    "Nobleman of Crossout": 2, "Snatch Steal": 1,
    "Lightning Vortex": 1, "Heavy Storm": 1, "Creature Swap": 1,
    "Dust Tornado": 3, "Call of the Haunted": 1,
    "Ring of Destruction": 1, "Torrential Tribute": 1,
    "Mirror Force": 1,
})


def test_published_charlotte_zombie_deck_has_exactly_40_main_cards():
    deck = read_ydk(ZOMBIE)
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (40, 0, 0)
    assert sum(EXPECTED_MAIN.values()) == 40


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_published_charlotte_zombie_deck_matches_pinned_card_names():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(ZOMBIE)
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb",
    )
    names = {}
    for database in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        with sqlite3.connect(root / "database" / database) as connection:
            for code in set(deck.main) - names.keys():
                row = connection.execute("SELECT name FROM texts WHERE id=?", (code,)).fetchone()
                if row:
                    names[code] = row[0].removesuffix(" (GOAT)").removesuffix(" (Pre-Errata)")
    assert names.keys() >= set(deck.main)
    assert Counter(names[code] for code in deck.main) == EXPECTED_MAIN


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("zombie_seat", [0, 1])
def test_charlotte_zombie_completes_visible_replay_verified_duel(tmp_path, zombie_seat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = (ZOMBIE, PHOENIX) if zombie_seat == 0 else (PHOENIX, ZOMBIE)
    seed = 36000 + zombie_seat
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        assert env.is_terminal(), "Zombie/Phoenix duel exceeded 3000 decisions"
        trajectory = env.trajectory()
    path = tmp_path / "charlotte_zombie.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(loaded)["decisions"] == len(
        trajectory.decisions)
