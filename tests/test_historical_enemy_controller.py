"""Enemy Controller's two modes and historical control-return timing."""

import os
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ENEMY_CONTROLLER = 98045062
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("mode", ["position", "control"])
def test_enemy_controller_modes_and_end_phase_return(tmp_path, mode):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{ENEMY_CONTROLLER}.lua").is_file():
        pytest.skip("Enemy Controller script not installed")
    deck = tmp_path / "enemy_controller.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        ENEMY_CONTROLLER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        def finish_and_verify(view):
            agents = (RandomAgent(18), RandomAgent(19))
            for _ in range(3000):
                if env.is_terminal():
                    break
                view = env.step(agents[view.acting_player].select_action(
                    view, env.legal_actions()))
            assert env.is_terminal()
            trajectory = replace(
                env.trajectory(), source="scripted_effect_probe",
                skill_metadata={"demonstrator_seat": 0,
                                "teacher": "scripted_effect_probe"})
            options = [record for record in trajectory.decisions
                       if record.observation.chain
                       and record.observation.chain[-1].card_code == ENEMY_CONTROLLER
                       and len(record.legal_actions) == 2
                       and all(action.kind == "select_option"
                               for action in record.legal_actions)]
            assert len(options) == 1
            assert options[0].legal_actions.index(options[0].selected_action) == (
                0 if mode == "position" else 1)
            path = tmp_path / f"enemy_controller_{mode}.json"
            write_trajectory(path, trajectory)
            loaded = read_trajectory(path)
            assert loaded == trajectory
            assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
                loaded.decisions)
            assert audit_trajectory_visibility(loaded)["decisions"] == len(
                loaded.decisions)

        observation = env.reset()
        set_card = own_summoned = opponent_summoned = activated = option_chosen = False
        own_code = target_code = None
        took_control = checked_resolution = False
        for _ in range(60):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not set_card:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                    set_card = action is not None
                if action is None and not own_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        own_summoned = True
                        own_code = action.parameters["code"]
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not opponent_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    opponent_summoned = True
                    target_code = action.parameters["code"]
            if opponent_summoned and not activated and observation.turn == 3 \
                    and observation.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                activated = action is not None
                if activated:
                    opponent_view = env.engine.probe.observation(1)
                    assert any(c.code is None and c.zone == "spell_trap"
                               and c.controller == 0 for c in opponent_view.field)
            if activated and not option_chosen and actions[0].kind == "select_option":
                assert len(actions) == 2
                action = actions[0 if mode == "position" else 1]
                option_chosen = True
            if activated and actions[0].kind == "select_card":
                if mode == "control" and not took_control:
                    own_targets = [a for a in actions if a.parameters.get("controller") == 0]
                    if own_targets:
                        assert {a.parameters["code"] for a in own_targets} == {own_code}
                        action = own_targets[0]
                        took_control = True
                if action is None:
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") == target_code), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if activated and ENEMY_CONTROLLER in {
                    c.code for c in observation.graveyards[0]} and not checked_resolution:
                monsters = [c for c in observation.field if c.zone == "monster"]
                target = next(c for c in monsters if c.code == target_code)
                assert observation.life_points == (8000, 8000)
                if mode == "position":
                    assert target.controller == 1 and target.orientation == "defense"
                    assert any(c.code == own_code and c.controller == 0 for c in monsters)
                    assert own_code not in {c.code for c in observation.graveyards[0]}
                    assert "official/c98045062.lua" in env.engine.probe.loaded_script_sha256
                    finish_and_verify(observation)
                    return
                assert took_control
                assert target.controller == 0 and target.position == "faceup"
                assert own_code in {c.code for c in observation.graveyards[0]}
                assert not any(c.code == own_code for c in monsters)
                checked_resolution = True
            if checked_resolution and observation.turn >= 4:
                target = next(c for c in observation.field if c.zone == "monster"
                              and c.code == target_code)
                assert target.controller == 1
                assert "official/c98045062.lua" in env.engine.probe.loaded_script_sha256
                finish_and_verify(observation)
                return
    pytest.fail(f"Enemy Controller {mode} line did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("mode", ["position", "control"])
def test_book_invalidates_either_enemy_controller_target(tmp_path, mode):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (ENEMY_CONTROLLER, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "enemy_controller.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        ENEMY_CONTROLLER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other = tmp_path / "book.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK_OF_MOON] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        econ_set = own_summoned = opponent_summoned = book_set = False
        activated = mode_chosen = paid_cost = econ_targeted = False
        book_chained = book_targeted = False
        own_code = target_code = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not econ_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                    econ_set |= action is not None
                if econ_set and not own_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        own_code = action.parameters["code"]
                        own_summoned = True
            if obs.turn == 2 and obs.acting_player == 1:
                if not opponent_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        target_code = action.parameters["code"]
                        opponent_summoned = True
                if opponent_summoned and not book_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set \
                    and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                activated |= action is not None
            if activated and not mode_chosen and actions[0].kind == "select_option":
                action = actions[0 if mode == "position" else 1]
                mode_chosen = True
            if mode_chosen and actions[0].kind == "select_card" and not econ_targeted:
                if mode == "control" and not paid_cost:
                    action = next((a for a in actions if a.parameters.get("controller") == 0
                                   and a.parameters.get("code") == own_code), None)
                    paid_cost |= action is not None
                else:
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") == target_code), None)
                    econ_targeted |= action is not None
            if econ_targeted and obs.acting_player == 1 and not book_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                book_chained |= action is not None
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == target_code), None)
                book_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if book_targeted and obs.chain == () and {ENEMY_CONTROLLER, BOOK_OF_MOON} \
                    <= {c.code for pile in obs.graveyards for c in pile}:
                own_view = env.engine.probe.observation(0)
                assert any(c.controller == 1 and c.zone == "monster"
                           and c.position == "facedown" and c.code is None
                           for c in own_view.field)
                assert not any(c.controller == 0 and c.code == target_code
                               for c in own_view.field)
                assert (own_code in {c.code for c in own_view.graveyards[0]}) \
                    == (mode == "control")
                assert not own_view.private_reveals
                assert {f"official/c{code}.lua" for code in (
                    ENEMY_CONTROLLER, BOOK_OF_MOON)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Book did not interrupt Enemy Controller's {mode} mode")
