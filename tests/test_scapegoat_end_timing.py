"""A replay-verified Scapegoat probe crosses both End Phase turn owners."""

import os
from pathlib import Path

import pytest

from goat_ai.replay import read_trajectory
from scripts.generate_scapegoat_timing_probe import run_probe, timing_records

SCAPEGOAT = 504700123


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_scapegoat_end_phase_choices_respect_turn_owner(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{SCAPEGOAT}.lua").is_file():
        pytest.skip("GOAT Scapegoat script not installed")
    path = tmp_path / "scapegoat_end_timing.json"
    trajectory = run_probe(root, path)
    assert len(trajectory.decisions) == 711
    assert trajectory.source == "scripted_timing_probe"
    assert [
        (record.observation.turn, record.observation.turn_player,
         record.observation.acting_player, record.selected_action.kind)
        for _, record in timing_records(read_trajectory(path))
    ] == [(3, 0, 1, "pass"), (4, 1, 1, "pass"), (5, 0, 1, "chain")]
