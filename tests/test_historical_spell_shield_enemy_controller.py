"""Spell Shield's free mode negates Enemy Controller's targeted position effect."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ENEMY_CONTROLLER = 98045062
SHIELD = 38275183
UPSTART = 70368879


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_spell_shield_free_mode_negates_enemy_controller_position_change(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (ENEMY_CONTROLLER, SHIELD, UPSTART):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"official script for {code} not installed")
    own = tmp_path / "controller.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        ENEMY_CONTROLLER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other = tmp_path / "shield.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SHIELD, *VANILLA_DECK[1:4], UPSTART, *VANILLA_DECK[5:])))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert ENEMY_CONTROLLER in {card.code for card in obs.hand}
        assert {SHIELD, UPSTART} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        shield_set = summoned = activated = option_chosen = target_chosen = shield_used = False
        target_code = None
        checked = False
        agents = (RandomAgent(9804), RandomAgent(3827))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "shield_enemy_controller.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                assert audit_trajectory_visibility(replay)["decisions"] == len(
                    replay.decisions)
                assert {f"official/c{code}.lua" for code in (ENEMY_CONTROLLER, SHIELD)} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action:
                        summoned = True
                        target_code = action.parameters["code"]
                if action is None and not shield_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SHIELD), None)
                    shield_set |= action is not None
            if not checked and shield_set and summoned and obs.turn == 3 \
                    and obs.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                activated |= action is not None
            if activated and not option_chosen and actions[0].kind == "select_option":
                action = actions[0]
                option_chosen = True
            if activated and option_chosen and not target_chosen \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == target_code
                               and a.parameters.get("controller") == 1), None)
                target_chosen |= action is not None
            if target_chosen and not shield_used and obs.acting_player == 1:
                choices = [a for a in actions if a.kind == "chain"
                           and a.parameters.get("code") == SHIELD]
                if choices:
                    assert [a.parameters.get("effect_option") for a in choices] == [0, 1]
                    assert not obs.known_opponent_hand_cards
                    action = choices[0]
                    shield_used = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if shield_used and not checked and not obs.chain \
                    and SHIELD in {card.code for card in obs.graveyards[1]}:
                target = next(card for card in obs.field if card.code == target_code)
                assert target.controller == 1 and target.orientation == "attack"
                assert UPSTART in {card.code for card in
                                   env.engine.probe.observation(1).hand}
                assert ENEMY_CONTROLLER in {card.code for card in obs.graveyards[0]}
                checked = True
    pytest.fail("Spell Shield / Enemy Controller fixture exceeded decision budget")
