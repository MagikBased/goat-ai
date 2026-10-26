"""Historical Assailant effect survives destruction of Necrovalley in its chain."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ASSAILANT = 25262697
NECROVALLEY = 511002998  # pre-errata variant
MST = 5318639
DEFENDER = VANILLA_DECK[4]


def _write_deck(path, substitutions):
    cards = list(VANILLA_DECK)
    for index, code in substitutions:
        cards[index] = code
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_mst", [False, True])
def test_assailant_changes_position_after_necrovalley_is_destroyed(
    tmp_path, chain_mst,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{ASSAILANT}.lua",
               f"pre-errata/c{NECROVALLEY}.lua", f"official/c{MST}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required historical scripts not installed")
    own = _write_deck(tmp_path / "assailant.ydk", ((2, ASSAILANT), (1, NECROVALLEY)))
    other = _write_deck(tmp_path / "mst.ydk", ((20, MST),))

    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {ASSAILANT, NECROVALLEY} <= {c.code for c in observation.hand}
        assert MST in {c.code for c in env.engine.probe.observation(1).hand}
        necro = summoned = mst_set = defender_summoned = attacked = effect = False
        mst_responded = mst_targeted = resolved = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not necro:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == NECROVALLEY), None)
                    necro |= action is not None
                if necro and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon" and
                                   a.parameters.get("code") == ASSAILANT), None)
                    summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not mst_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap" and
                                   a.parameters.get("code") == MST), None)
                    mst_set |= action is not None
                if mst_set and not defender_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon" and
                                   a.parameters.get("code") == DEFENDER), None)
                    defender_summoned |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if observation.phase == "main1" and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                if observation.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack" and
                                   a.parameters.get("code") == ASSAILANT), None)
                    attacked |= action is not None
                if attacked and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") ==
                                   DEFENDER and a.parameters.get("controller") == 1), None)
                if attacked and not effect and actions[0].kind == "no":
                    assert {a.kind for a in actions} == {"yes", "no"}
                    action = next(a for a in actions if a.kind == "yes")
                    effect = True
            if observation.turn == 3 and observation.acting_player == 1 and effect:
                if not mst_responded:
                    response = next((a for a in actions if a.kind == "chain" and
                                     a.parameters.get("code") == MST), None)
                    if response is not None:
                        assert any(c.code == NECROVALLEY for c in observation.field)
                        action = response if chain_mst else next(
                            a for a in actions if a.kind == "pass")
                        mst_responded = True
                if chain_mst and mst_responded and not mst_targeted and \
                        actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") ==
                                   NECROVALLEY and a.parameters.get("controller") == 0), None)
                    mst_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase", "main2")), actions[0])
            observation = env.step(action)
            defender = next((c for c in observation.field if c.code == DEFENDER and
                             c.controller == 1), None)
            if effect and mst_responded and defender is not None and \
                    defender.orientation == "defense":
                assert defender.position == "faceup"
                assert (NECROVALLEY in {c.code for c in observation.graveyards[0]}) \
                    == chain_mst
                assert (NECROVALLEY in {c.code for c in observation.field}) \
                    != chain_mst
                assert (MST in {c.code for c in observation.graveyards[1]}) \
                    == chain_mst
                assert f"official/c{ASSAILANT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                resolved = True
                break
        assert resolved, "Assailant position change did not resolve"

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            observation = env.step(
                agents[observation.acting_player].select_action(observation, legal))
        assert env.is_terminal(), "Assailant duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / f"assailant_mst_{chain_mst}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(
                                     trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
