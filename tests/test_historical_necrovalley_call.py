"""Pinned Call/Necrovalley timing, without certifying disputed activation legality."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

GRACEFUL = 79571449
CALL = 97077563
NECROVALLEY = 511002998
MST = 5318639
HEAVY_STORM = 19613556
MYSTICAL_ELF = 15025844
MAD_DOG = 79182538


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("remove_valley_before_resolution", [False, True])
def test_pinned_call_under_necrovalley_with_mst_response(
        tmp_path, remove_valley_before_resolution):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = {f"official/c{code}.lua" for code in (GRACEFUL, CALL, MST)}
    required.add(f"pre-errata/c{NECROVALLEY}.lua")
    if any(not (root / "scripts" / script).is_file() for script in required):
        pytest.skip("required card scripts not installed")
    owner = _deck(tmp_path / "call.ydk", (
        GRACEFUL, CALL, MST, *VANILLA_DECK[3:]))
    opponent = _deck(tmp_path / "valley.ydk", (
        NECROVALLEY, *VANILLA_DECK[1:]))

    with GoatEnvironment(owner, opponent, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = call_set = valley_active = False
        call_used = call_targeted = mst_used = mst_targeted = checked = False
        random_agent = RandomAgent(401)
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                elif not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {MYSTICAL_ELF, MAD_DOG}), None)
                    discarded |= action is not None
                elif discarded and not call_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL), None)
                    call_set |= action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1 and not valley_active:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NECROVALLEY), None)
                valley_active |= action is not None
            if (not checked and obs.turn == 3 and obs.acting_player == 0
                    and obs.phase == "main1" and valley_active and call_set):
                if not call_used:
                    assert any(c.code == NECROVALLEY and c.position == "faceup"
                               for c in obs.field)
                    assert MYSTICAL_ELF in {c.code for c in obs.graveyards[0]}
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == CALL), None)
                    assert action is not None, "pinned core did not offer Call under Necrovalley"
                    call_used = True
                elif not call_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == MYSTICAL_ELF
                                   and a.parameters.get("location") == 16), None)
                    call_targeted |= action is not None
                elif (remove_valley_before_resolution and call_targeted
                      and not mst_used and [link.card_code for link in obs.chain] == [CALL]):
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == MST), None)
                    mst_used |= action is not None
                elif mst_used and not mst_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == NECROVALLEY
                                   and a.parameters.get("controller") == 1), None)
                    mst_targeted |= action is not None
                elif call_targeted and not obs.chain:
                    assert any(c.code == CALL and c.zone == "spell_trap"
                               and c.position == "faceup" for c in obs.field)
                    if remove_valley_before_resolution:
                        assert mst_used and mst_targeted
                        assert any(c.code == MYSTICAL_ELF and c.zone == "monster"
                                   for c in obs.field)
                        assert NECROVALLEY in {c.code for c in obs.graveyards[1]}
                    else:
                        assert not mst_used
                        assert MYSTICAL_ELF in {c.code for c in obs.graveyards[0]}
                        assert any(c.code == NECROVALLEY and c.position == "faceup"
                                   for c in obs.field)
                    assert required - ({f"official/c{MST}.lua"}
                                       if not mst_used else set()) <= (
                                           env.engine.probe.loaded_script_sha256.keys())
                    checked = True
            if action is None:
                action = (random_agent.select_action(obs, actions) if checked else
                          next((a for a in actions if a.kind in (
                              "select_card", "place", "pass", "end_phase")), actions[0]))
            obs = env.step(action)
        assert checked, (f"Call/Necrovalley line stalled: graceful={graceful}, "
                         f"discarded={discarded}, set={call_set}, valley={valley_active}, "
                         f"Call={call_used}/{call_targeted}, MST={mst_used}/{mst_targeted}")
        assert env.is_terminal(), "Call/Necrovalley continuation did not finish"
        trajectory = env.trajectory()
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
        audit_trajectory_visibility(trajectory)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_call_chained_to_heavy_storm_under_necrovalley_is_still_negated(tmp_path):
    """Recreate the March 2005 Call/Heavy/Necrovalley chain discussion."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = {f"official/c{code}.lua" for code in (GRACEFUL, CALL, HEAVY_STORM)}
    required.add(f"pre-errata/c{NECROVALLEY}.lua")
    if any(not (root / "scripts" / script).is_file() for script in required):
        pytest.skip("required card scripts not installed")
    owner = _deck(tmp_path / "call.ydk", (
        GRACEFUL, CALL, MST, *VANILLA_DECK[3:]))
    opponent = _deck(tmp_path / "valley_heavy.ydk", (
        NECROVALLEY, *VANILLA_DECK[1:4], HEAVY_STORM, *VANILLA_DECK[5:]))

    with GoatEnvironment(owner, opponent, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = call_set = valley_active = heavy_used = False
        call_chained = call_targeted = checked = False
        random_agent = RandomAgent(402)
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                elif not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {MYSTICAL_ELF, MAD_DOG}), None)
                    discarded |= action is not None
                elif discarded and not call_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL), None)
                    call_set |= action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1:
                if not valley_active:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NECROVALLEY), None)
                    valley_active |= action is not None
                elif not heavy_used and not obs.chain:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == HEAVY_STORM), None)
                    heavy_used |= action is not None
            if (not checked and heavy_used and obs.acting_player == 0
                    and [link.card_code for link in obs.chain] == [HEAVY_STORM]
                    and not call_chained):
                assert any(c.code == NECROVALLEY and c.position == "faceup"
                           for c in obs.field)
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == CALL), None)
                call_chained |= action is not None
            if call_chained and not call_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == MYSTICAL_ELF
                               and a.parameters.get("location") == 16), None)
                call_targeted |= action is not None
            if call_targeted and not obs.chain and not checked:
                assert MYSTICAL_ELF in {c.code for c in obs.graveyards[0]}
                assert CALL in {c.code for c in obs.graveyards[0]}
                assert {NECROVALLEY, HEAVY_STORM} <= {c.code for c in obs.graveyards[1]}
                assert not any(c.zone == "monster" and c.controller == 0
                               for c in obs.field)
                assert required <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
            if action is None:
                action = (random_agent.select_action(obs, actions) if checked else
                          next((a for a in actions if a.kind in (
                              "select_card", "place", "pass", "end_phase")), actions[0]))
            obs = env.step(action)
        assert checked, (f"Call/Heavy/Necrovalley chain stalled: graceful={graceful}, "
                         f"discarded={discarded}, set={call_set}, valley={valley_active}, "
                         f"Heavy={heavy_used}, Call={call_chained}/{call_targeted}")
        assert env.is_terminal(), "Call/Heavy/Necrovalley continuation did not finish"
        trajectory = env.trajectory()
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
        audit_trajectory_visibility(trajectory)
