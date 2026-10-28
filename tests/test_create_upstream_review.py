"""Earlier mistakes are reviewed without changing a forced-choice queue."""

import json

import pytest

from goat_ai.actions import Action
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord, Trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts import create_upstream_review
from scripts.serve_review_queue import ReviewStore


def _source_queue(tmp_path):
    observation = Observation(viewer=0, acting_player=0, turn=2, phase="draw",
                              life_points=(8000, 8000), hand=(), field=(),
                              graveyards=((), ()), banished=((), ()),
                              opponent_hand_count=5, deck_counts=(32, 32),
                              extra_deck_counts=(0, 0))
    activate = Action("mst", "chain", 0, {"code": 5318639})
    pass_action = Action("pass", "pass", 0)
    target_one = Action("own_set_1", "select_card", 0, {"code": 1})
    target_two = Action("own_set_2", "select_card", 0, {"code": 2})
    decisions = (DecisionRecord(observation, (activate, pass_action), activate),
                 DecisionRecord(observation, (target_one, target_two), target_two))
    trajectory = Trajectory("goat", ("a.ydk", "b.ydk"), 42, decisions, 0,
                            source="policy_evaluation",
                            skill_metadata={"demonstrator_seat": 0,
                                            "policy_checkpoint_sha256": "b" * 64})
    replay = tmp_path / "replay.json"
    write_trajectory(replay, trajectory)
    digest = sha256_file(replay)
    viewer = tmp_path / "viewer.html"
    viewer.write_text("<html></html>")
    item = {"trajectory": str(replay), "trajectory_sha256": digest,
            "decision_index": 1, "viewer_frame": 2, "seat": 0,
            "turn": 2, "phase": "draw", "legal_action_count": 2,
            "policy_action": {"kind": "select_card", "parameters": {"code": 2}},
            "teacher_action": {"kind": "select_card", "parameters": {"code": 1}},
            "viewer": f"{viewer}#decision=2"}
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"schema_version": 1,
                                 "purpose": "human_review_candidates_not_training_labels",
                                 "checkpoint_sha256": "b" * 64,
                                 "selected": [item]}))
    return queue, replay, digest, trajectory


def test_upstream_queue_preserves_target_labels_and_offers_pass(tmp_path, monkeypatch):
    queue, replay, digest, trajectory = _source_queue(tmp_path)
    monkeypatch.setattr(create_upstream_review, "ExperimentalOcgcoreEngine",
                        lambda root: None)
    monkeypatch.setattr(create_upstream_review, "verify_trajectory", lambda *a: 2)
    monkeypatch.setattr(create_upstream_review, "audit_trajectory_visibility",
                        lambda *a: {"decisions": 2})
    original = queue.read_bytes()
    original_store = ReviewStore(queue, tmp_path / "original_labels")
    original_store.choose(digest, 1, 0)
    label_before = original_store.label_path(digest).read_bytes()
    output = tmp_path / "upstream_1.json"
    create_upstream_review.create_upstream_review(queue, 1, 0, output,
                                                   tmp_path / "native")
    assert queue.read_bytes() == original
    assert original_store.label_path(digest).read_bytes() == label_before
    assert output.with_suffix(".html").is_file()
    upstream_store = ReviewStore(output, tmp_path / "upstream_labels")
    assert upstream_store.progress() == {"choices": [], "total": 1}
    candidate = json.loads(output.read_text())["selected"][0]
    assert candidate["decision_index"] == 0
    assert candidate["teacher_action"] == {"kind": "pass", "parameters": {}}
    upstream_store.choose(digest, 0, 1)
    assert upstream_store.progress()["choices"] == [
        {"source": digest, "decision_index": 0, "action_index": 1}]
    with pytest.raises(ValueError, match="absent from this queue"):
        upstream_store.choose(digest, 1, 0)


def test_upstream_review_rejects_invalid_index_and_original_output(tmp_path,
                                                                    monkeypatch):
    queue, _, _, _ = _source_queue(tmp_path)
    monkeypatch.setattr(create_upstream_review, "ExperimentalOcgcoreEngine",
                        lambda root: None)
    monkeypatch.setattr(create_upstream_review, "verify_trajectory", lambda *a: 2)
    monkeypatch.setattr(create_upstream_review, "audit_trajectory_visibility",
                        lambda *a: {"decisions": 2})
    with pytest.raises(ValueError, match="must not replace"):
        create_upstream_review.create_upstream_review(queue, 1, 0, queue,
                                                       tmp_path / "native")
    with pytest.raises(ValueError, match="must precede"):
        create_upstream_review.create_upstream_review(
            queue, 1, 1, tmp_path / "upstream.json", tmp_path / "native")
    output = tmp_path / "upstream.json"
    output.write_text('{"saved":"other review"}')
    with pytest.raises(ValueError, match="different contents"):
        create_upstream_review.create_upstream_review(
            queue, 1, 0, output, tmp_path / "native")
    assert output.read_text() == '{"saved":"other review"}'
