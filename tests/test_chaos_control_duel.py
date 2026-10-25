"""Sourced 2022 Worlds Chaos Control deck legality and full-duel protocol."""

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
CHAOS_CONTROL = REPOSITORY / "examples/decks/chaos_control_insids_worlds_2022.ydk"
CHAOS_TURBO = REPOSITORY / "examples/decks/chaos_turbo_riclar_2020.ydk"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("control_seat", [0, 1])
def test_sourced_chaos_control_full_duel_and_replay(tmp_path, control_seat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(CHAOS_CONTROL)
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (40, 15, 15)
    main, extra = Counter(deck.main), Counter(deck.extra)
    assert main[504700118] == 1  # GOAT Black Luster Soldier
    assert main[504700054] == 3   # GOAT Thunder Dragon
    assert main[504700123] == 2   # GOAT Scapegoat
    assert main[511000824] == 1   # pre-errata Ring of Destruction
    assert extra[504700102] == 3  # GOAT Thousand-Eyes Restrict
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb")

    paths = (str(CHAOS_CONTROL), str(CHAOS_TURBO)) if control_seat == 0 else (
        str(CHAOS_TURBO), str(CHAOS_CONTROL))
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
            pytest.fail("sourced Chaos Control duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert len(trajectory.decisions) > 100
        assert trajectory.winner in (0, 1, None)
        assert trajectory.deck_sha256 is not None
        assert trajectory.asset_sha256 is not None
        assert any(504700054 in record.observation.own_main_deck
                   for record in trajectory.decisions
                   if record.observation.viewer == control_seat)
    path = tmp_path / "chaos_control.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
