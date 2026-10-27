"""Solemn can negate Jinzo's Tribute Summon before Jinzo suppresses Traps."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

JINZO = 77585513
SOLEMN = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_judgment_before_jinzo_continuous_effect(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = {f"official/c{code}.lua" for code in (JINZO, SOLEMN)}
    if any(not (root / "scripts" / name).is_file() for name in required):
        pytest.skip("Jinzo and Solemn scripts not installed")
    jinzo_deck = tmp_path / "jinzo.ydk"
    jinzo_deck.write_text("#main\n" + "\n".join(map(str, (
        JINZO, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    solemn_deck = tmp_path / "solemn.ydk"
    solemn_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SOLEMN] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(jinzo_deck), str(solemn_deck), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert JINZO in {card.code for card in observation.hand}
        assert SOLEMN in {card.code for card in env.engine.probe.observation(1).hand}
        tribute_base = trap_set = attempted = responded = checked = False
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(5000):
            if env.is_terminal():
                assert tribute_base and trap_set and attempted and responded and checked
                trajectory = env.trajectory()
                path = tmp_path / f"jinzo_solemn_{negate}.json"
                write_trajectory(path, trajectory)
                loaded = read_trajectory(path)
                assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(loaded)
                assert required <= env.engine.probe.loaded_script_sha256.keys()
                return
            actions = env.legal_actions()
            action = None
            if not checked:
                if observation.turn == 1 and observation.acting_player == 0 \
                        and not tribute_base:
                    action = next((item for item in actions
                                   if item.kind == "normal_summon"
                                   and item.parameters.get("code") != JINZO), None)
                    tribute_base |= action is not None
                if observation.turn == 2 and observation.acting_player == 1 \
                        and not trap_set:
                    action = next((item for item in actions
                                   if item.kind == "set_spell_trap"
                                   and item.parameters.get("code") == SOLEMN), None)
                    trap_set |= action is not None
                if observation.turn == 3 and observation.acting_player == 0 \
                        and not attempted:
                    assert tribute_base and trap_set
                    action = next((item for item in actions
                                   if item.kind == "normal_summon"
                                   and item.parameters.get("code") == JINZO), None)
                    attempted |= action is not None
                if attempted and action is None:
                    action = next((item for item in actions if item.kind == "tribute"), None)
                if attempted and not responded and observation.acting_player == 1:
                    solemn = next((item for item in actions if item.kind == "chain"
                                   and item.parameters.get("code") == SOLEMN), None)
                    if solemn is not None:
                        assert observation.chain == ()
                        assert any(card.code == JINZO for card in observation.field)
                        action = solemn if negate else next(
                            item for item in actions if item.kind == "pass")
                        responded = True
                if responded and observation.turn == 3 \
                        and observation.acting_player == 1 and not negate \
                        and action is None:
                    assert not any(item.kind == "chain"
                                   and item.parameters.get("code") == SOLEMN
                                   for item in actions)
                if responded and observation.turn == 3 and observation.acting_player == 0 \
                        and not observation.chain \
                        and any(item.kind == "end_phase" for item in actions):
                    if negate:
                        assert observation.life_points == (8000, 4000)
                        assert JINZO in {card.code for card in observation.graveyards[0]}
                        assert SOLEMN in {card.code for card in observation.graveyards[1]}
                        assert not any(card.code == JINZO for card in observation.field)
                    else:
                        assert observation.life_points == (8000, 8000)
                        assert any(card.code == JINZO and card.position == "faceup"
                                   for card in observation.field)
                        assert SOLEMN not in {card.code for card in observation.graveyards[1]}
                    assert not any(item.kind == "normal_summon" for item in actions)
                    checked = True
                if action is None and not checked:
                    action = next((item for item in actions if item.kind in (
                        "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[observation.acting_player].select_action(observation, actions)
            observation = env.step(action)
    pytest.fail("Jinzo / Solemn line did not finish")
