"""The coverage suite must include each distinct legal Main and Fusion ID."""

import os
from pathlib import Path

import pytest

from scripts.probe_whitelist_coverage import canonical_pool, coverage_decks


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native card databases not installed")
def test_coverage_decks_are_deterministic_legal_and_complete():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    main, fusion = canonical_pool(root)
    decks = coverage_decks(root, 120000)
    assert decks == coverage_decks(root, 120000)
    assert decks != coverage_decks(root, 120001)
    assert len(decks) == (len(main) + 39) // 40
    assert all(len(deck.main) == 40 and len(deck.extra) <= 15 for deck in decks)
    assert {code for deck in decks for code in deck.main} == set(main)
    assert {code for deck in decks for code in deck.extra} == set(fusion)
