"""A Phoenix revived by chained Call returns after Typhoon destroys Call."""

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
CALL = 97077563
PHOENIX = 504700099
MST = 5318639
BOOK = 14087893
FILLER = 79182538


def _deck(path: Path, cards: list[int]) -> str:
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_call_chained_to_mst_destroys_phoenix_then_revives_it(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, CALL, MST, BOOK)}
    scripts.add(f"goat/c{PHOENIX}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required Phoenix / Call scripts not installed")
    owner = _deck(tmp_path / "phoenix_call.ydk", [
        GRACEFUL, CALL, PHOENIX, *VANILLA_DECK[3:]])
    opponent_cards = [MST, *VANILLA_DECK[1:]]
    opponent_cards[4] = BOOK
    opponent = _deck(tmp_path / "opponent.ydk", opponent_cards)

    with GoatEnvironment(owner, opponent, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, CALL, PHOENIX} <= {c.code for c in obs.hand}
        assert {MST, BOOK} <= {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = call_set = book_set = mst_used = False
        mst_targeted = call_chained = phoenix_targeted = phoenix_destroyed = False
        phoenix_returned = book_destroyed = False
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
                if discarded and not call_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL), None)
                    call_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if call_set and not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
                if book_set and not mst_used and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == MST), None)
                    mst_used |= action is not None
                if mst_used and not mst_targeted and actions[0].kind == "select_card":
                    assert any(c.controller == 0 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
                    action = next((a for a in actions if a.parameters.get("controller") == 0
                                   and a.parameters.get("location") == 8), None)
                    mst_targeted |= action is not None
            if mst_targeted and obs.acting_player == 0 and not call_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == CALL), action)
                call_chained |= action is not None and action.kind == "chain" \
                    and action.parameters.get("code") == CALL
            if call_chained and not phoenix_targeted and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [MST, CALL]
                action = next((a for a in actions if a.parameters.get("code") == PHOENIX
                               and a.parameters.get("location") == 16), None)
                phoenix_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if phoenix_targeted and PHOENIX in {c.code for c in obs.graveyards[0]} \
                    and CALL in {c.code for c in obs.graveyards[0]}:
                phoenix_destroyed = True
            if phoenix_destroyed and obs.turn == 3 and PHOENIX in {
                    c.code for c in obs.field if c.zone == "monster"}:
                phoenix_returned = True
                if BOOK in {c.code for c in obs.graveyards[1]} and not obs.chain:
                    assert not any(c.code == BOOK for c in obs.field)
                    book_destroyed = True
                    break
        assert all((graceful, discarded, call_set, book_set, mst_used,
                    mst_targeted, call_chained, phoenix_targeted,
                    phoenix_destroyed, phoenix_returned, book_destroyed)), (
                        obs.turn, obs.phase, obs.acting_player)
        assert scripts <= env.engine.probe.loaded_script_sha256.keys()
        agents = (RandomAgent(103), RandomAgent(104))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        assert env.is_terminal(), "Phoenix / Call fixture exceeded 3000 decisions"
        trajectory = env.trajectory()
    path = tmp_path / "phoenix_call_mst.json"
    write_trajectory(path, trajectory)
    assert verify_trajectory(read_trajectory(path), ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(trajectory)["decisions"] == len(
        trajectory.decisions)
