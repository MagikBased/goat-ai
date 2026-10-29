"""A Sheep Token pays Enemy Controller's control cost without a Tribute Summon."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

SCAPEGOAT = 504700123
ENEMY_CONTROLLER = 98045062
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_sheep_token_pays_enemy_controller_control_cost(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SCAPEGOAT, ENEMY_CONTROLLER):
        if not any((root / f"scripts/{folder}/c{code}.lua").is_file()
                   for folder in ("official", "goat")):
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "goat_controller.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, ENEMY_CONTROLLER, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        goat_set = controller_set = opposing_summoned = goats_used = False
        econ_used = mode_chosen = cost_paid = target_chosen = checked = returned = False
        opponent_code = spent_token = None
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(3000):
            if env.is_terminal():
                assert checked and returned
                trajectory = env.trajectory()
                assert verify_trajectory(
                    trajectory, ExperimentalOcgcoreEngine(root)) == len(
                        trajectory.decisions)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                return
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0:
                    if not goat_set:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == SCAPEGOAT), None)
                        goat_set |= action is not None
                    if goat_set and not controller_set and action is None:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                        controller_set |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and not opposing_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        opponent_code = action.parameters["code"]
                        opposing_summoned = True
                if (obs.turn == 2 and obs.phase == "end" and obs.acting_player == 0
                        and opponent_code is not None and not goats_used):
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goats_used |= action is not None
                if (obs.turn == 3 and obs.phase == "main1"
                        and obs.acting_player == 0 and goats_used
                        and not econ_used):
                    assert any(a.kind == "normal_summon" for a in actions)
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                    econ_used |= action is not None
                if econ_used and not mode_chosen and actions[0].kind == "select_option":
                    assert len(actions) == 2
                    action = actions[1]
                    mode_chosen = True
                if mode_chosen and not cost_paid and actions[0].kind == "select_card":
                    own_choices = [a for a in actions
                                   if a.parameters.get("controller") == 0]
                    assert {a.parameters.get("code") for a in own_choices} == SHEEP_CODES
                    action = next((a for a in actions if a.parameters.get("controller") == 0
                                   and a.parameters.get("code") in SHEEP_CODES), None)
                    if action is not None:
                        spent_token = action.parameters["code"]
                        cost_paid = True
                if cost_paid and not target_chosen and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") == opponent_code), None)
                    target_chosen |= action is not None
                if target_chosen and obs.chain == () and ENEMY_CONTROLLER in {
                        c.code for c in obs.graveyards[0]}:
                    own_monsters = [c for c in obs.field if c.zone == "monster"
                                    and c.controller == 0]
                    assert len(own_monsters) == 4
                    assert sum(c.code in SHEEP_CODES for c in own_monsters) == 3
                    assert any(c.code == opponent_code for c in own_monsters)
                    assert spent_token not in {c.code for c in own_monsters}
                    assert any(c.code == opponent_code and c.controller == 0
                               for c in env.engine.probe.observation(1).field)
                    assert {f"{folder}/c{code}.lua" for folder, code in (
                        ("goat", SCAPEGOAT), ("official", ENEMY_CONTROLLER))}.issubset(
                            env.engine.probe.loaded_script_sha256)
                    checked = True
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "pass", "end_phase")), actions[0])
            elif not returned:
                if obs.turn >= 4:
                    assert any(c.code == opponent_code and c.controller == 1
                               for c in obs.field if c.zone == "monster")
                    returned = True
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            else:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
    pytest.fail("Scapegoat/Enemy Controller fixture did not complete")
