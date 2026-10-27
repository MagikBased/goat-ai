"""Wanghu's summon trigger resolves before Exiled Force can Tribute itself."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

WANGHU = 504700143  # GOAT variant
EXILED_FORCE = 74131780
ARCHFIEND_SOLDIER = 49881766


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("wanghu_present", [False, True])
def test_wanghu_preempts_exiled_force_ignition_effect(tmp_path, wanghu_present):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{WANGHU}.lua", f"official/c{EXILED_FORCE}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    wanghu_deck = tmp_path / "wanghu.ydk"
    wanghu_deck.write_text("#main\n" + "\n".join(map(str, (
        *([WANGHU] * 3), *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")
    exiled_deck = tmp_path / "exiled.ydk"
    exiled_deck.write_text("#main\n" + "\n".join(map(str, (
        EXILED_FORCE, *VANILLA_DECK[1:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(wanghu_deck), str(exiled_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {WANGHU, ARCHFIEND_SOLDIER} <= {card.code for card in obs.hand}
        assert EXILED_FORCE in {card.code for card in env.engine.probe.observation(1).hand}
        first_summoned = exiled_summoned = effect_used = target_chosen = False
        checked = False
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"wanghu_exiled_{wanghu_present}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) \
                    == len(trajectory.decisions)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not first_summoned:
                wanted = WANGHU if wanghu_present else ARCHFIEND_SOLDIER
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == wanted), None)
                first_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not exiled_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == EXILED_FORCE), None)
                exiled_summoned |= action is not None
            if exiled_summoned and not checked:
                if wanghu_present:
                    assert not any(a.kind == "activate" and
                                   a.parameters.get("code") == EXILED_FORCE for a in actions)
                elif obs.acting_player == 1 and not effect_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == EXILED_FORCE), action)
                    effect_used |= action is not None and action.kind == "activate"
                if effect_used and not target_chosen and actions[0].kind == "select_card":
                    assert EXILED_FORCE in {card.code for card in obs.graveyards[1]}
                    action = next((a for a in actions if a.parameters.get("code")
                                   == ARCHFIEND_SOLDIER and
                                   a.parameters.get("controller") == 0), None)
                    target_chosen |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if exiled_summoned and not checked and not obs.chain and \
                    EXILED_FORCE in {card.code for card in obs.graveyards[1]}:
                assert obs.life_points == (8000, 8000)
                if wanghu_present:
                    assert not effect_used
                    assert any(card.code == WANGHU for card in obs.field)
                    assert f"goat/c{WANGHU}.lua" in \
                        env.engine.probe.loaded_script_sha256
                else:
                    assert effect_used and target_chosen
                    assert ARCHFIEND_SOLDIER in {
                        card.code for card in obs.graveyards[0]}
                    assert not any(card.code == ARCHFIEND_SOLDIER
                                   for card in obs.field)
                assert f"official/c{EXILED_FORCE}.lua" in \
                    env.engine.probe.loaded_script_sha256
                checked = True
    pytest.fail("Wanghu / Exiled Force duel did not finish")
