"""Tournament-mix protocol probes use legal, reproducible sourced cards."""

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.decks import Decklist, read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.competitive_corpus import (
    INDIANAPOLIS_2005_MAIN_DECKS,
    TOURNAMENT_MAIN_DECKS,
)
from goat_ai.replay.fingerprint import sha256_file
from scripts.probe_random_decks import (
    METAMORPHOSIS,
    SCAPEGOAT,
    THOUSAND_EYES_RESTRICT,
    generate_deck,
    generate_tournament_mix,
    probe,
    probe_isolated,
    write_deck,
)


def test_isolated_probe_rejects_incompatible_options_before_spawning(tmp_path, monkeypatch):
    def unexpected_worker(*_args, **_kwargs):
        pytest.fail("invalid probe options started an isolated worker")

    monkeypatch.setattr("scripts.probe_random_decks.subprocess.run", unexpected_worker)
    with pytest.raises(ValueError, match="random Extra Decks require"):
        probe_isolated(tmp_path, tmp_path / "output", 1, 2, 500,
                       card_pool="indianapolis-2005", random_extra=True)
    assert not (tmp_path / "output").exists()


def test_isolated_probe_reports_worker_error_detail(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.probe_random_decks.subprocess.run",
                        lambda command, **_kwargs: subprocess.CompletedProcess(
                            command, 1, "", "Traceback\nValueError: unsupported native prompt\n"))
    report = probe_isolated(tmp_path, tmp_path / "output", 1, 1, 500)
    assert report["games"][0]["error"] == (
        "isolated worker exited 1: ValueError: unsupported native prompt")


def test_probe_cli_rejects_incompatible_options_without_writing_report(tmp_path):
    output = tmp_path / "bad_sweep"
    script = Path(__file__).resolve().parents[1] / "scripts/probe_random_decks.py"
    result = subprocess.run([
        sys.executable, str(script), "--output", str(output),
        "--card-pool", "indianapolis-2005", "--random-extra",
        "--isolate-games", "--seeds", "32",
    ], capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "random Extra Decks require the whitelist card pool" in result.stderr
    assert not output.exists()


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
def test_sixty_card_repeated_copy_decks_complete_and_reproduce(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    plain = generate_deck(native_root, 176100)
    large = generate_deck(native_root, 176100, include_random_extra=True,
                          main_size=60)
    assert large.main[:40] == plain.main
    assert len(large.main) == 60
    assert len(set(large.main)) < 60
    assert large == generate_deck(native_root, 176100, include_random_extra=True,
                                  main_size=60)
    limits = read_goat_whitelist(native_root / "banlist/GOAT.lflist.conf")
    assert all(count <= limits[code] for code, count in Counter(large.main).items())
    report = probe(native_root, tmp_path / "large", 176100, 1, 3000,
                   verify_replays=True, distinct_opponents=True,
                   repeat_seeds=True, random_extra=True, main_size=60)
    game = report["games"][0]
    assert report["main_size"] == 60
    assert report["repeat_copy_seed_offset"] == 3_000_000
    assert len(read_ydk(game["opponent_deck"]).main) == 60
    assert game["terminal"] and game["error"] is None
    assert game["replay_verified_decisions"] == game["decisions"]
    assert game["deterministic_repeat"] is True
    assert report["visibility_audit"]["decisions"] == game["decisions"]


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sixty_card_duplicate_deck_hides_changed_opening_card(tmp_path):
    """Replacing one private opening card must not alter the other seat's menu."""
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    original = generate_deck(native_root, 176100, include_random_extra=True,
                             main_size=60)
    changed = list(original.main)
    changed[changed.index(5405694)] = 15025844
    decks = (original, Decklist(tuple(changed), original.extra))
    snapshots = []
    private_hands = []
    for index, deck in enumerate(decks):
        path = tmp_path / f"opponent_{index}.ydk"
        write_deck(path, deck)
        with GoatEnvironment("examples/decks/nobleman_probe.ydk", str(path), 52,
                             ExperimentalOcgcoreEngine(native_root)) as env:
            observation = env.reset()
            assert observation.viewer == observation.acting_player == 0
            assert observation.opponent_hand_count == 5
            assert observation.deck_counts[1] == 55
            snapshots.append((observation, env.legal_actions()))
            private_hands.append(tuple(card.code for card in
                                       env.engine.probe.observation(1).hand))
    assert private_hands[0] != private_hands[1]
    assert 5405694 in private_hands[0]
    assert 15025844 in private_hands[1]
    assert snapshots[0] == snapshots[1]


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
def test_2005_indianapolis_mix_is_legal_and_visibility_audited(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = generate_tournament_mix(
        native_root, 23100, source_names=INDIANAPOLIS_2005_MAIN_DECKS)
    assert deck == generate_tournament_mix(
        native_root, 23100, source_names=INDIANAPOLIS_2005_MAIN_DECKS)
    source_root = Path(__file__).resolve().parents[1] / "examples/decks"
    source_codes = set().union(*(set(read_ydk(source_root / name).main)
                                 for name in INDIANAPOLIS_2005_MAIN_DECKS))
    assert len(deck.main) == 40 and set(deck.main) <= source_codes
    limits = read_goat_whitelist(native_root / "banlist/GOAT.lflist.conf")
    validate_goat_deck(deck, limits, native_root / "database/cards.cdb",
                       native_root / "database/goat-entries.cdb",
                       native_root / "database/cards-unofficial.cdb")

    report = probe(native_root, tmp_path / "indianapolis", 23100, 1, 3000,
                   card_pool="indianapolis-2005", verify_replays=True,
                   distinct_opponents=True)
    game = report["games"][0]
    assert game["terminal"] and game["error"] is None
    assert game["replay_verified_decisions"] == game["decisions"]
    assert report["visibility_audit"]["decisions"] == game["decisions"]
    assert report["source_deck_sha256"] == {
        name: sha256_file(source_root / name)
        for name in INDIANAPOLIS_2005_MAIN_DECKS}


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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tactical_tournament_probe_is_reproducible_in_isolated_mode(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    options = {"card_pool": "tournament", "verify_replays": True,
               "distinct_opponents": True, "repeat_seeds": True,
               "agent_name": "tactical"}
    direct = probe(root, tmp_path / "direct", 18650, 1, 3000, **options)
    isolated = probe_isolated(root, tmp_path / "isolated", 18650, 1, 3000, **options)
    for report in (direct, isolated):
        assert report["agent"] == "tactical"
        assert report["games"][0]["terminal"] and report["games"][0]["error"] is None
        assert report["games"][0]["deterministic_repeat"] is True
        assert report["replay_verification"]["verified_decisions"] == (
            report["games"][0]["decisions"])
        assert report["visibility_audit"]["decisions"] == report["games"][0]["decisions"]
    assert direct["games"][0]["decisions"] == isolated["games"][0]["decisions"]
    assert direct["games"][0]["winner"] == isolated["games"][0]["winner"]
    assert direct["games"][0]["deck_sha256"] == isolated["games"][0]["deck_sha256"]
    child = json.loads(Path(isolated["worker_reports"][0]).read_text())
    assert child["agent"] == "tactical" and child["agent_version"] == 14
