"""Control stolen mid-chain does not transfer an activated Faith effect."""

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

POT = 55144522
FAITH = 31560081
ENEMY_CONTROLLER = 98045062


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("take_control", [False, True])
def test_faith_spell_recovery_stays_with_effect_activator(tmp_path, take_control):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own = tmp_path / "faith.ydk"
    other = tmp_path / "controller.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        POT, FAITH, FAITH, FAITH, *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")
    other.write_text("#main\n" + "\n".join(map(str, (
        ENEMY_CONTROLLER, ENEMY_CONTROLLER, ENEMY_CONTROLLER,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), 18,
                         ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT, FAITH}.issubset(c.code for c in obs.hand)
        assert ENEMY_CONTROLLER in {c.code for c in env.engine.probe.observation(1).hand}
        used_pot = set_faith = summoned_fodder = set_controller = False
        flipped = targeted_pot = chained = mode_chosen = paid_cost = targeted_faith = False
        recovered = False
        for _ in range(180):
            legal = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not used_pot:
                    action = next((a for a in legal if a.kind == "activate"
                                   and a.parameters.get("code") == POT), None)
                    used_pot |= action is not None
                if used_pot and not set_faith and action is None:
                    action = next((a for a in legal if a.kind == "set_monster"
                                   and a.parameters.get("code") == FAITH), None)
                    set_faith |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned_fodder:
                    action = next((a for a in legal if a.kind == "normal_summon"), None)
                    summoned_fodder |= action is not None
                if summoned_fodder and not set_controller and action is None:
                    action = next((a for a in legal if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                    set_controller |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if set_faith and not flipped:
                    action = next((a for a in legal if a.kind == "flip_summon"
                                   and a.parameters.get("code") == FAITH), action)
                    flipped |= action is not None and action.kind == "flip_summon"
                if flipped and not targeted_pot and legal[0].kind == "select_card":
                    action = next((a for a in legal if a.parameters.get("code") == POT
                                   and a.parameters.get("location") == 16), action)
                    targeted_pot |= action is not None and action.kind == "select_card"
            if targeted_pot and obs.acting_player == 1 and not chained \
                    and obs.chain and obs.chain[-1].card_code == FAITH:
                if take_control:
                    action = next((a for a in legal if a.kind == "chain"
                                   and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                    chained |= action is not None
                else:
                    action = next((a for a in legal if a.kind == "pass"), None)
            if chained and not mode_chosen and legal[0].kind == "select_option":
                assert len(legal) == 2
                action = legal[1]
                mode_chosen = True
            if mode_chosen and legal[0].kind == "select_card":
                if not paid_cost:
                    action = next((a for a in legal if a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), None)
                    paid_cost |= action is not None
                elif not targeted_faith:
                    action = next((a for a in legal if a.parameters.get("controller") == 0
                                   and a.parameters.get("code") == FAITH), None)
                    targeted_faith |= action is not None
            if action is None:
                action = next((a for a in legal if a.kind in (
                    "place", "pass", "end_phase")), legal[0])
            obs = env.step(action)
            if targeted_pot and not obs.chain and POT in {c.code for c in obs.hand} \
                    and any(c.code == FAITH for c in obs.field):
                own_view = env.engine.probe.observation(0)
                other_view = env.engine.probe.observation(1)
                faith = next(c for c in own_view.field if c.code == FAITH)
                assert faith.controller == (1 if take_control else 0)
                assert POT in {c.code for c in own_view.hand}
                assert POT not in {c.code for c in other_view.hand}
                assert POT in other_view.known_opponent_hand_cards
                if take_control:
                    assert chained and mode_chosen and paid_cost and targeted_faith
                recovered = True
                break
        assert used_pot and set_faith and summoned_fodder and set_controller
        assert flipped and targeted_pot and recovered
        loaded_scripts = env.engine.probe.loaded_script_sha256
        assert {f"official/c{code}.lua" for code in (POT, FAITH)} <= set(loaded_scripts)
        if take_control:
            assert f"official/c{ENEMY_CONTROLLER}.lua" in loaded_scripts
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(
                obs, env.legal_actions()))
        assert env.is_terminal()
        trajectory = replace(env.trajectory(), source="scripted_effect_probe")
        path = tmp_path / f"faith_controller_{take_control}.json"
        write_trajectory(path, trajectory)
        loaded = read_trajectory(path)
        assert loaded == trajectory
        assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
            loaded.decisions)
        assert audit_trajectory_visibility(loaded)["decisions"] == len(
            loaded.decisions)
