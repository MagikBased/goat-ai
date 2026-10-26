"""A replay-verified Scapegoat probe crosses both End Phase turn owners."""

import hashlib
import os
import sys
from pathlib import Path

import pytest

from goat_ai.replay import read_decision_annotations, read_trajectory
from scripts.generate_scapegoat_timing_probe import (
    curriculum_records,
    run_probe,
    timing_records,
)

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
    labels, selected = read_decision_annotations(
        path.with_suffix(".labels.json"), hashlib.sha256(path.read_bytes()).hexdigest(),
        read_trajectory(path))
    assert labels.authorization == "scripted_scenario"
    assert labels.choices == ((20, 1), (28, 1), (35, 0))
    assert [record.selected_action.kind for record in selected] == ["pass", "pass", "chain"]
    curriculum, selected = read_decision_annotations(
        path.with_suffix(".curriculum.labels.json"),
        hashlib.sha256(path.read_bytes()).hexdigest(), read_trajectory(path))
    assert len(curriculum.choices) == len(tuple(curriculum_records(trajectory))) == 19
    assert any(record.selected_action.kind == "set_spell_trap" for record in selected)
    assert selected[-1].selected_action.kind == "chain"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_trainer_rejects_unannotated_scripted_replay(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    from scripts.train_behavioral_clone import main as train_main

    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    path = tmp_path / "scapegoat_end_timing.json"
    run_probe(root, path)
    monkeypatch.setattr(sys, "argv", ["train_behavioral_clone.py", str(path),
                                     "--native-root", str(root), "--engine", "experimental",
                                     "--feature-version", "19", "--output",
                                     str(tmp_path / "bad.pt")])
    with pytest.raises(ValueError, match="scripted replay requires explicit annotations"):
        train_main()


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_published_deck_timing_probe_records_early_passes(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = Path(__file__).resolve().parents[1] / "examples/decks"
    path = tmp_path / "cas_timing.json"
    trajectory = run_probe(
        root, path, seed=2601,
        deck_a=decks / "gravekeeper_daryl_gessler_indianapolis_2005.ydk",
        deck_b=decks / "flip_control_cas_stomphorst_indianapolis_2005.ydk")
    assert len(trajectory.decisions) == 1119
    labels, records = read_decision_annotations(
        path.with_suffix(".curriculum.labels.json"),
        hashlib.sha256(path.read_bytes()).hexdigest(), read_trajectory(path))
    assert len(labels.choices) == 19
    assert [record.selected_action.kind for record in records].count("chain") == 1
    assert records[-1].observation.phase == "end"
    assert records[-1].observation.turn_player == 0
