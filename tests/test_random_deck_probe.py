"""Tournament-mix protocol probes use legal, reproducible sourced cards."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.evaluation.competitive_corpus import TOURNAMENT_MAIN_DECKS
from scripts.probe_random_decks import generate_tournament_mix, probe


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
    assert report["games"][0]["terminal"]
    assert report["games"][0]["error"] is None


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_distinct_tournament_mixes_replay_verify(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    report = probe(native_root, tmp_path / "cross", 18650, 1, 3000,
                   card_pool="tournament", verify_replays=True,
                   distinct_opponents=True, count_card_actions=True)
    game = report["games"][0]
    assert report["distinct_opponents"] is True
    assert report["opponent_seed_offset"] == 1_000_000
    assert game["deck_sha256"] != game["opponent_deck_sha256"]
    assert Path(game["deck"]).is_file() and Path(game["opponent_deck"]).is_file()
    assert game["terminal"] and game["error"] is None
    assert game["replay_verified_decisions"] == game["decisions"]
    assert report["card_actions"]
    assert all(row["selected_decisions"] <= row["offered_decisions"]
               for row in report["card_actions"])
    assert all(row["selected_decisions"] > 0
               for row in report["chain_responses"])
