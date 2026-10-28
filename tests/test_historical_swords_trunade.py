"""Returning Swords to hand permits a fresh three-turn attack restriction."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SWORDS = 72302403
TRUNADE = 42703248


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_trunade_returns_swords_and_restarts_three_opposing_turns(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (SWORDS, TRUNADE)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    own = tmp_path / "swords_trunade.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        SWORDS, VANILLA_DECK[1], TRUNADE, *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SWORDS, TRUNADE} <= {card.code for card in obs.hand}
        swords_activations = 0
        trunade_used = attacker_summoned = returned_seen = False
        checked_turns = set()
        attacker_code = None
        for _ in range(500):
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.phase == "main1":
                if obs.turn == 1 and swords_activations == 0:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SWORDS), None)
                    swords_activations += action is not None
                elif obs.turn == 3 and not trunade_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == TRUNADE), None)
                    trunade_used = action is not None
                elif obs.turn == 3 and trunade_used and swords_activations == 1 \
                        and TRUNADE in {card.code for card in obs.graveyards[0]}:
                    assert SWORDS in {card.code for card in obs.hand}
                    assert SWORDS not in {card.code for card in obs.field}
                    opponent = env.engine.probe.observation(1)
                    assert SWORDS in opponent.known_opponent_hand_cards
                    returned_seen = True
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SWORDS), None)
                    swords_activations += action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not attacker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    attacker_summoned = True
                    attacker_code = action.parameters["code"]
            if obs.turn in (2, 4, 6, 8, 10) and obs.acting_player == 1:
                if obs.phase == "main1" and attacker_summoned \
                        and obs.turn not in checked_turns and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                if obs.phase == "battle_start" and obs.turn not in checked_turns:
                    assert any(card.code == attacker_code and card.controller == 1
                               for card in obs.field)
                    assert bool([a for a in actions if a.kind == "attack"]) \
                        == (obs.turn == 10)
                    checked_turns.add(obs.turn)
                    if obs.turn == 10:
                        assert swords_activations == 2 and trunade_used and returned_seen
                        assert SWORDS in {card.code for card in obs.graveyards[0]}
                        assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                        agents = (RandomAgent(316), RandomAgent(317))
                        for _ in range(5000):
                            obs = env.step(agents[obs.acting_player].select_action(
                                obs, env.legal_actions()))
                            if env.is_terminal():
                                path = tmp_path / "swords_trunade.json"
                                write_trajectory(path, env.trajectory())
                                replay = read_trajectory(path)
                                assert verify_trajectory(
                                    replay, ExperimentalOcgcoreEngine(root)) \
                                    == len(replay.decisions)
                                assert audit_trajectory_visibility(replay)["decisions"] \
                                    == len(replay.decisions)
                                return
                        pytest.fail("Swords / Trunade duel did not finish")
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "main2", "end_phase", "pass", "place")), actions[0])
            obs = env.step(action)
    pytest.fail(f"Swords / Trunade line did not reach turn 10: {checked_turns}")
