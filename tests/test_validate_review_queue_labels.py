"""Downloaded review labels must match the shortlisted visible decisions."""

import json

import pytest

from goat_ai.actions import Action
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord, Trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts import validate_review_queue_labels as validator


def review_files(tmp_path):
    view = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1",
        life_points=(8000, 8000), hand=(), field=(),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    legal = (Action("a", "battle_phase", 0), Action("b", "end_phase", 0))
    record = DecisionRecord(view, legal, legal[0])
    duel = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record, record), 0,
                      source="policy_evaluation",
                      skill_metadata={"demonstrator_seat": 0,
                                      "policy_checkpoint_sha256": "b" * 64})
    replay = tmp_path / "replay.json"
    write_trajectory(replay, duel)
    digest = sha256_file(replay)
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({
        "schema_version": 1,
        "purpose": "human_review_candidates_not_training_labels",
        "selected": [{"trajectory": replay.name, "trajectory_sha256": digest,
                      "decision_index": 0}],
    }))
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({
        "schema_version": 1, "source_trajectory_sha256": digest,
        "authorization": "policy_review", "reviewer": "Test reviewer",
        "choices": [{"decision_index": 0, "action_index": 1}],
    }))
    return queue, labels, replay


def test_queue_label_validation_binds_replay_and_shortlisted_choice(tmp_path, monkeypatch):
    queue, labels, _ = review_files(tmp_path)
    monkeypatch.setattr(validator, "verify_trajectory", lambda *_: 2)
    monkeypatch.setattr(validator, "audit_trajectory_visibility", lambda *_: None)
    result = validator.validate_labels(queue, [labels], tmp_path)
    assert result["authorization"] == "policy_review"
    assert result["verified_decisions"] == 2
    assert result["reviewed_decisions"] == 1
    assert result["cases"][0]["changed_choices"] == 1

    data = json.loads(labels.read_text())
    data["choices"][0]["decision_index"] = 1
    labels.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="outside shortlisted"):
        validator.validate_labels(queue, [labels], tmp_path)


def test_queue_label_validation_rejects_wrong_replay_or_duplicate_export(tmp_path, monkeypatch):
    queue, labels, replay = review_files(tmp_path)
    monkeypatch.setattr(validator, "verify_trajectory", lambda *_: 2)
    monkeypatch.setattr(validator, "audit_trajectory_visibility", lambda *_: None)
    with pytest.raises(ValueError, match="duplicate export"):
        validator.validate_labels(queue, [labels, labels], tmp_path)
    replay.write_text(replay.read_text() + " ")
    with pytest.raises(ValueError, match="SHA-256 changed"):
        validator.validate_labels(queue, [labels], tmp_path)
    data = json.loads(labels.read_text())
    data["source_trajectory_sha256"] = "c" * 64
    labels.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="absent from review queue"):
        validator.validate_labels(queue, [labels], tmp_path)
