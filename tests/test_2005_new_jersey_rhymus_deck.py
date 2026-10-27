"""Rhymus Lizo's published SJC New Jersey 2005 list runs in the native core."""

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
RHY = ROOT / "examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk"
ZOMBIE = ROOT / "examples/decks/zombie_jae_kim_charlotte_2005.ydk"

EXPECTED_MAIN = Counter({
    "Magician of Faith": 2, "D.D. Assailant": 2,
    "D.D. Warrior Lady": 1, "Sangan": 1, "Cannon Soldier": 1,
    "Sinister Serpent": 1, "Breaker the Magical Warrior": 1,
    "Morphing Jar": 1, "Kycoo the Ghost Destroyer": 1,
    "Blade Knight": 1, "Tribe-Infecting Virus": 1,
    "Black Luster Soldier - Envoy of the Beginning": 1,
    "Airknight Parshath": 1, "Jinzo": 1, "Giant Trunade": 1,
    "Snatch Steal": 1, "Graceful Charity": 1,
    "Swords of Revealing Light": 1, "Delinquent Duo": 1,
    "Premature Burial": 1, "Pot of Greed": 1,
    "Mystical Space Typhoon": 1, "Lightning Vortex": 1,
    "Enemy Controller": 1, "Heavy Storm": 1,
    "Scapegoat": 2, "Book of Moon": 2,
    "Nobleman of Crossout": 2, "Ring of Destruction": 1,
    "Mirror Force": 1, "Bottomless Trap Hole": 2,
    "Call of the Haunted": 1, "Torrential Tribute": 1,
    "Ceasefire": 1,
})
EXPECTED_FUSION = Counter({
    "Dark Balter the Terrible": 2, "Ryu Senshi": 2,
    "Gatling Dragon": 2, "Thousand-Eyes Restrict": 2,
})


def test_published_counts():
    deck = read_ydk(RHY)
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (40, 8, 0)
    assert sum(EXPECTED_MAIN.values()) == 40
    assert sum(EXPECTED_FUSION.values()) == 8


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_published_names_and_goat_legality():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(RHY)
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb",
    )
    names = {}
    for database in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        with sqlite3.connect(root / "database" / database) as connection:
            for code in set(deck.main + deck.extra) - names.keys():
                row = connection.execute(
                    "SELECT name FROM texts WHERE id=?", (code,)
                ).fetchone()
                if row:
                    names[code] = row[0].removesuffix(" (GOAT)").removesuffix(" (Pre-Errata)")
    assert names.keys() >= set(deck.main + deck.extra)
    assert Counter(names[code] for code in deck.main) == EXPECTED_MAIN
    assert Counter(names[code] for code in deck.extra) == EXPECTED_FUSION


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("rhymus_seat", [0, 1])
def test_complete_visible_replay_verified_duel(tmp_path, rhymus_seat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = (RHY, ZOMBIE) if rhymus_seat == 0 else (ZOMBIE, RHY)
    seed = 37000 + rhymus_seat
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(
                obs, env.legal_actions()))
        assert env.is_terminal(), "New Jersey/Charlotte duel exceeded 3000 decisions"
        trajectory = env.trajectory()
    path = tmp_path / "new_jersey_rhymus.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(loaded)["decisions"] == len(
        trajectory.decisions)
