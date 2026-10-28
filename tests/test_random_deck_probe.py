"""Tournament-mix protocol probes use legal, reproducible sourced cards."""

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.evaluation.competitive_corpus import TOURNAMENT_MAIN_DECKS
from goat_ai.replay.fingerprint import sha256_file
from scripts.probe_random_decks import (
    METAMORPHOSIS,
    SCAPEGOAT,
    THOUSAND_EYES_RESTRICT,
    generate_deck,
    generate_tournament_mix,
    probe,
    probe_isolated,
)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_random_fusion_extra_decks_keep_main_seed_and_replay_verify(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    plain = generate_deck(native_root, 10700)
    expanded = generate_deck(native_root, 10700, include_random_extra=True)
    assert plain.main == expanded.main
    assert plain.extra == ()
    assert len(expanded.extra) == len(set(expanded.extra)) == 15
    assert expanded == generate_deck(native_root, 10700, include_random_extra=True)
    report = probe(native_root, tmp_path / "fusion", 10700, 1, 3000,
                   verify_replays=True, distinct_opponents=True,
                   random_extra=True)
    assert report["random_extra"] is True
    assert report["extra_seed_offset"] == 2_000_000
    assert len(read_ydk(report["games"][0]["deck"]).extra) == 15
    assert len(read_ydk(report["games"][0]["opponent_deck"]).extra) == 15
    assert report["games"][0]["terminal"]
    assert report["games"][0]["error"] is None
    assert report["games"][0]["replay_verified_decisions"] == report["games"][0]["decisions"]


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_fusion_stress_reaches_extra_deck_card_actions(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = generate_deck(native_root, 10753, include_random_extra=True,
                         fusion_stress=True)
    assert Counter(deck.main)[SCAPEGOAT] == 3
    assert Counter(deck.main)[METAMORPHOSIS] == 3
    assert THOUSAND_EYES_RESTRICT in deck.extra
    report = probe(native_root, tmp_path / "stress", 10753, 1, 3000,
                   verify_replays=True, distinct_opponents=True,
                   count_card_actions=True, random_extra=True,
                   fusion_stress=True)
    assert report["fusion_stress"] is True
    assert report["games"][0]["terminal"]
    assert report["games"][0]["error"] is None
    assert any(row["code"] == THOUSAND_EYES_RESTRICT
               and row["selected_decisions"] > 0
               for row in report["card_actions"])


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize(("seed", "source_code"),
                         [(10772, 93671934), (10786, 28566710)])
def test_fusion_stress_native_regressions(tmp_path, seed, source_code):
    """Morale Boost and Last Turn each exposed a native duel failure."""
    root = Path(__file__).resolve().parents[1]
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve()
    result = subprocess.run(
        [sys.executable, str(root / "scripts/probe_random_decks.py"),
         "--native-root", str(native_root), "--output", str(tmp_path),
         "--seed", str(seed), "--seeds", "1", "--max-decisions", "3000",
         "--random-extra", "--fusion-stress", "--distinct-opponents",
         "--verify-replays", "--count-card-actions"],
        cwd=root, env={**os.environ, "PYTHONPATH": f"{root / 'src'}{os.pathsep}{root}"},
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((tmp_path / "report.json").read_text())
    game = report["games"][0]
    assert game["seed"] == seed
    assert game["terminal"] and game["error"] is None
    assert game["replay_verified_decisions"] == game["decisions"]
    assert any(row["code"] == source_code and row["selected_decisions"] > 0
               for row in report["card_actions"])
    if seed == 10772:
        assert report["loaded_asset_sha256"]["scripts/official/c93671934.lua"] == (
            "3cda0dc2671fb47d6b2dcb212e7f99bff1bc5e142686e7c35b0c6ded7dc65c20")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tournament_mix_is_legal_and_replay_verifies(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = generate_tournament_mix(native_root, 18600)
    assert deck == generate_tournament_mix(native_root, 18600)
    assert len(deck.main) == 40
    source_root = Path(__file__).resolve().parents[1] / "examples/decks"
    source_codes = set().union(*(set(read_ydk(source_root / name).main)
                                 for name in TOURNAMENT_MAIN_DECKS))
    assert set(deck.main) <= source_codes
    limits = read_goat_whitelist(native_root / "banlist/GOAT.lflist.conf")
    assert all(count <= limits[code] for code, count in Counter(deck.main).items())
    validate_goat_deck(deck, limits, native_root / "database/cards.cdb",
                       native_root / "database/goat-entries.cdb",
                       native_root / "database/cards-unofficial.cdb")

    report = probe(native_root, tmp_path / "mixed", 18600, 1, 3000,
                   card_pool="tournament", verify_replays=True)
    assert report["card_pool"] == "tournament"
    assert report["replay_verification"] == {
        "verified_games": 1,
        "verified_decisions": report["games"][0]["decisions"],
    }
    assert report["visibility_audit"]["audited_games"] == 1
    assert report["visibility_audit"]["decisions"] == report["games"][0]["decisions"]
    assert report["games"][0]["terminal"]
    assert report["games"][0]["error"] is None


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_distinct_tournament_mixes_replay_verify(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    report = probe(native_root, tmp_path / "cross", 18650, 1, 3000,
                   card_pool="tournament", verify_replays=True,
                   distinct_opponents=True, count_card_actions=True,
                   repeat_seeds=True)
    game = report["games"][0]
    assert report["distinct_opponents"] is True
    assert report["opponent_seed_offset"] == 1_000_000
    assert game["deck_sha256"] != game["opponent_deck_sha256"]
    assert Path(game["deck"]).is_file() and Path(game["opponent_deck"]).is_file()
    assert game["terminal"] and game["error"] is None
    assert game["replay_verified_decisions"] == game["decisions"]
    assert game["deterministic_repeat"] is True
    assert report["determinism"] == {
        "repeated_games": 1, "identical_decisions": game["decisions"]}
    assert report["visibility_audit"]["audited_games"] == 1
    assert report["visibility_audit"]["decisions"] == game["decisions"]
    assert report["card_actions"]
    assert all(row["selected_decisions"] <= row["offered_decisions"]
               for row in report["card_actions"])
    assert all(row["selected_decisions"] > 0
               for row in report["chain_responses"])


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_probe_reports_initialization_failure_with_replay_verification(tmp_path, monkeypatch):
    def fail_engine(_root):
        raise OSError("native library unavailable")

    monkeypatch.setattr("scripts.probe_random_decks.ExperimentalOcgcoreEngine", fail_engine)
    report = probe(Path(os.environ["GOAT_AI_NATIVE_ROOT"]), tmp_path / "failed",
                   18600, 1, 3000, card_pool="tournament", verify_replays=True)
    game = report["games"][0]
    assert game["error"] == "OSError: native library unavailable"
    assert game["terminal"] is False
    assert game["replay_verified_decisions"] is None


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_isolated_probe_keeps_later_verified_game_after_worker_crash(tmp_path, monkeypatch):
    original_run = subprocess.run

    def crash_first(command, **kwargs):
        if command[command.index("--seed") + 1] == "18650":
            directory = Path(command[command.index("--output") + 1])
            directory.mkdir(parents=True)
            (directory / "seed_18650.ydk").write_text("generated first deck\n")
            (directory / "seed_18650_opponent.ydk").write_text("generated opponent\n")
            return subprocess.CompletedProcess(command, -11, "", "")
        return original_run(command, **kwargs)

    monkeypatch.setattr("scripts.probe_random_decks.subprocess.run", crash_first)
    report = probe_isolated(Path(os.environ["GOAT_AI_NATIVE_ROOT"]),
                            tmp_path / "isolated", 18650, 2, 3000,
                            card_pool="tournament", verify_replays=True,
                            distinct_opponents=True, count_card_actions=True)
    failed, passed = report["games"]
    assert failed["error"] == "isolated worker exited -11"
    assert failed["replay_verified_decisions"] is None
    assert failed["deck_sha256"] == sha256_file(Path(failed["deck"]))
    assert failed["opponent_deck_sha256"] == sha256_file(Path(failed["opponent_deck"]))
    assert passed["seed"] == 18651 and passed["terminal"]
    assert passed["replay_verified_decisions"] == passed["decisions"]
    assert report["replay_verification"] == {
        "verified_games": 1, "verified_decisions": passed["decisions"]}
    assert report["visibility_audit"]["decisions"] == passed["decisions"]
    assert report["card_actions"]
    assert json.loads((tmp_path / "isolated" / "report.json").read_text()) == report
