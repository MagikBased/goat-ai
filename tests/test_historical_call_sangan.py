"""Destroying an active Call also destroys its revived Sangan and starts its search."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
CALL = 97077563
MST = 5318639
SANGAN = 504700178
MYSTICAL_ELF = 15025844
SECOND_DISCARD = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_call_revives_sangan_then_mst_destroys_it_and_sangan_searches(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, CALL, MST)}
    scripts.add(f"goat/c{SANGAN}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    cards = [GRACEFUL, CALL, MST, *VANILLA_DECK[3:]]
    cards[cards.index(MYSTICAL_ELF)] = SANGAN
    deck = tmp_path / "call_sangan.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = call_set = mst_used = mst_targeted = False
        call_used = call_targeted = searched = False
        selected_code = None
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"]
                                   for c in a.parameters["cards"]} == {
                                       SANGAN, SECOND_DISCARD}), None)
                    discarded |= action is not None
                if discarded and not call_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL), None)
                    call_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and call_set:
                if not mst_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == MST), None)
                    mst_used |= action is not None
                if mst_used and not mst_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == CALL
                                   and a.parameters.get("controller") == 0), None)
                    mst_targeted |= action is not None
                if mst_targeted and not call_used:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == CALL), action)
                    call_used |= action is not None and action.kind == "chain"
                    if call_used:
                        assert [link.card_code for link in obs.chain] == [MST]
                if call_used and not call_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == SANGAN
                                   and a.parameters.get("controller") == 0), None)
                    call_targeted |= action is not None
                if call_targeted and not searched and actions[0].kind == "select_card":
                    options = [a for a in actions if a.parameters.get("location") == 1]
                    if options:
                        assert all("sequence" not in a.parameters for a in options)
                        action = options[0]
                        selected_code = action.parameters["code"]
                        searched = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if searched and not obs.chain and SANGAN in {c.code for c in obs.graveyards[0]}:
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert {CALL, MST, SANGAN} <= {c.code for c in owner.graveyards[0]}
                assert not any(c.code == SANGAN and c.zone == "monster" for c in owner.field)
                assert selected_code in {c.code for c in owner.hand}
                assert opponent.known_opponent_hand_cards == (selected_code,)
                assert not owner.private_reveals
                assert [c.code for c in opponent.private_reveals[-1].cards] == [selected_code]
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                break
        else:
            pytest.fail(f"Call/Sangan search stalled: Graceful={graceful}/{discarded} "
                        f"Call={call_set}/{call_used}/{call_targeted} "
                        f"MST={mst_used}/{mst_targeted} searched={searched} turn={obs.turn}")

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        else:
            pytest.fail("Call/Sangan duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert trajectory.winner in (0, 1, None)
        assert any([link.card_code for link in record.observation.chain] == [MST]
                   and record.selected_action.kind == "chain"
                   and record.selected_action.parameters.get("code") == CALL
                   for record in trajectory.decisions)
    path = tmp_path / "call_sangan.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
