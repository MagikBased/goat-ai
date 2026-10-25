"""Legal choices must expose only identities the acting player knows."""

from dataclasses import replace

import pytest

from goat_ai.actions import Action
from goat_ai.evaluation.visibility import (
    VisibilityViolation,
    audit_decision_visibility,
    audit_trajectory_visibility,
)
from goat_ai.observations import CardView, KnownCardView, Observation
from goat_ai.replay import DecisionRecord, Trajectory


def _observation():
    return Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(CardView(0, "hand", "hidden", 123),),
        field=(CardView(1, "monster", "facedown", None, 2),
               CardView(1, "spell_trap", "faceup", 789, 1),
               CardView(1, "spell_trap", "facedown", None, 3)),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=2,
        deck_counts=(30, 30), extra_deck_counts=(0, 0),
        known_opponent_field_cards=(KnownCardView(1, "monster", 2, 456),),
        known_opponent_hand_cards=(321,),
    )


def _record(observation, parameters, kind="select_card"):
    action = Action("0", kind, observation.acting_player, parameters)
    return DecisionRecord(observation, (action,), action)


def test_audit_accepts_hidden_slots_and_addressed_hand_choices():
    observation = _observation()
    decisions = (
        _record(observation, {"controller": 1, "location": 4, "sequence": 2}),
        _record(observation, {"controller": 1, "location": 8, "sequence": 3}),
        _record(observation, {"controller": 1, "location": 8,
                              "sequence": 1, "code": 789}),
        _record(observation, {"controller": 1, "location": 2, "code": 321}),
    )
    trajectory = Trajectory("goat", ("one", "two"), 52, decisions, 0)
    assert audit_trajectory_visibility(trajectory) == {
        "decisions": 4, "opponent_field_choices": 3,
        "hidden_field_choices": 2, "opponent_hand_choices": 1,
    }


@pytest.mark.parametrize("parameters,reason", [
    ({"controller": 1, "location": 4, "sequence": 2, "code": 456},
     "face-down"),
    ({"controller": 1, "location": 8, "sequence": 3, "attack": 1900},
     "face-down"),
    ({"controller": 1, "location": 8, "sequence": 1, "code": 123},
     "disagrees"),
    ({"controller": 1, "location": 2, "sequence": 0, "code": 321},
     "native slot"),
    ({"controller": 1, "location": 2, "code": 654},
     "unknown identity"),
])
def test_audit_rejects_choice_identity_leaks(parameters, reason):
    with pytest.raises(VisibilityViolation, match=reason):
        audit_decision_visibility(_record(_observation(), parameters))


def test_audit_checks_multi_card_choices_and_decision_viewer():
    observation = _observation()
    multi = _record(observation, {"cards": [
        {"controller": 1, "location": 4, "sequence": 2, "code": 456},
    ]}, "select_cards")
    with pytest.raises(VisibilityViolation, match="face-down"):
        audit_decision_visibility(multi)
    staged = _record(observation, {"controller": 0, "location": 32, "code": 123,
                                   "cards": [{"controller": 1, "location": 4,
                                              "sequence": 2, "code": 456}]})
    with pytest.raises(VisibilityViolation, match="face-down"):
        audit_decision_visibility(staged)
    finish = _record(observation, {"cards": [
        {"controller": 1, "location": 2, "code": 654},
    ]}, "finish_selection")
    with pytest.raises(VisibilityViolation, match="unknown identity"):
        audit_decision_visibility(finish)
    with pytest.raises(VisibilityViolation, match="acting player"):
        audit_decision_visibility(_record(replace(observation, viewer=1,
                                                  acting_player=0, hand=(),
                                                  known_opponent_field_cards=()), {}))


def test_legacy_trajectory_cannot_claim_complete_hand_audit():
    observation = _observation()
    record = _record(observation, {"controller": 1, "location": 2, "code": 321})
    legacy = Trajectory("goat", ("one", "two"), 52, (record,), 0,
                        schema_version=16)
    with pytest.raises(VisibilityViolation, match="schema v17"):
        audit_trajectory_visibility(legacy)
