"""MR1 Synchro Summon response: Bottomless is offered after Junk Warrior appears."""

import hashlib
import os
from pathlib import Path

import pytest

from goat_ai.engine.mr1_synchro_probe import (
    BOTTOMLESS_TRAP_HOLE, JUNK_WARRIOR, Mr1SynchroProbeEngine,
)
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from scripts.record_mr1_bottomless_synchro_probe import record_probe


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_mr1_bottomless_after_synchro_is_hidden_until_activated(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    results = {}
    for chain in (True, False):
        trajectory, offer, resolved, loaded_script = record_probe(
            root, chain_bottomless=chain)
        results[chain] = trajectory
        assert offer == 36
        assert resolved == (39 if chain else 38)
        assert len(trajectory.decisions) == (1267 if chain else 1238)
        assert trajectory.ruleset == "mr1-synchro-protocol"
        assert loaded_script == hashlib.sha256(
            (root / f"scripts/official/c{BOTTOMLESS_TRAP_HOLE}.lua").read_bytes()
        ).hexdigest()
        offered = trajectory.decisions[offer]
        assert offered.observation.acting_player == 1
        assert any(card.code == JUNK_WARRIOR and card.attack == 2300
                   for card in offered.observation.field)
        assert any(action.kind == "chain"
                   and action.parameters.get("code") == BOTTOMLESS_TRAP_HOLE
                   for action in offered.legal_actions)
        assert offered.selected_action.kind == ("chain" if chain else "pass")
        hidden = next(record.observation for record in trajectory.decisions[:offer]
                      if record.observation.acting_player == 0
                      and any(card.controller == 1 and card.zone == "spell_trap"
                              for card in record.observation.field))
        assert all(card.code is None for card in hidden.field
                   if card.controller == 1 and card.zone == "spell_trap")
        state = trajectory.decisions[resolved].observation
        if chain:
            assert any(card.code == JUNK_WARRIOR for card in state.banished[0])
            assert any(card.code == BOTTOMLESS_TRAP_HOLE
                       for card in state.graveyards[1])
        else:
            assert any(card.code == JUNK_WARRIOR for card in state.field)
            assert not state.banished[0]
        path = tmp_path / f"bottomless_{chain}.json"
        write_trajectory(path, trajectory)
        loaded = read_trajectory(path)
        assert loaded == trajectory
        assert verify_trajectory(loaded, Mr1SynchroProbeEngine(root)) == len(
            trajectory.decisions)
        assert audit_trajectory_visibility(loaded)["decisions"] == len(
            trajectory.decisions)
    assert results[True].decisions[:36] == results[False].decisions[:36]
