"""A sourced World Championship Bazoo Return deck plays complete native duels."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

REPOSITORY = Path(__file__).resolve().parent.parent
BAZOO_RETURN = REPOSITORY / "examples/decks/bazoo_return_weirdchamp_worlds.ydk"
GOAT_CONTROL = REPOSITORY / "examples/decks/goat_control_lolmarcus_2020.ydk"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("bazoo_seat", [0, 1])
def test_sourced_bazoo_return_full_duel_and_replay(tmp_path, bazoo_seat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(BAZOO_RETURN)
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (40, 0, 0)
    copies = Counter(deck.main)
    assert copies[40133511] == 3  # Bazoo the Soul-Eater
    assert copies[27174286] == 3  # Return from the Different Dimension
    assert copies[504700143] == 2  # GOAT King Tiger Wanghu
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb")

    paths = (str(BAZOO_RETURN), str(GOAT_CONTROL)) if bazoo_seat == 0 else (
        str(GOAT_CONTROL), str(BAZOO_RETURN))
    with GoatEnvironment(*paths, seed=1,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        agents = (RandomAgent(1), RandomAgent(1001))
        for _ in range(3000):
            action = agents[obs.acting_player].select_action(obs, env.legal_actions())
            obs = env.step(action)
            if env.is_terminal():
                break
        else:
            pytest.fail("sourced Bazoo Return duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert len(trajectory.decisions) > 100
        assert trajectory.winner in (0, 1, None)
        assert trajectory.deck_sha256 is not None
        assert trajectory.asset_sha256 is not None
        assert any(40133511 in decision.observation.own_main_deck
                   for decision in trajectory.decisions
                   if decision.observation.viewer == bazoo_seat)
    path = tmp_path / "bazoo_return.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
