"""Enemy Controller's two modes and historical control-return timing."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

ENEMY_CONTROLLER = 98045062


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
                return
    pytest.fail(f"Enemy Controller {mode} line did not finish")
