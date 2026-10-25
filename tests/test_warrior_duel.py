"""Full-deck native coverage for a documented competitive Warrior list."""

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
WARRIOR = REPOSITORY / "examples/decks/warrior_montague_clash.ydk"
CHAOS = REPOSITORY / "examples/decks/chaos_turbo_riclar_2020.ydk"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("seed,warrior_seat", [(1, 0), (7, 1)])
def test_full_warrior_versus_chaos_duel_and_replay(tmp_path, seed, warrior_seat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(WARRIOR)
    assert len(deck.main) == 40 and not deck.extra and not deck.side
    copies = Counter(deck.main)
    assert copies[39507162] == 3  # Blade Knight
    assert copies[504700077] == 2  # GOAT Mystic Swordsman LV2
    assert copies[504700055] == 2  # GOAT Reinforcement of the Army
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb")
    decks = (str(WARRIOR), str(CHAOS)) if warrior_seat == 0 \
        else (str(CHAOS), str(WARRIOR))
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
            pytest.fail("Warrior versus Chaos duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert len(trajectory.decisions) > 100
        assert trajectory.deck_sha256 is not None
        assert trajectory.asset_sha256 is not None
        assert any(504700055 in record.observation.own_main_deck
                   for record in trajectory.decisions
                   if record.observation.viewer == warrior_seat)
    path = tmp_path / "warrior_vs_chaos.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
