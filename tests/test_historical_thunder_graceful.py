"""Chaos Turbo's Thunder Dragon search feeds Graceful Charity's discard."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

THUNDER = 504700054
GRACEFUL = 79571449


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_graceful_discards_two_publicly_searched_thunder_dragons(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{THUNDER}.lua", f"official/c{GRACEFUL}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    deck = tmp_path / "thunder_graceful.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        THUNDER, THUNDER, THUNDER, GRACEFUL, *VANILLA_DECK[4:])))
                    + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {THUNDER, GRACEFUL} <= {c.code for c in obs.hand}
        assert sum(c.code == THUNDER for c in obs.hand) == 1
        searched = activated_thunder = activated_graceful = discarded = checked = False
        deck_before = obs.deck_counts[0]
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert checked, (activated_thunder, searched, activated_graceful,
                                 discarded, obs.turn, obs.phase)
                path = tmp_path / "thunder_graceful.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not discarded:
                if not activated_thunder:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == THUNDER), None)
                    activated_thunder |= action is not None
                elif not searched and any(a.kind == "select_cards" for a in actions):
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and len(a.parameters["cards"]) == 2
                                   and all(c["code"] == THUNDER
                                           for c in a.parameters["cards"])), None)
                    searched |= action is not None
                elif searched and not activated_graceful:
                    opponent = env.engine.probe.observation(1)
                    assert opponent.known_opponent_hand_cards.count(THUNDER) == 2
                    assert obs.deck_counts[0] == deck_before - 2
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    activated_graceful |= action is not None
                elif activated_graceful and any(a.kind == "select_cards" for a in actions):
                    assert obs.deck_counts[0] == deck_before - 5
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and len(a.parameters["cards"]) == 2
                                   and all(c["code"] == THUNDER
                                           for c in a.parameters["cards"])), None)
                    discarded |= action is not None
            if action is None and not discarded:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if discarded and not checked:
                own = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                if GRACEFUL in {c.code for c in own.graveyards[0]} and not own.chain:
                    assert sum(c.code == THUNDER for c in own.graveyards[0]) == 3
                    assert not any(c.code == THUNDER for c in own.hand)
                    assert opponent.known_opponent_hand_cards == ()
                    assert opponent.opponent_hand_count == len(own.hand)
                    assert own.deck_counts[0] == deck_before - 5
                    assert any([c.code for c in reveal.cards] == [THUNDER, THUNDER]
                               for reveal in opponent.private_reveals)
                    assert not own.private_reveals
                    assert set(scripts) <= env.engine.probe.loaded_script_sha256.keys()
                    checked = True
    pytest.fail("Thunder Dragon / Graceful Charity duel did not finish")
