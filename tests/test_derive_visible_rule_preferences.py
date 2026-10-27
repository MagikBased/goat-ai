"""Automated visible-rule labels must refer to alternatives actually offered."""

from types import SimpleNamespace

import pytest

from goat_ai.actions import Action
from goat_ai.evaluation.replay_review import ReviewCandidate
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord, Trajectory
from goat_ai.replay.preferences import ReviewedPreference
from scripts import derive_visible_rule_preferences as rules


derive = rules.derive


def test_derive_self_target_preference_uses_only_enemy_legal_choices():
    view = Observation(
        viewer=0, acting_player=0, turn=2, phase="main1",
        life_points=(8000, 8000), hand=(), field=(), graveyards=((), ()),
        banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    own = Action("own", "select_card", 0, {"location": 4, "controller": 0})
    enemy_a = Action("enemy-a", "select_card", 0,
                     {"location": 4, "controller": 1})
    enemy_b = Action("enemy-b", "select_card", 0,
                     {"location": 4, "controller": 1})
    hand = Action("hand", "select_card", 0, {"location": 2, "controller": 1})
    record = DecisionRecord(view, (own, enemy_a, enemy_b, hand), own)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1)
    candidate = ReviewCandidate(0, "chaos_sorcerer_targets_itself_with_enemy_option",
                                2, "main1", 0, {"source_card_code": 9596126})
    preferences, counts = derive(replay, (candidate,))
    assert preferences == [{"decision_index": 0,
                            "preferred_action_indices": [1, 2],
                            "disfavored_action_indices": [0]}]
    assert counts == {"chaos_sorcerer_targets_itself_with_enemy_option": 1}


def test_derive_skips_review_flags_without_a_safe_alternative():
    view = Observation(
        viewer=0, acting_player=0, turn=2, phase="main1",
        life_points=(8000, 8000), hand=(), field=(), graveyards=((), ()),
        banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    own = Action("own", "select_card", 0, {"location": 4, "controller": 0})
    record = DecisionRecord(view, (own,), own)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1)
    candidate = ReviewCandidate(0, "chaos_sorcerer_targets_itself_with_enemy_option",
                                2, "main1", 0, {})
    assert derive(replay, (candidate,)) == ([], {})


def test_automated_labels_must_match_recomputed_visible_rule(monkeypatch):
    view = Observation(
        viewer=0, acting_player=0, turn=2, phase="main1",
        life_points=(8000, 8000), hand=(), field=(), graveyards=((), ()),
        banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    own = Action("own", "select_card", 0, {"location": 4, "controller": 0})
    enemy = Action("enemy", "select_card", 0, {"location": 4, "controller": 1})
    hand = Action("hand", "select_card", 0, {"location": 2, "controller": 1})
    record = DecisionRecord(view, (own, enemy, hand), own)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1)
    candidate = ReviewCandidate(0, "chaos_sorcerer_targets_itself_with_enemy_option",
                                2, "main1", 0, {})
    monkeypatch.setattr(rules, "review_candidates", lambda *args, **kwargs: (candidate,))
    valid = SimpleNamespace(preferences=(ReviewedPreference(0, (1,), (0,)),))
    rules.validate_automated_preferences(replay, valid, {})
    edited = SimpleNamespace(preferences=(ReviewedPreference(0, (2,), (0,)),))
    with pytest.raises(ValueError, match="do not match visible_audit_v1"):
        rules.validate_automated_preferences(replay, edited, {})
