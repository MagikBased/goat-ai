"""The training-label audit distinguishes legal zero, one, and two-card searches."""

from dataclasses import replace

from goat_ai.actions import Action
from goat_ai.evaluation.thunder_search_audit import (
    THUNDER_DRAGON,
    thunder_search_choice,
)
from goat_ai.observations import ChainLinkView, Observation
from goat_ai.replay.trajectory import DecisionRecord


def test_thunder_search_audit_counts_staged_and_bulk_choices():
    view = Observation(viewer=0, acting_player=0, turn=1, phase="main1",
                       life_points=(8000, 8000), hand=(), field=(),
                       graveyards=((), ()), banished=((), ()),
                       opponent_hand_count=5, deck_counts=(35, 35),
                       extra_deck_counts=(0, 0),
                       chain=(ChainLinkView(1, THUNDER_DRAGON, 0, 2, 0),))
    copy = Action("copy", "select_card", 0,
                  {"code": THUNDER_DRAGON, "location": 1, "controller": 0})
    zero = Action("zero", "select_cards", 0, {})
    two = Action("two", "select_cards", 0,
                 {"cards": [{"code": THUNDER_DRAGON, "location": 1,
                             "controller": 0}] * 2})
    legal = (copy, zero, two)
    assert thunder_search_choice(DecisionRecord(view, legal, copy), 0) == "take_one"
    assert thunder_search_choice(DecisionRecord(view, legal, zero), 0) == "take_zero"
    assert thunder_search_choice(DecisionRecord(view, legal, two), 0) == "take_2"
    assert thunder_search_choice(DecisionRecord(replace(view, chain=()), legal, zero),
                                 0) is None
    assert thunder_search_choice(DecisionRecord(view, legal, zero), 1) is None
