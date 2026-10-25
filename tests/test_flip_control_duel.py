"""Full-deck native coverage for the sourced Flip Control guide list."""

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
FLIP_CONTROL = REPOSITORY / "examples/decks/flip_control_goatformat_guide.ydk"
CHAOS = REPOSITORY / "examples/decks/chaos_turbo_riclar_2020.ydk"
GOAT_CONTROL = REPOSITORY / "examples/decks/goat_control_lolmarcus_2020.ydk"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("opponent", [CHAOS, GOAT_CONTROL])
@pytest.mark.parametrize("seed,flip_seat", [(31, 0), (37, 1)])
def test_full_flip_control_duel_and_replay(tmp_path, opponent, seed, flip_seat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(FLIP_CONTROL)
    assert len(deck.main) == 40 and not deck.extra and not deck.side
    copies = Counter(deck.main)
    assert copies[34853266] == 3  # Tsukuyomi
    assert copies[87621407] == 3  # Dekoichi
    assert copies[28933734] == 3  # Mask of Darkness
    assert copies[31560081] == 3  # Magician of Faith
    assert copies[35316708] == 3  # Time Seal
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb")
    decks = (str(FLIP_CONTROL), str(opponent)) if flip_seat == 0 \
        else (str(opponent), str(FLIP_CONTROL))
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
            pytest.fail("Flip Control duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert len(trajectory.decisions) > 100
        assert trajectory.deck_sha256 is not None
        assert trajectory.asset_sha256 is not None
        assert any(34853266 in record.observation.own_main_deck
                   for record in trajectory.decisions
                   if record.observation.viewer == flip_seat)
    path = tmp_path / "flip_control.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
