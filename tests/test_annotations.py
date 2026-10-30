"""Retrospective labels must stay tied to verified visible legal decisions."""

import json
from dataclasses import replace

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
    assert labels.authorization == "self_recorded"
    assert len(records) == 1
    assert records[0].selected_action == trajectory().decisions[0].legal_actions[1]
    assert records[0].observation == trajectory().decisions[0].observation


def test_local_ai_match_cannot_be_labeled_as_human_recording(tmp_path):
    generated = replace(trajectory(), source="local_ai_match",
                        skill_metadata={"agents": ["Random", "Tactical"]})
    with pytest.raises(ValueError, match="agent replay labels require"):
        read_decision_annotations(annotation_file(tmp_path), "a" * 64, generated)


def test_edopro_self_recorded_labels_require_authorized_played_human_action(tmp_path):
    base = trajectory()
    opponent_view = replace(base.decisions[0].observation, viewer=1, acting_player=1)
    human_actions = (Action("human-pass", "pass", 1),
                     Action("human-end", "end_phase", 1))
    human_record = DecisionRecord(opponent_view, human_actions, human_actions[0])
    edopro = replace(base, source="edopro_pinned_historical",
                     decisions=(*base.decisions, human_record),
                     skill_metadata={"human_client_seat": 1,
                                     "authorization": "self_recorded"})
    labels, records = read_decision_annotations(annotation_file(
        tmp_path, choices=[{"decision_index": 1, "action_index": 0}]),
        "a" * 64, edopro)
    assert labels.choices == ((1, 0),)
    assert records == (human_record,)
    with pytest.raises(ValueError, match="human seat"):
        read_decision_annotations(annotation_file(
            tmp_path, choices=[{"decision_index": 0, "action_index": 0}]),
            "a" * 64, edopro)
    with pytest.raises(ValueError, match="played action"):
        read_decision_annotations(annotation_file(
            tmp_path, choices=[{"decision_index": 1, "action_index": 1}]),
            "a" * 64, edopro)
    with pytest.raises(ValueError, match="authorized human seat"):
        read_decision_annotations(annotation_file(
            tmp_path, choices=[{"decision_index": 1, "action_index": 0}]),
            "a" * 64, replace(edopro, skill_metadata={"human_client_seat": 1}))


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


def test_scripted_annotations_require_matching_replayed_actions(tmp_path):
    scripted = replace(trajectory(), source="scripted_timing_probe")
    labels, records = read_decision_annotations(annotation_file(
        tmp_path, authorization="scripted_scenario",
        choices=[{"decision_index": 0, "action_index": 0}]), "a" * 64, scripted)
    assert labels.authorization == "scripted_scenario"
    assert records[0].selected_action == scripted.decisions[0].selected_action
    with pytest.raises(ValueError, match="scripted trajectory"):
        read_decision_annotations(annotation_file(
            tmp_path, authorization="scripted_scenario",
            choices=[{"decision_index": 0, "action_index": 0}]),
            "a" * 64, trajectory())
    with pytest.raises(ValueError, match="replayed action"):
        read_decision_annotations(annotation_file(
            tmp_path, authorization="scripted_scenario"), "a" * 64, scripted)


def test_policy_review_can_correct_only_checkpoint_policy_seat(tmp_path):
    base = trajectory()
    opponent_view = replace(base.decisions[0].observation, viewer=1, acting_player=1)
    opponent_actions = (Action("opp-pass", "pass", 1),)
    policy = replace(base, source="policy_evaluation",
                     skill_metadata={"demonstrator_seat": 0,
                                     "policy_checkpoint_sha256": "b" * 64},
                     decisions=(*base.decisions,
                                DecisionRecord(opponent_view, opponent_actions,
                                               opponent_actions[0])))
    labels, records = read_decision_annotations(annotation_file(
        tmp_path, authorization="policy_review"), "a" * 64, policy)
    assert labels.authorization == "policy_review"
    assert records[0].selected_action == base.decisions[0].legal_actions[1]
    assert records[0].selected_action != base.decisions[0].selected_action
    with pytest.raises(ValueError, match="review authorization"):
        read_decision_annotations(annotation_file(tmp_path), "a" * 64, policy)

    with pytest.raises(ValueError, match="policy seat"):
        read_decision_annotations(annotation_file(
            tmp_path, authorization="policy_review",
            choices=[{"decision_index": 1, "action_index": 0}]),
            "a" * 64, policy)
    for invalid in (base, replace(policy, skill_metadata={"demonstrator_seat": 0}),
                    replace(policy, skill_metadata={"demonstrator_seat": 0,
                                                    "policy_checkpoint_sha256": "invalid"}),
                    replace(policy, skill_metadata={"demonstrator_seat": True,
                                                    "policy_checkpoint_sha256": "b" * 64})):
        with pytest.raises(ValueError, match="checkpoint-attributed"):
            read_decision_annotations(annotation_file(
                tmp_path, authorization="policy_review"), "a" * 64, invalid)


def test_self_play_review_cannot_be_misclassified_as_human_or_label_opponent(tmp_path):
    base = trajectory()
    opponent_view = replace(base.decisions[0].observation, viewer=1, acting_player=1)
    opponent_action = Action("opp-pass", "pass", 1)
    sampled = replace(base, source="self_play_rl",
                      skill_metadata={"learner_seat": 0, "demonstrator_seat": 0},
                      decisions=(*base.decisions,
                                 DecisionRecord(opponent_view, (opponent_action,),
                                                opponent_action)))
    labels, records = read_decision_annotations(annotation_file(
        tmp_path, authorization="self_play_review"), "a" * 64, sampled)
    assert labels.authorization == "self_play_review"
    assert records[0].selected_action == base.decisions[0].legal_actions[1]
    with pytest.raises(ValueError, match="learner seat"):
        read_decision_annotations(annotation_file(
            tmp_path, authorization="self_play_review",
            choices=[{"decision_index": 1, "action_index": 0}]),
            "a" * 64, sampled)
    with pytest.raises(ValueError, match="review authorization"):
        read_decision_annotations(annotation_file(tmp_path), "a" * 64, sampled)
    for invalid in (base, replace(sampled, skill_metadata={}),
                    replace(sampled, skill_metadata={"learner_seat": True}),
                    replace(sampled, skill_metadata={"learner_seat": 0,
                                                     "demonstrator_seat": 1})):
        with pytest.raises(ValueError, match="learner-seat self-play"):
            read_decision_annotations(annotation_file(
                tmp_path, authorization="self_play_review"), "a" * 64, invalid)
