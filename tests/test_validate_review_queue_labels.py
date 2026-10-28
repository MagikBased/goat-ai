"""Downloaded review labels must match the shortlisted visible decisions."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.actions import Action
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord, Trajectory, read_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts import convert_review_labels_to_preferences as converter
from scripts import create_review_recheck_queue as recheck
from scripts import merge_review_queue_labels as merger
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
        "checkpoint_sha256": "b" * 64,
        "selected": [{"trajectory": replay.name, "trajectory_sha256": digest,
                      "decision_index": 0, "viewer_frame": 1, "seat": 0,
                      "turn": 1, "phase": "main1", "legal_action_count": 2,
                      "policy_action": {"kind": "battle_phase", "parameters": {}},
                      "teacher_action": {"kind": "end_phase", "parameters": {}}}],
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
    assert result["policy_checkpoint_sha256"] == "b" * 64
    assert result["verified_decisions"] == 2
    assert result["reviewed_decisions"] == 1
    assert result["cases"][0]["changed_choices"] == 1

    data = json.loads(labels.read_text())
    data["choices"][0]["decision_index"] = 1
    labels.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="outside shortlisted"):
        validator.validate_labels(queue, [labels], tmp_path)


def test_changed_review_choice_becomes_only_recorded_pairwise_preference(
    tmp_path, monkeypatch,
):
    queue, labels, replay = review_files(tmp_path)
    trajectory = read_trajectory(replay)
    third = Action("c", "set_spell_trap", 0)
    trajectory = replace(trajectory, decisions=tuple(
        replace(record, legal_actions=(*record.legal_actions, third))
        for record in trajectory.decisions))
    write_trajectory(replay, trajectory)
    digest = sha256_file(replay)
    offered = json.loads(queue.read_text())
    offered["selected"][0]["trajectory_sha256"] = digest
    offered["selected"][0]["legal_action_count"] = 3
    offered["selected"].append({**offered["selected"][0],
                                "decision_index": 1, "viewer_frame": 2})
    queue.write_text(json.dumps(offered))
    raw = json.loads(labels.read_text())
    raw["source_trajectory_sha256"] = digest
    raw["choices"].append({"decision_index": 1, "action_index": 0})
    labels.write_text(json.dumps(raw))
    monkeypatch.setattr(validator, "verify_trajectory", lambda *_: 2)
    monkeypatch.setattr(validator, "audit_trajectory_visibility", lambda *_: None)

    manifest = converter.convert(queue, [labels], tmp_path, tmp_path / "preferences")
    assert manifest["reviewed_decisions"] == 2
    assert manifest["changed_preferences"] == 1
    item = json.loads(Path(manifest["cases"][0]["preferences"]).read_text())
    assert item["source_trajectory_sha256"] == sha256_file(replay)
    assert item["preferences"] == [{"decision_index": 0,
                                    "preferred_action_indices": [1],
                                    "disfavored_action_indices": [0]}]


def test_ambiguous_review_recheck_starts_with_fresh_choices(tmp_path, monkeypatch):
    queue, labels, _ = review_files(tmp_path)
    source = json.loads(queue.read_text())
    second = {**source["selected"][0], "decision_index": 1, "viewer_frame": 2}
    source["selected"].append(second)
    queue.write_text(json.dumps(source))
    label_dir = tmp_path / "old_labels"
    label_dir.mkdir()
    labels.rename(label_dir / labels.name)
    monkeypatch.setattr(validator, "verify_trajectory", lambda *_: 2)
    monkeypatch.setattr(validator, "audit_trajectory_visibility", lambda *_: None)
    output = tmp_path / "fresh" / "recheck.json"

    assert recheck.create_recheck_queue(queue, label_dir, output, tmp_path,
                                        refresh=False) == 1
    fresh = json.loads(output.read_text())
    assert len(fresh["selected"]) == 1
    assert fresh["selected"][0]["decision_index"] == 0
    assert "action_index" not in output.read_text()
    assert Path(fresh["selected"][0]["viewer"].split("#")[0]).is_relative_to(
        output.parent)
    assert recheck.create_recheck_queue(queue, label_dir, output, tmp_path,
                                        refresh=False) == 1
    assert json.loads((label_dir / labels.name).read_text())["choices"] == [
        {"decision_index": 0, "action_index": 1}]


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


@pytest.mark.parametrize("field,value,message", [
    ("checkpoint_sha256", "c" * 64, "declared policy checkpoint"),
    ("seat", 1, "metadata differs"),
    ("turn", 2, "metadata differs"),
    ("phase", "battle_start", "metadata differs"),
    ("legal_action_count", 3, "metadata differs"),
    ("policy_action", {"kind": "end_phase", "parameters": {}}, "metadata differs"),
    ("teacher_action", {"kind": "attack", "parameters": {}}, "metadata differs"),
])
def test_queue_label_validation_rejects_stale_display_metadata(
    tmp_path, monkeypatch, field, value, message,
):
    queue, labels, _ = review_files(tmp_path)
    monkeypatch.setattr(validator, "verify_trajectory", lambda *_: 2)
    monkeypatch.setattr(validator, "audit_trajectory_visibility", lambda *_: None)
    data = json.loads(queue.read_text())
    if field == "checkpoint_sha256":
        data[field] = value
    else:
        data["selected"][0][field] = value
    queue.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=message):
        validator.validate_labels(queue, [labels], tmp_path)


def test_merge_reviewers_requires_agreement_and_preserves_sources(tmp_path, monkeypatch):
    queue, first, _ = review_files(tmp_path)
    monkeypatch.setattr(validator, "verify_trajectory", lambda *_: 2)
    monkeypatch.setattr(validator, "audit_trajectory_visibility", lambda *_: None)
    second = tmp_path / "second.json"
    raw = json.loads(first.read_text())
    raw["reviewer"] = "Second reviewer"
    second.write_text(json.dumps(raw))
    result = merger.merge_labels(queue, [first, second], tmp_path,
                                 tmp_path / "merged", min_reviewers=2)
    assert len(result["merged"]) == 1
    assert result["merged"][0]["decisions"] == 1
    assert not result["unresolved"]
    annotation = json.loads(Path(result["merged"][0]["annotation"]).read_text())
    assert annotation["choices"] == [{"decision_index": 0, "action_index": 1}]
    assert annotation["aggregation"]["decision_provenance"] == [
        {"decision_index": 0, "reviewers": ["Second reviewer", "Test reviewer"]}]
    assert len(annotation["aggregation"]["source_label_sha256"]) == 2


def test_merge_reviewers_holds_conflicts_and_insufficient_votes(tmp_path, monkeypatch):
    queue, first, _ = review_files(tmp_path)
    monkeypatch.setattr(validator, "verify_trajectory", lambda *_: 2)
    monkeypatch.setattr(validator, "audit_trajectory_visibility", lambda *_: None)
    second = tmp_path / "second.json"
    raw = json.loads(first.read_text())
    raw["reviewer"] = "Second reviewer"
    raw["choices"][0]["action_index"] = 0
    second.write_text(json.dumps(raw))
    result = merger.merge_labels(queue, [first, second], tmp_path,
                                 tmp_path / "conflict", min_reviewers=1)
    assert not result["merged"]
    assert result["unresolved"][0]["reason"] == "conflict"
    single = merger.merge_labels(queue, [first], tmp_path,
                                 tmp_path / "single", min_reviewers=2)
    assert not single["merged"]
    assert single["unresolved"][0]["reason"] == "insufficient_reviews"


def test_merge_rejects_same_reviewer_contradiction(tmp_path, monkeypatch):
    queue, first, _ = review_files(tmp_path)
    monkeypatch.setattr(validator, "verify_trajectory", lambda *_: 2)
    monkeypatch.setattr(validator, "audit_trajectory_visibility", lambda *_: None)
    second = tmp_path / "second.json"
    raw = json.loads(first.read_text())
    raw["reviewer"] = "test REVIEWER"
    raw["choices"][0]["action_index"] = 0
    second.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="contradicted their choice"):
        merger.merge_labels(queue, [first, second], tmp_path, tmp_path / "merged")
    assert not (tmp_path / "merged").exists()
