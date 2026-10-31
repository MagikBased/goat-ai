"""Recorded teacher provenance stays seat-specific with a named opponent."""

import json
import os
import sys
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.collect_heuristic_demos import main


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tactical_teacher_against_combat_baseline_records_verified_seats(
    tmp_path, monkeypatch, capsys,
):
    root = Path(__file__).resolve().parents[1]
    native = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    output = tmp_path / "demos"
    monkeypatch.setattr(sys, "argv", [
        "collect_heuristic_demos.py", "--native-root", str(native),
        "--engine", "experimental", "--teacher", "tactical",
        "--opponent", "combat_heuristic",
        "--deck-a", str(root / "examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk"),
        "--deck-b", str(root / "examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk"),
        "--seed", "2500", "--seeds", "1", "--max-decisions", "3000",
        "--output-dir", str(output), "--verify-replays",
    ])
    main()
    report = json.loads(capsys.readouterr().out)
    assert json.loads((output / ".manifest.json").read_text()) == report
    assert report["verify_replays"] is True
    assert len(report["games"]) == 2
    for seat, game in enumerate(report["games"]):
        replay = read_trajectory(game["path"])
        assert replay.schema_version == 29
        assert replay.source == "tactical"
        assert replay.skill_metadata == {
            "demonstrator_seat": seat,
            "teacher": "TacticalHeuristicAgent", "teacher_version": 14,
            "opponent": "CombatHeuristicAgent", "opponent_version": 3,
        }
        assert game["teacher_decisions"] == sum(
            record.observation.acting_player == seat for record in replay.decisions)
        assert game["replay_verified_decisions"] == game["decisions"]
        assert game["visibility_audit"]["decisions"] == game["decisions"]
        assert game["trajectory_sha256"] == sha256_file(Path(game["path"]))
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(native)) == len(
            replay.decisions)
