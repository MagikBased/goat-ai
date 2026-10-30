"""Premature Burial destruction must schedule Sacred Phoenix's 2005 revival."""

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
MST = 5318639
BOOK = 14087893
FILLER = 79182538


def _deck(path: Path, cards: list[int]) -> str:
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("destroy_equip", [False, True])
def test_premature_destroyed_by_mst_schedules_phoenix_return(tmp_path, destroy_equip):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, PREMATURE, MST, BOOK)}
    scripts.add(f"goat/c{PHOENIX}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required Phoenix / Equip scripts not installed")
    owner = _deck(tmp_path / "phoenix.ydk", [
        GRACEFUL, PREMATURE, PHOENIX, *VANILLA_DECK[3:]])
    opponent_cards = [MST, *VANILLA_DECK[1:]]
    opponent_cards[4] = BOOK
    opponent = _deck(tmp_path / "opponent.ydk", opponent_cards)

    with GoatEnvironment(owner, opponent, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, PREMATURE, PHOENIX} <= {c.code for c in obs.hand}
        assert {MST, BOOK} <= {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = premature = targeted_phoenix = phoenix_summoned = False
        book_set = mst_used = mst_target_chosen = phoenix_destroyed = False
        phoenix_returned = book_destroyed = False
        for _ in range(130):
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
                if premature and not targeted_phoenix and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == PHOENIX
                                   and a.parameters.get("location") == 16), None)
                    targeted_phoenix |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if phoenix_summoned and not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
                if book_set and not mst_used and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == MST), None)
                    mst_used |= action is not None
                if mst_used and not mst_target_chosen and actions[0].kind == "select_card":
                    target_code = PREMATURE if destroy_equip else BOOK
                    action = next((a for a in actions if
                                   a.parameters.get("code") == target_code), None)
                    mst_target_chosen |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if targeted_phoenix and not phoenix_summoned and PHOENIX in {
                    c.code for c in obs.field if c.zone == "monster"}:
                assert obs.life_points == (7200, 8000)
                assert any(c.code == PREMATURE for c in obs.field)
                phoenix_summoned = True
            if mst_target_chosen and PHOENIX in {c.code for c in obs.graveyards[0]}:
                phoenix_destroyed = True
            if destroy_equip and phoenix_destroyed and obs.turn == 3 and PHOENIX in {
                    c.code for c in obs.field if c.zone == "monster"}:
                phoenix_returned = True
                if BOOK in {c.code for c in obs.graveyards[1]} and not obs.chain:
                    assert not any(c.code == BOOK for c in obs.field)
                    assert {GRACEFUL, PREMATURE} <= {c.code for c in obs.graveyards[0]}
                    book_destroyed = True
                    break
            if (not destroy_equip and mst_target_chosen and obs.turn == 3
                    and obs.phase == "main1" and not obs.chain):
                assert PHOENIX in {c.code for c in obs.field if c.zone == "monster"}
                assert PHOENIX not in {c.code for c in obs.graveyards[0]}
                assert any(c.code == PREMATURE for c in obs.field)
                assert BOOK in {c.code for c in obs.graveyards[1]}
                break
        assert all((graceful, discarded, premature, targeted_phoenix,
                    phoenix_summoned, book_set, mst_used, mst_target_chosen)), (
                        obs.turn, obs.phase, obs.acting_player)
        assert (phoenix_destroyed, phoenix_returned, book_destroyed) == (
            (True, True, True) if destroy_equip else (False, False, False))
        assert scripts <= env.engine.probe.loaded_script_sha256.keys()
        agents = (RandomAgent(101), RandomAgent(102))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        assert env.is_terminal(), "Phoenix fixture exceeded 3000 decisions"
        trajectory = env.trajectory()
    path = tmp_path / "phoenix_premature_mst.json"
    write_trajectory(path, trajectory)
    assert verify_trajectory(read_trajectory(path), ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(trajectory)["decisions"] == len(
        trajectory.decisions)
