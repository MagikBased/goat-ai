"""2022 Worlds winning Chaos Return deck legality and full-duel protocol."""

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
CHAOS_RETURN = REPOSITORY / "examples/decks/chaos_return_dingosig_worlds_2022.ydk"
WARRIOR = REPOSITORY / "examples/decks/warrior_montague_clash.ydk"
RETURN = 27174286


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("return_seat", [0, 1])
def test_sourced_chaos_return_full_duel_and_replay(tmp_path, return_seat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(CHAOS_RETURN)
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (40, 15, 15)
    main, extra = Counter(deck.main), Counter(deck.extra)
    assert main[RETURN] == 2
    assert main[504700044] == 3  # GOAT Gravekeeper's Spy
    assert main[504700170] == 2  # GOAT Shining Angel
    assert extra[504700102] == 1  # GOAT Thousand-Eyes Restrict
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb")
    paths = (str(CHAOS_RETURN), str(WARRIOR)) if return_seat == 0 else (
        str(WARRIOR), str(CHAOS_RETURN))
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
            pytest.fail("sourced Chaos Return duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert len(trajectory.decisions) > 100
        assert trajectory.winner in (0, 1, None)
        assert trajectory.deck_sha256 is not None
        assert trajectory.asset_sha256 is not None
        assert any(RETURN in record.observation.own_main_deck
                   for record in trajectory.decisions
                   if record.observation.viewer == return_seat)
    path = tmp_path / "chaos_return.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
