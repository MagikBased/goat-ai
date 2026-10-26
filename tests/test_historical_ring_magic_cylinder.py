"""Ring chained to Magic Cylinder removes its attacker before Cylinder resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CYLINDER = 62279055
RING = 511000824


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_ring", [False, True])
def test_ring_chained_to_cylinder_removes_attack_target(tmp_path, chain_ring):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{CYLINDER}.lua", f"pre-errata/c{RING}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "attacker.ydk"
    defender = tmp_path / "defender.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK))
                        + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str,
                        (CYLINDER, RING, *VANILLA_DECK[2:])))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(attacker), str(defender), seed=72,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {CYLINDER, RING} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        summoned = cylinder_set = ring_set = attacked = cylinder_used = False
        ring_used = target_selected = resolved = False
        attack_code = attack_value = None
        random_agent = RandomAgent(72)
        for _ in range(3000):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = next((option for option in actions
                               if option.kind == "normal_summon"), None)
                summoned = action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not cylinder_set:
                    action = next((option for option in actions
                                   if option.kind == "set_spell_trap"
                                   and option.parameters.get("code") == CYLINDER), action)
                    cylinder_set |= action is not None and action.kind == "set_spell_trap"
                elif not ring_set:
                    action = next((option for option in actions
                                   if option.kind == "set_spell_trap"
                                   and option.parameters.get("code") == RING), action)
                    ring_set |= action is not None and action.kind == "set_spell_trap"
            if observation.turn == 3 and observation.acting_player == 0 \
                    and ring_set and not attacked:
                action = next((option for option in actions
                               if option.kind in ("battle_phase", "attack")), action)
                if action is not None and action.kind == "attack":
                    attacked = True
                    attack_code = action.parameters["code"]
                    attack_value = next(card.attack for card in observation.field
                                        if card.controller == 0 and card.code == attack_code)
                    assert attack_value > 0
            if attacked and observation.acting_player == 1 and not cylinder_used:
                option = next((option for option in actions if option.kind == "chain"
                               and option.parameters.get("code") == CYLINDER), None)
                if option is not None:
                    assert observation.phase == "battle_step"
                    action = option
                    cylinder_used = True
            if cylinder_used and observation.chain and not ring_used and chain_ring:
                option = next((option for option in actions if option.kind == "chain"
                               and option.parameters.get("code") == RING), None)
                if option is not None:
                    assert tuple(link.card_code for link in observation.chain) == (CYLINDER,)
                    action = option
                    ring_used = True
            if ring_used and not target_selected and actions[0].kind == "select_card":
                action = next((option for option in actions if
                               option.parameters.get("code") == attack_code and
                               option.parameters.get("controller") == 0), None)
                target_selected |= action is not None
            if action is None:
                if resolved:
                    action = random_agent.select_action(observation, actions)
                else:
                    action = next((option for option in actions if option.kind in (
                        "place", "select_position", "pass", "main2", "end_phase")),
                                  actions[0])
            observation = env.step(action)
            if cylinder_used and not resolved and not observation.chain \
                    and CYLINDER in {card.code for card in observation.graveyards[1]}:
                resolved = True
                assert attacked and (not chain_ring or target_selected)
                assert observation.life_points == (
                    (8000 - attack_value, 8000 - attack_value) if chain_ring
                    else (8000 - attack_value, 8000))
                assert (RING in {card.code for card in observation.graveyards[1]}) \
                    == chain_ring
                assert any(card.code == attack_code for card in
                           observation.graveyards[0]) == chain_ring
                assert set(scripts[:1] if not chain_ring else scripts) <= \
                    env.engine.probe.loaded_script_sha256.keys()
            if env.is_terminal():
                assert resolved
                trajectory = env.trajectory()
                path = tmp_path / "cylinder_ring.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                return
    pytest.fail("Ring / Magic Cylinder fixture did not terminate")
