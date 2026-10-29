"""The coverage suite must include each distinct legal Main and Fusion ID."""

import os
from pathlib import Path

import pytest

from goat_ai.actions import Action
from scripts.probe_whitelist_coverage import (
    FirstActivationProbeAgent,
    canonical_pool,
    coverage_decks,
)


def test_first_activation_probe_exercises_each_offered_card_once():
    actions = (
        Action("a", "activate", 0, {"code": 10}),
        Action("b", "chain", 0, {"code": 20}),
        Action("c", "pass", 0),
    )
    agent = FirstActivationProbeAgent(42)
    first = agent.select_action(None, actions)
    second = agent.select_action(None, actions)
    assert {first.parameters["code"], second.parameters["code"]} == {10, 20}
    assert agent.activated == {10, 20}
    assert agent.select_action(None, actions) in actions


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
