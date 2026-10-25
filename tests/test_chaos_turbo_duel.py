"""Full-deck native protocol coverage for a documented Chaos Turbo list."""

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
CHAOS = REPOSITORY / "examples/decks/chaos_turbo_riclar_2020.ydk"
CONTROL = REPOSITORY / "examples/decks/control_probe.ydk"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("seed,chaos_seat", [(1, 0), (7, 1)])
def test_full_chaos_turbo_duel_and_replay(tmp_path, seed, chaos_seat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(CHAOS)
    assert len(deck.main) == 40 and not deck.extra and not deck.side
    copies = Counter(deck.main)
    assert copies[504700054] == 3  # GOAT Thunder Dragon
    assert copies[16226796] == 2   # pre-errata Night Assailant
    assert copies[4178474] == 3    # Raigeki Break
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb")
    decks = (str(CHAOS), str(CONTROL)) if chaos_seat == 0 \
        else (str(CONTROL), str(CHAOS))
    with GoatEnvironment(*decks, seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        agents = (RandomAgent(seed), RandomAgent(seed + 1000))
        for _ in range(3000):
            action = agents[obs.acting_player].select_action(obs, env.legal_actions())
            obs = env.step(action)
            if env.is_terminal():
                break
        else:
            pytest.fail("full Chaos Turbo duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert len(trajectory.decisions) > 100
        assert trajectory.winner in (0, 1, None)
        assert trajectory.deck_sha256 is not None
        assert trajectory.asset_sha256 is not None
        assert any(16226796 in record.observation.own_main_deck
                   for record in trajectory.decisions
                   if record.observation.viewer == chaos_seat)
    path = tmp_path / "chaos_turbo.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
