"""A stolen Phoenix destroyed by effect returns to its owner."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
PREMATURE = 70828912
PHOENIX = 504700099
SNATCH = 45986603
MST = 5318639
FILLER = 79182538


def _deck(path: Path, cards: list[int]) -> str:
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("destroy_premature", [False, True])
def test_stolen_phoenix_destroyed_by_premature_returns_to_owner(
        tmp_path, destroy_premature):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, PREMATURE, SNATCH, MST)}
    scripts.add(f"goat/c{PHOENIX}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required Phoenix / control-change scripts not installed")
    owner = _deck(tmp_path / "phoenix.ydk", [
        GRACEFUL, PREMATURE, PHOENIX, *VANILLA_DECK[3:]])
    opponent_cards = [SNATCH, *VANILLA_DECK[1:]]
    opponent_cards[4] = MST
    opponent = _deck(tmp_path / "snatch.ydk", opponent_cards)

    with GoatEnvironment(owner, opponent, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, PREMATURE, PHOENIX} <= {c.code for c in obs.hand}
        assert {SNATCH, MST} <= {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = premature = phoenix_targeted = phoenix_summoned = False
        snatch_used = snatch_targeted = stolen = mst_used = mst_targeted = False
        phoenix_destroyed = returned_to_owner = False
        for _ in range(150):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {PHOENIX, FILLER}), None)
                    discarded |= action is not None
                if discarded and not premature and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE), None)
                    premature |= action is not None
                if premature and not phoenix_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == PHOENIX
                                   and a.parameters.get("location") == 16), None)
                    phoenix_targeted |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if phoenix_summoned and not snatch_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH), None)
                    snatch_used |= action is not None
                if snatch_used and not snatch_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == PHOENIX
                                   and a.parameters.get("controller") == 0), None)
                    snatch_targeted |= action is not None
                if stolen and not mst_used and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == MST), None)
                    mst_used |= action is not None
                if mst_used and not mst_targeted and actions[0].kind == "select_card":
                    target = PREMATURE if destroy_premature else SNATCH
                    controller = 0 if destroy_premature else 1
                    action = next((a for a in actions if a.parameters.get("code") == target
                                   and a.parameters.get("controller") == controller), None)
                    mst_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if phoenix_targeted and not phoenix_summoned and any(
                    c.code == PHOENIX and c.controller == 0 for c in obs.field):
                phoenix_summoned = True
                assert obs.life_points == (7200, 8000)
            if snatch_targeted and any(c.code == PHOENIX and c.controller == 1
                                       for c in obs.field):
                stolen = True
            if mst_targeted and PHOENIX in {c.code for c in obs.graveyards[0]}:
                phoenix_destroyed = True
                assert PHOENIX not in {c.code for c in obs.graveyards[1]}
            if phoenix_destroyed and obs.turn == 3 and any(
                    c.code == PHOENIX and c.controller == 0 for c in obs.field):
                assert SNATCH in {c.code for c in obs.graveyards[1]}
                assert PREMATURE in {c.code for c in obs.graveyards[0]}
                returned_to_owner = True
                break
            if (not destroy_premature and mst_targeted and obs.turn == 2
                    and not obs.chain and SNATCH in {c.code for c in obs.graveyards[1]}
                    and any(c.code == PHOENIX and c.controller == 0 for c in obs.field)):
                assert PHOENIX not in {c.code for c in obs.graveyards[0]}
                assert any(c.code == PREMATURE for c in obs.field)
                returned_to_owner = True
                break
        assert all((graceful, discarded, premature, phoenix_targeted,
                    phoenix_summoned, snatch_used, snatch_targeted, stolen,
                    mst_used, mst_targeted, returned_to_owner)), (
                        obs.turn, obs.phase, obs.acting_player)
        assert phoenix_destroyed == destroy_premature
        assert scripts <= env.engine.probe.loaded_script_sha256.keys()
        agents = (RandomAgent(105), RandomAgent(106))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        assert env.is_terminal(), "Phoenix control-change fixture exceeded 3000 decisions"
        trajectory = env.trajectory()
    path = tmp_path / "phoenix_snatch_owner.json"
    write_trajectory(path, trajectory)
    assert verify_trajectory(read_trajectory(path), ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(trajectory)["decisions"] == len(
        trajectory.decisions)
