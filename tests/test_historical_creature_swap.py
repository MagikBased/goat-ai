"""Creature Swap chooses monsters during resolution and changes control permanently."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

CREATURE_SWAP = 31036355


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_creature_swap_choices_after_chain_and_permanent_control(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{CREATURE_SWAP}.lua").is_file():
        pytest.skip("Creature Swap script not installed")
    own = tmp_path / "swap.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([CREATURE_SWAP] * 2), *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        first_summoned = opponent_summoned = second_summoned = swap_used = False
        chose_own = chose_opponent = resolved = False
        first_code = second_code = opponent_code = None
        for _ in range(50):
            actions = env.legal_actions()
            action = None
            if first_summoned and not opponent_summoned \
                    and observation.acting_player == 0:
                assert not any(a.kind == "activate" and a.parameters.get("code")
                               == CREATURE_SWAP for a in actions)
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not first_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    first_summoned = True
                    first_code = action.parameters["code"]
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not opponent_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    opponent_summoned = True
                    opponent_code = action.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0:
                if not second_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        second_summoned = True
                        second_code = action.parameters["code"]
                if action is None and second_summoned and not swap_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == CREATURE_SWAP), None)
                    swap_used |= action is not None
            if swap_used and actions[0].kind == "select_card":
                assert len(observation.chain) == 1
                assert observation.chain[0].card_code == CREATURE_SWAP
                if observation.acting_player == 0 and not chose_own:
                    assert {(a.parameters["code"], a.parameters["controller"])
                            for a in actions} == {(first_code, 0), (second_code, 0)}
                    action = next(a for a in actions
                                  if a.parameters["code"] == first_code)
                    chose_own = True
                elif observation.acting_player == 1 and not chose_opponent:
                    assert len(actions) == 1
                    assert actions[0].parameters["code"] == opponent_code
                    assert actions[0].parameters["controller"] == 1
                    action = actions[0]
                    chose_opponent = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if chose_own and chose_opponent and not resolved and CREATURE_SWAP in {
                    c.code for c in observation.graveyards[0]}:
                assert {(c.code, c.controller) for c in observation.field
                        if c.zone == "monster"} == {
                            (first_code, 1), (second_code, 0), (opponent_code, 0)}
                assert observation.life_points == (8000, 8000)
                resolved = True
            if resolved and observation.turn == 3 and observation.acting_player == 0 \
                    and any(a.kind == "end_phase" for a in env.legal_actions()):
                assert not any(a.kind == "change_position" and a.parameters.get("code")
                               == opponent_code for a in env.legal_actions())
            if resolved and observation.turn >= 4:
                assert {(c.code, c.controller) for c in observation.field
                        if c.zone == "monster"} == {
                            (first_code, 1), (second_code, 0), (opponent_code, 0)}
                assert f"official/c{CREATURE_SWAP}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Creature Swap did not exchange the chosen monsters")
