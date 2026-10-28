"""Transcribed SJC New Jersey Top 8 Main and Fusion Decks."""

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
DECKS = {
    "ryan": ROOT / "examples/decks/goat_control_ryan_hayakawa_new_jersey_2005.ydk",
    "theeresak": (ROOT / "examples/decks/"
                  "goat_control_theeresak_poonsombat_new_jersey_2005.ydk"),
}
EXPECTED_MAIN = {
    "ryan": Counter({
        "Magician of Faith": 2, "Blade Knight": 1, "Sinister Serpent": 1,
        "D.D. Assailant": 2, "Airknight Parshath": 1, "Jinzo": 1,
        "Sangan": 1, "Breaker the Magical Warrior": 1,
        "Kycoo the Ghost Destroyer": 1, "Tribe-Infecting Virus": 1,
        "Don Zaloog": 1, "Black Luster Soldier - Envoy of the Beginning": 1,
        "Enraged Battle Ox": 1, "D.D. Warrior Lady": 1,
        "Nobleman of Crossout": 2, "Pot of Greed": 1, "Snatch Steal": 1,
        "Enemy Controller": 2, "Scapegoat": 2, "Graceful Charity": 1,
        "Premature Burial": 1, "Delinquent Duo": 1, "Mystical Space Typhoon": 1,
        "Metamorphosis": 1, "Creature Swap": 1, "Lightning Vortex": 1,
        "Heavy Storm": 1, "Smashing Ground": 1, "Book of Moon": 1,
        "Bottomless Trap Hole": 1, "Dust Tornado": 1, "Torrential Tribute": 1,
        "Mirror Force": 1, "Call of the Haunted": 1, "Ring of Destruction": 1,
    }),
    "theeresak": Counter({
        "Breaker the Magical Warrior": 1, "Magician of Faith": 1,
        "Asura Priest": 1, "Tribe-Infecting Virus": 1,
        "Kycoo the Ghost Destroyer": 1, "D.D. Assailant": 2,
        "Airknight Parshath": 1, "Blade Knight": 1, "Sinister Serpent": 1,
        "Tsukuyomi": 1, "Exiled Force": 1, "Sangan": 1,
        "D.D. Warrior Lady": 1,
        "Black Luster Soldier - Envoy of the Beginning": 1,
        "Don Zaloog": 1, "Delinquent Duo": 1, "Premature Burial": 1,
        "Reinforcement of the Army": 1, "Lightning Vortex": 1,
        "Enemy Controller": 1, "Nobleman of Crossout": 2,
        "Metamorphosis": 1, "Scapegoat": 2, "Mystical Space Typhoon": 1,
        "Smashing Ground": 1, "Book of Moon": 1, "Pot of Greed": 1,
        "Graceful Charity": 1, "Heavy Storm": 1, "Snatch Steal": 1,
        "Ring of Destruction": 1, "Torrential Tribute": 1,
        "Mirror Force": 1, "Dust Tornado": 2, "Call of the Haunted": 1,
        "Bottomless Trap Hole": 1,
    }),
}
EXPECTED_EXTRA = {
    "ryan": Counter({
        "Master of Oz": 1, "Gatling Dragon": 1, "King Dragun": 1,
        "Thousand-Eyes Restrict": 3, "Darkfire Dragon": 1,
        "Reaper on the Nightmare": 2, "Dark Balter the Terrible": 3,
        "Dark Flare Knight": 3, "Ojama King": 1, "Sanwitch": 1,
        "Mokey Mokey King": 1, "Giltia the D. Knight": 1,
        "Musician King": 1, "The Last Warrior from Another Planet": 1,
        "Dark Blade the Dragon Knight": 3, "Ryu Senshi": 3,
    }),
    "theeresak": Counter({
        "Fusionist": 1, "Thousand-Eyes Restrict": 3, "Ryu Senshi": 3,
        "Dark Blade the Dragon Knight": 3, "Dark Balter the Terrible": 3,
        "Dark Flare Knight": 2, "Musician King": 2,
        "Reaper on the Nightmare": 1, "Dragoness the Wicked Knight": 1,
        "Flame Ghost": 1, "Gatling Dragon": 2,
        "Twin-Headed Thunder Dragon": 1,
        "The Last Warrior from Another Planet": 1, "St. Joan": 1,
    }),
}


@pytest.mark.parametrize("name", DECKS)
def test_published_new_jersey_deck_sizes(name):
    deck = read_ydk(DECKS[name])
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (
        40, sum(EXPECTED_EXTRA[name].values()), 0)
    assert sum(EXPECTED_MAIN[name].values()) == 40


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("name", DECKS)
def test_published_new_jersey_deck_matches_pinned_card_names(name):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(DECKS[name])
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb")
    names = {}
    for database in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        with sqlite3.connect(root / "database" / database) as connection:
            for code in {*deck.main, *deck.extra} - names.keys():
                row = connection.execute("SELECT name FROM texts WHERE id=?", (code,)).fetchone()
                if row:
                    names[code] = (row[0].removesuffix(" (GOAT)")
                                   .removesuffix(" (Pre-Errata)"))
    assert names.keys() >= {*deck.main, *deck.extra}
    assert Counter(names[code] for code in deck.main) == EXPECTED_MAIN[name]
    assert Counter(names[code] for code in deck.extra) == EXPECTED_EXTRA[name]


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("first", ("ryan", "theeresak"))
def test_new_jersey_decks_complete_visible_replay_verified_duel(tmp_path, first):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    other = "theeresak" if first == "ryan" else "ryan"
    seed = 17700 + (first == "theeresak")
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    with GoatEnvironment(str(DECKS[first]), str(DECKS[other]), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs,
                                                                    env.legal_actions()))
        assert env.is_terminal(), "New Jersey duel exceeded 3000 decisions"
        trajectory = env.trajectory()
    path = tmp_path / f"new_jersey_{first}.json"
    write_trajectory(path, trajectory)
    replay = read_trajectory(path)
    assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
    assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
