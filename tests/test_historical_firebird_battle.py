"""A pinned GOAT Firebird battle callback must not crash native duels."""

import os
from pathlib import Path

import pytest

from scripts.probe_random_decks import probe


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("seed", (10030, 10062, 10122))
def test_firebird_battle_callback_completes_seeded_duel(tmp_path, seed):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    report = probe(root, tmp_path / str(seed), seed, 1, 3000,
                   distinct_opponents=True, verify_replays=True)
    game, = report["games"]
    assert game["error"] is None
    assert game["terminal"]
    assert game["replay_verified_decisions"] == game["decisions"]
    assert "scripts/goat/c504700151.lua" in report["loaded_asset_sha256"]
