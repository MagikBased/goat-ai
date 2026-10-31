"""The fallback replay diagnostic verifies the recorded inference mode."""

import json
import os
import sys
from pathlib import Path

import pytest

from scripts.audit_tactical_fallback_replay import audit_replay
from scripts.record_policy_match import main as record_match


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_verified_fallback_replay_compares_parent_on_visible_states(
        tmp_path, monkeypatch, capsys):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve()
    project = Path(__file__).resolve().parents[1]
    checkpoint = project / ".cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt"
    if not checkpoint.is_file():
        pytest.skip("selected checkpoint not installed")
    trajectory = tmp_path / "fallback.json"
    monkeypatch.setattr(sys, "argv", [
        "record_policy_match.py", str(checkpoint),
        "--deck1", str(project / "examples/decks/zombie_jae_kim_charlotte_2005.ydk"),
        "--deck2", str(project / "examples/decks/warrior_mary_triatafilidi_new_jersey_2005.ydk"),
        "--native-root", str(root), "--seed", "204300", "--policy-seat", "0",
        "--opponent", "tactical", "--tactical-fallback-margin", "1.0",
        "--output", str(trajectory),
    ])
    record_match()
    recorded = json.loads(capsys.readouterr().out)
    report = audit_replay(trajectory, checkpoint, root, 1.0)
    assert report["verified_decisions"] == recorded["verified_decisions"]
    assert report["policy_decisions"] > report["changed_choices"] > 0
    assert report["changed_choices"] == len(report["decisions"])
    with pytest.raises(ValueError, match="not bound"):
        audit_replay(trajectory, checkpoint, root, 2.0)
