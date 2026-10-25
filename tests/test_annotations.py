"""Retrospective labels must stay tied to verified visible legal decisions."""

import json

import pytest

from goat_ai.actions import Action
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord, Trajectory, read_decision_annotations


def trajectory():
    observation = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1", life_points=(8000, 8000),
        hand=(), field=(), graveyards=((), ()), banished=((), ()),
        opponent_hand_count=5, deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    first = Action("first", "battle_phase", 0)
    second = Action("second", "end_phase", 0)
    return Trajectory("goat", ("a.ydk", "b.ydk"), 42,
                      (DecisionRecord(observation, (first, second), first),), 0)


def annotation_file(tmp_path, **changes):
    payload = {"schema_version": 1, "source_trajectory_sha256": "a" * 64,
               "authorization": "self_recorded", "reviewer": "Reviewer",
               "choices": [{"decision_index": 0, "action_index": 1}]}
    payload.update(changes)
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(payload))
    return path


def test_annotations_select_only_reviewed_legal_action(tmp_path):
    labels, records = read_decision_annotations(
        annotation_file(tmp_path), "a" * 64, trajectory())
    assert labels.choices == ((0, 1),)
    assert labels.reviewer == "Reviewer"
    assert len(records) == 1
    assert records[0].selected_action == trajectory().decisions[0].legal_actions[1]
    assert records[0].observation == trajectory().decisions[0].observation


@pytest.mark.parametrize("change,message", [
    ({"authorization": "third_party"}, "authorization"),
    ({"reviewer": " "}, "reviewer"),
    ({"choices": []}, "at least one"),
    ({"choices": [{"decision_index": 0, "action_index": 2}]}, "not legal"),
    ({"choices": [{"decision_index": 1, "action_index": 0}]}, "decision index"),
    ({"choices": [{"decision_index": True, "action_index": 0}]}, "decision index"),
    ({"choices": [{"decision_index": 0, "action_index": 1},
                  {"decision_index": 0, "action_index": 0}]}, "duplicate"),
])
def test_annotations_reject_untrusted_or_invalid_labels(tmp_path, change, message):
    with pytest.raises(ValueError, match=message):
        read_decision_annotations(annotation_file(tmp_path, **change), "a" * 64,
                                  trajectory())


def test_annotations_reject_wrong_source_hash(tmp_path):
    with pytest.raises(ValueError, match="SHA-256"):
        read_decision_annotations(annotation_file(tmp_path), "b" * 64, trajectory())
