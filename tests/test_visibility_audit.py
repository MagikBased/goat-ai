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


def test_audit_treats_zone_disabling_as_public_coordinates_not_card_targets():
    observation = _observation()
    # The opponent's empty Monster Zone 1 is a valid Ground Collapse choice.
    assert audit_decision_visibility(_record(observation, {
        "controller": 1, "location": 4, "sequence": 1,
    }, "disable_zone")) == {}
    assert audit_decision_visibility(_record(observation, {
        "controller": 1, "location": 4, "sequence": 1,
    }, "place")) == {}
    assert audit_decision_visibility(_record(observation, {
        "zones": [{"controller": 1, "location": 4, "sequence": 1},
                  {"controller": 1, "location": 4, "sequence": 4}],
    }, "disable_zones")) == {}
    assert audit_decision_visibility(_record(observation, {
        "zones": [{"controller": 0, "location": 8, "sequence": 4},
                  {"controller": 1, "location": 4, "sequence": 1}],
    }, "place_zones")) == {}
    for parameters in (
            {"controller": 1, "location": 4, "sequence": 1, "code": 999},
            {"controller": 1, "location": 4, "sequence": 7},
            {"zones": [{"controller": 1, "location": 4, "sequence": 1,
                        "code": 999}]},
            {"zones": [{"controller": 1, "location": 4, "sequence": 1}] * 2}):
        kind = "disable_zones" if "zones" in parameters else "disable_zone"
        with pytest.raises(VisibilityViolation, match="zone choice"):
            audit_decision_visibility(_record(observation, parameters, kind))


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


@pytest.mark.parametrize("kind", ["chain", "activate", "special_summon"])
def test_audit_checks_direct_card_references_for_every_action_kind(kind):
    observation = _observation()
    hidden = {"controller": 1, "location": 8, "sequence": 3, "code": 789}
    with pytest.raises(VisibilityViolation, match="face-down"):
        audit_decision_visibility(_record(observation, hidden, kind))
    public = {"controller": 1, "location": 8, "sequence": 1, "code": 789}
    assert audit_decision_visibility(_record(observation, public, kind)) == {
        "opponent_field_choices": 1}


@pytest.mark.parametrize("kind,parameters", [
    ("select_card", {"controller": 0, "location": 1, "sequence": 17, "code": 123}),
    ("select_card", {"controller": 0, "location": 64, "sequence": 2, "code": 123}),
    ("special_summon", {"controller": 0, "location": 64, "sequence": 2, "code": 123}),
    ("unselect_card", {"controller": 0, "location": 1, "sequence": 17,
                       "code": 123}),
    ("select_cards", {"cards": [
        {"controller": 0, "location": 1, "sequence": 17, "code": 123}]}),
    ("sort_cards", {"cards": [
        {"controller": 0, "location": 1, "sequence": 17, "code": 123}]}),
])
def test_audit_rejects_physical_deck_slots(kind, parameters):
    with pytest.raises(VisibilityViolation, match="Deck choice exposes native slot"):
        audit_decision_visibility(_record(_observation(), parameters, kind))


def test_audit_accepts_visible_deck_card_without_physical_slot():
    record = _record(_observation(), {"controller": 0, "location": 1,
                                      "code": 123})
    assert audit_decision_visibility(record) == {}


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


def test_nested_card_choices_are_audited_for_every_action_kind():
    observation = _observation()
    hidden = {"controller": 1, "location": 4, "sequence": 2, "code": 456}
    for kind in ("unselect_card", "future_card_choice"):
        with pytest.raises(VisibilityViolation, match="face-down"):
            audit_decision_visibility(_record(observation, {"cards": [hidden]}, kind))
    with pytest.raises(VisibilityViolation, match="invalid payload"):
        audit_decision_visibility(_record(observation, {"cards": {"hidden": hidden}},
                                          "future_card_choice"))


def test_action_ids_cannot_encode_hidden_information():
    observation = _observation()
    for action_id in ("hidden-card-456", "1", "00"):
        action = Action(action_id, "pass", 0)
        with pytest.raises(VisibilityViolation, match="public ordinal"):
            audit_decision_visibility(DecisionRecord(observation, (action,), action))


def test_audit_checks_single_and_multi_tribute_choices():
    observation = _observation()
    hidden = {"controller": 1, "location": 4, "sequence": 2, "code": 456}
    for kind, parameters in (("tribute", hidden),
                             ("tribute_cards", {"cards": [hidden]})):
        with pytest.raises(VisibilityViolation, match="face-down"):
            audit_decision_visibility(_record(observation, parameters, kind))
    legal = _record(observation, {"cards": [
        {"controller": 0, "location": 4, "sequence": 0, "code": 123},
        {"controller": 1, "location": 4, "sequence": 2},
    ]}, "tribute_cards")
    assert audit_decision_visibility(legal) == {
        "opponent_field_choices": 1, "hidden_field_choices": 1}


def test_audit_limits_duplicate_opponent_hand_choices_per_action():
    observation = _observation()
    duplicate = {"cards": [
        {"controller": 1, "location": 2, "code": 321},
        {"controller": 1, "location": 2, "code": 321},
    ]}
    with pytest.raises(VisibilityViolation, match="exceeds known copies"):
        audit_decision_visibility(_record(observation, duplicate, "select_cards"))
    staged = {"controller": 1, "location": 2, "code": 321,
              "cards": [{"controller": 1, "location": 2, "code": 321}]}
    with pytest.raises(VisibilityViolation, match="exceeds known copies"):
        audit_decision_visibility(_record(observation, staged))
    # Separate alternatives may each offer the same known card.
    first = Action("0", "select_card", 0, {"controller": 1, "location": 2,
                                            "code": 321})
    second = Action("1", "select_card", 0, {"controller": 1, "location": 2,
                                             "code": 321})
    assert audit_decision_visibility(DecisionRecord(observation,
                                                     (first, second), first)) == {
        "opponent_hand_choices": 2}


def test_audit_matches_opponent_graveyard_and_banished_choices_to_visible_piles():
    observation = replace(_observation(),
                          graveyards=((), (CardView(1, "graveyard", "faceup", 123, 0),)),
                          banished=((), (CardView(1, "banished", "faceup", 456, 0),
                                         CardView(1, "banished", "facedown", None, 1))))
    for choice in ({"controller": 1, "location": 16, "sequence": 0, "code": 123},
                   {"controller": 1, "location": 32, "sequence": 0, "code": 456},
                   {"controller": 1, "location": 32, "sequence": 1}):
        assert audit_decision_visibility(_record(observation, choice)) == {}
    for choice, reason in (
            ({"controller": 1, "location": 16, "sequence": 0, "code": 999},
             "disagrees"),
            ({"controller": 1, "location": 32, "sequence": 1, "code": 456},
             "face-down"),
            ({"controller": 1, "location": 32, "sequence": 2, "code": 456},
             "visible slot")):
        with pytest.raises(VisibilityViolation, match=reason):
            audit_decision_visibility(_record(observation, choice))


def test_legacy_trajectory_cannot_claim_complete_hand_audit():
    observation = _observation()
    record = _record(observation, {"controller": 1, "location": 2, "code": 321})
    legacy = Trajectory("goat", ("one", "two"), 52, (record,), 0,
                        schema_version=16)
    with pytest.raises(VisibilityViolation, match="schema v17"):
        audit_trajectory_visibility(legacy)
