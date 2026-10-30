"""Book of Moon answers Bottomless after a successful MR1 Synchro Summon."""

import hashlib
import os
from pathlib import Path

import pytest

from goat_ai.engine.mr1_synchro_probe import (
    BOOK_OF_MOON,
    BOTTOMLESS_TRAP_HOLE,
    JUNK_WARRIOR,
    Mr1SynchroProbeEngine,
)
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from scripts.record_mr1_bottomless_synchro_probe import record_probe


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_book_chained_to_bottomless_preserves_synchro_and_hidden_view(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    branches = {}
    for chain_book in (True, False):
        trajectory, offer, resolved, _ = record_probe(
            root, chain_bottomless=True, book_response=chain_book)
        branches[chain_book] = trajectory
        assert trajectory.ruleset == "mr1-synchro-protocol"
        assert trajectory.asset_sha256["scripts/official/c14087893.lua"] == (
            hashlib.sha256((root / "scripts/official/c14087893.lua").read_bytes())
            .hexdigest())
        assert offer == 40
        assert resolved == (45 if chain_book else 43)
        bottomless = trajectory.decisions[offer]
        assert bottomless.selected_action.kind == "chain"
        assert bottomless.selected_action.parameters["code"] == BOTTOMLESS_TRAP_HOLE
        assert any(card.code == JUNK_WARRIOR for card in bottomless.observation.field)
        response = trajectory.decisions[offer + 1]
        assert response.observation.acting_player == 0
        assert any(action.kind == "chain"
                   and action.parameters.get("code") == BOOK_OF_MOON
                   for action in response.legal_actions)
        assert response.selected_action.kind == ("chain" if chain_book else "pass")
        assert any(card.controller == 0 and card.zone == "spell_trap"
                   and card.code is None for card in bottomless.observation.field)
        state = trajectory.decisions[resolved].observation
        assert any(card.code == BOTTOMLESS_TRAP_HOLE
                   for card in state.graveyards[1])
        if chain_book:
            target = trajectory.decisions[offer + 2].selected_action
            assert target.kind == "select_card"
            assert target.parameters["code"] == JUNK_WARRIOR
            assert any(card.code == JUNK_WARRIOR and card.position == "facedown"
                       for card in state.field)
            assert JUNK_WARRIOR not in {card.code for card in state.banished[0]}
            assert BOOK_OF_MOON in {card.code for card in state.graveyards[0]}
        else:
            assert JUNK_WARRIOR in {card.code for card in state.banished[0]}
            assert any(card.code == BOOK_OF_MOON and card.position == "facedown"
                       for card in state.field)
        path = tmp_path / f"mr1_bottomless_book_{chain_book}.json"
        write_trajectory(path, trajectory)
        restored = read_trajectory(path)
        assert restored == trajectory
        assert verify_trajectory(restored, Mr1SynchroProbeEngine(root)) == len(
            trajectory.decisions)
        assert audit_trajectory_visibility(restored)["decisions"] == len(
            trajectory.decisions)
    assert branches[True].decisions[:41] == branches[False].decisions[:41]
