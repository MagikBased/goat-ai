"""Full-deck native coverage for documented Goat Control versus Chaos Turbo."""

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
GOAT_CONTROL = REPOSITORY / "examples/decks/goat_control_lolmarcus_2020.ydk"
CHAOS = REPOSITORY / "examples/decks/chaos_turbo_riclar_2020.ydk"
WARRIOR = REPOSITORY / "examples/decks/warrior_montague_clash.ydk"
RESTRICT = 504700102


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("seed,goat_seat", [(1, 0), (7, 1)])
@pytest.mark.parametrize("opponent", [CHAOS, WARRIOR])
def test_full_goat_control_duel_and_replay(tmp_path, seed, goat_seat, opponent):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(GOAT_CONTROL)
    assert len(deck.main) == 40 and not deck.side
    assert deck.extra == (RESTRICT,) * 3
    copies = Counter(deck.main)
    assert copies[504700123] == 2  # Scapegoat
    assert copies[46411259] == 3   # Metamorphosis
    assert copies[34853266] == 2   # Tsukuyomi
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb")
    decks = (str(GOAT_CONTROL), str(opponent)) if goat_seat == 0 \
        else (str(opponent), str(GOAT_CONTROL))
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
            pytest.fail("Goat Control duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert len(trajectory.decisions) > 100
        assert trajectory.deck_sha256 is not None
        assert trajectory.asset_sha256 is not None
        assert any(tuple(c.code for c in record.observation.own_extra_deck)
                   == (RESTRICT,) * 3 for record in trajectory.decisions
                   if record.observation.viewer == goat_seat)
    path = tmp_path / "goat_control_vs_chaos.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
