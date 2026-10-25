"""Swords blocks three opposing turns and expires in the third End Phase."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SWORDS = 72302403


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_swords_expires_after_opponents_third_turn(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{SWORDS}.lua").is_file():
        pytest.skip("Swords of Revealing Light script not installed")
    own = tmp_path / "swords.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        SWORDS, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SWORDS in {c.code for c in obs.hand}
        swords_activated = attacker_summoned = expired_seen = False
        battle_checked: set[int] = set()
        attacker_code = None
        for _ in range(220):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not swords_activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SWORDS), None)
                swords_activated |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not attacker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    attacker_summoned = True
                    attacker_code = action.parameters["code"]
            if obs.turn == 7 and not expired_seen:
                assert battle_checked == {2, 4, 6}
                assert SWORDS in {c.code for c in obs.graveyards[0]}
                assert SWORDS not in {c.code for c in obs.field}
                expired_seen = True
            if obs.turn in (2, 4, 6, 8) and obs.acting_player == 1:
                if obs.phase == "main1" and obs.turn not in battle_checked \
                        and (obs.turn != 2 or attacker_summoned) and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"),
                                  action)
                if obs.phase == "battle_start" and obs.turn not in battle_checked:
                    assert any(c.code == attacker_code and c.controller == 1
                               and c.position == "faceup" for c in obs.field), (
                                   obs.turn, attacker_code,
                                   [(c.code, c.controller, c.position)
                                    for c in obs.field])
                    attacks = [a for a in actions if a.kind == "attack"]
                    assert bool(attacks) == (obs.turn == 8)
                    assert (SWORDS in {c.code for c in obs.field}) == (
                        obs.turn != 8)
                    battle_checked.add(obs.turn)
                    if obs.turn == 8:
                        assert expired_seen
                        assert f"official/c{SWORDS}.lua" in (
                            env.engine.probe.loaded_script_sha256)
                        agents = (RandomAgent(316), RandomAgent(317))
                        for _ in range(5000):
                            obs = env.step(agents[obs.acting_player].select_action(
                                obs, env.legal_actions()))
                            if env.is_terminal():
                                path = tmp_path / "swords_expiration.json"
                                write_trajectory(path, env.trajectory())
                                assert verify_trajectory(read_trajectory(path),
                                                         ExperimentalOcgcoreEngine(root)) \
                                    == len(env.trajectory().decisions)
                                return
                        pytest.fail("Swords expiration duel did not finish")
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "main2", "end_phase", "pass", "place")), actions[0])
            obs = env.step(action)
    pytest.fail(f"Swords expiration did not reach turn 8: {battle_checked}")
