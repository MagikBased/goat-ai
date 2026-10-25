"""Creature Swap chooses monsters during resolution and changes control permanently."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("opponent_set", [False, True])
def test_swap_of_set_monster_keeps_former_controller_knowledge(tmp_path, opponent_set):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{CREATURE_SWAP}.lua").is_file():
        pytest.skip("Creature Swap script not installed")
    own = tmp_path / "swap.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([CREATURE_SWAP] * 2), *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_monster = opponent_summoned = swap_used = False
        own_code = opponent_code = None
        for _ in range(50):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not set_monster:
                action = next((a for a in actions if a.kind == "set_monster"), None)
                if action is not None:
                    set_monster = True
                    own_code = action.parameters["code"]
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not opponent_summoned:
                kind = "set_monster" if opponent_set else "normal_summon"
                action = next((a for a in actions if a.kind == kind), None)
                if action is not None:
                    opponent_summoned = True
                    opponent_code = action.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0 and not swap_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CREATURE_SWAP), None)
                swap_used |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if swap_used and CREATURE_SWAP in {c.code for c in observation.graveyards[0]}:
                hidden = next(c for c in observation.field if c.controller == 1
                              and c.zone == "monster")
                assert hidden.position == "facedown" and hidden.code is None
                assert {(c.controller, c.zone, c.sequence, c.code)
                        for c in observation.known_opponent_field_cards} == {
                            (1, "monster", hidden.sequence, own_code)}
                assert any(c.code == opponent_code and c.controller == 0
                           for c in observation.field)
                other = env.engine.probe.observation(1)
                assert any(c.code == own_code and c.controller == 1
                           and c.position == "facedown" for c in other.field)
                if opponent_set:
                    assert any(c.controller == 0 and c.code == opponent_code
                               and c.position == "facedown" for c in observation.field)
                    assert any(c.controller == 0 and c.code is None
                               and c.position == "facedown" for c in other.field)
                    assert {(c.controller, c.zone, c.sequence, c.code)
                            for c in other.known_opponent_field_cards} == {
                                (0, "monster", 0, opponent_code)}
                agents = (RandomAgent(3), RandomAgent(4))
                for _ in range(5000):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        trajectory = env.trajectory()
                        assert trajectory.schema_version == 19
                        path = tmp_path / f"creature_swap_set_{opponent_set}.json"
                        write_trajectory(path, trajectory)
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     trajectory.decisions)
                        return
                pytest.fail("set-monster Creature Swap duel did not finish")
    pytest.fail("Creature Swap did not transfer the set monster")
