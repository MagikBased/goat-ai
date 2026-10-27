"""Period Brionac effect behavior in the isolated MR1 protocol."""

import hashlib
import os
from pathlib import Path

import pytest

from goat_ai.engine.mr1_synchro_probe import BRIONAC, Mr1SynchroProbeEngine
from goat_ai.engine.ocgcore_probe import UPSTREAM_BRIONAC_SHA256
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from scripts.record_mr1_brionac_probe import DARK_BLADE, record_probe


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_brionac_can_activate_twice_and_target_either_field(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    source = native_root / f"scripts/official/c{BRIONAC}.lua"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == UPSTREAM_BRIONAC_SHA256
    trajectory, activations, targets, loaded_script = record_probe(native_root)
    assert activations == (55, 63)
    assert targets == ((1, DARK_BLADE, 58), (0, BRIONAC, 65))
    assert loaded_script == "b895a1bd35aa7260e0604602961ba5b6b4880f24ce0eff19c9c4bb64300c5198"
    assert len(trajectory.decisions) == 1111
    assert trajectory.ruleset == "mr1-synchro-protocol"
    # The first resolution removes the opposing target; the second returns
    # Brionac to its owner's Extra Deck rather than leaving it on the field.
    first = trajectory.decisions[60].observation
    second = trajectory.decisions[67].observation
    assert {card.code for card in first.field} == {BRIONAC}
    assert not second.field
    assert second.extra_deck_counts[0] == 1
    path = tmp_path / "mr1_brionac.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(native_root)) == 1111
    assert audit_trajectory_visibility(loaded)["decisions"] == 1111
