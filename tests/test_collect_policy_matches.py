"""Batch collection keeps a deterministic schedule and refuses overwrites."""

import json
import sys
from pathlib import Path

import pytest

from scripts import collect_policy_matches as collector


def test_schedule_pairs_each_seed_with_both_policy_seats(tmp_path):
    pairs = [(Path("a.ydk"), Path("b.ydk")),
             (Path("c.ydk"), Path("d.ydk"))]
    tasks = collector.schedule_matches(pairs, 52, 2, tmp_path)
    assert [(task.matchup_index, task.seed, task.policy_seat)
            for task in tasks] == [
                (0, 52, 0), (0, 52, 1), (0, 53, 0), (0, 53, 1),
                (1, 52, 0), (1, 52, 1), (1, 53, 0), (1, 53, 1),
            ]
    assert len({task.output for task in tasks}) == 8
    with pytest.raises(ValueError, match="positive seeds"):
        collector.schedule_matches(pairs, 52, 0, tmp_path)


def test_batch_manifest_preserves_schedule_and_existing_files(tmp_path, monkeypatch, capsys):
    checkpoint = tmp_path / "policy.pt"
    checkpoint.write_bytes(b"checkpoint")
    decks = [tmp_path / f"deck_{index}.ydk" for index in range(4)]
    for deck in decks:
        deck.write_text("#main\n123\n", encoding="utf-8")
    output = tmp_path / "recordings"

    def fake_record(task, **kwargs):
        assert kwargs["checkpoint_sha256"] == collector.sha256_file(checkpoint)
        task.output.write_text("recorded", encoding="utf-8")
        return {"matchup_index": task.matchup_index, "seed": task.seed,
                "policy_seat": task.policy_seat,
                "trajectory": str(task.output), "verified_decisions": 7}

    monkeypatch.setattr(collector, "record_task", fake_record)
    argv = ["collect_policy_matches.py", str(checkpoint),
            "--matchup", str(decks[0]), str(decks[1]),
            "--matchup", str(decks[2]), str(decks[3]),
            "--seed", "52", "--seeds", "2", "--workers", "2",
            "--output-dir", str(output)]
    monkeypatch.setattr(sys, "argv", argv)
    collector.main()
    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads((output / "manifest.json").read_text())
    assert summary["verified_games"] == manifest["verified_games"] == 8
    assert manifest["policy_inference"] == "greedy"
    assert summary["verified_decisions"] == manifest["verified_decisions"] == 56
    assert [(game["matchup_index"], game["seed"], game["policy_seat"])
            for game in manifest["games"]] == [
                (task.matchup_index, task.seed, task.policy_seat)
                for task in collector.schedule_matches(
                    [(decks[0], decks[1]), (decks[2], decks[3])], 52, 2, output)]
    with pytest.raises(SystemExit):
        collector.main()
    assert (output / "manifest.json").exists()


def test_batch_manifest_records_guard_version(tmp_path, monkeypatch, capsys):
    checkpoint = tmp_path / "policy.pt"
    checkpoint.write_bytes(b"checkpoint")
    deck1 = tmp_path / "a.ydk"
    deck2 = tmp_path / "b.ydk"
    for deck in (deck1, deck2):
        deck.write_text("#main\n123\n")
    seen = []

    def fake_record(task, **kwargs):
        seen.append((kwargs["own_loss_guard"], kwargs["own_loss_guard_version"]))
        task.output.write_text("recorded")
        return {"verified_decisions": 1}

    monkeypatch.setattr(collector, "record_task", fake_record)
    monkeypatch.setattr(sys, "argv", ["collect_policy_matches.py", str(checkpoint),
                                     "--matchup", str(deck1), str(deck2),
                                     "--seed", "52", "--seeds", "1",
                                     "--own-loss-guard", "--own-loss-guard-version", "3",
                                     "--output-dir", str(tmp_path / "guarded")])
    collector.main()
    assert seen == [(True, 3), (True, 3)]
    assert json.loads((tmp_path / "guarded/manifest.json").read_text())[
        "policy_inference"] == "greedy_own_loss_guard_v3"
    assert json.loads(capsys.readouterr().out)["verified_games"] == 2
