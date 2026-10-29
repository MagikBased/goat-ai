"""Earlier mistakes are reviewed without changing a forced-choice queue."""

import json
from dataclasses import replace

import pytest

from goat_ai.actions import Action
from goat_ai.observations import ChainLinkView, Observation
from goat_ai.replay import DecisionRecord, Trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts import create_noted_upstream_queue, create_upstream_review
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
    queue, _, digest, _ = _source_queue(tmp_path)
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
    assert upstream_store.progress() == {"choices": [], "notes": [], "total": 1}
    candidate = json.loads(output.read_text())["selected"][0]
    assert candidate["decision_index"] == 0
    assert candidate["teacher_action"] == {"kind": "pass", "parameters": {}}
    upstream_store.choose(digest, 0, 1)
    assert upstream_store.progress()["choices"] == [
        {"source": digest, "decision_index": 0, "action_index": 1}]
    with pytest.raises(ValueError, match="absent from this queue"):
        upstream_store.choose(digest, 1, 0)


def test_upstream_candidate_offers_phase_transition_when_pass_is_absent(tmp_path):
    queue, replay, digest, trajectory = _source_queue(tmp_path)
    activation = trajectory.decisions[0]
    battle = Action("battle", "battle_phase", 0)
    end = Action("end", "end_phase", 0)
    main_activation = replace(activation, legal_actions=(activation.selected_action,
                                                         battle, end))
    trajectory = replace(trajectory, decisions=(main_activation,
                                                trajectory.decisions[1]))
    item = json.loads(queue.read_text())["selected"][0]
    candidate = create_upstream_review.upstream_candidate(
        trajectory, item, digest, replay, queue, 0)
    assert candidate["teacher_action"] == {"kind": "battle_phase", "parameters": {}}
    assert candidate["policy_action"]["kind"] == "chain"


def test_upstream_queue_finds_matching_activation_automatically(tmp_path,
                                                                 monkeypatch):
    queue, replay, _, trajectory = _source_queue(tmp_path)
    target = trajectory.decisions[1]
    source = ChainLinkView(1, 5318639, 0, 8, 0)
    target = replace(target, observation=replace(
        target.observation, chain=(source,)))
    write_trajectory(replay, replace(trajectory, schema_version=2,
                                     decisions=(trajectory.decisions[0], target)))
    listing = json.loads(queue.read_text())
    listing["selected"][0]["trajectory_sha256"] = sha256_file(replay)
    queue.write_text(json.dumps(listing))
    monkeypatch.setattr(create_upstream_review, "ExperimentalOcgcoreEngine",
                        lambda root: None)
    monkeypatch.setattr(create_upstream_review, "verify_trajectory", lambda *a: 2)
    monkeypatch.setattr(create_upstream_review, "audit_trajectory_visibility",
                        lambda *a: {"decisions": 2})
    output = tmp_path / "upstream.json"
    create_upstream_review.create_upstream_review(
        queue, 1, None, output, tmp_path / "native")
    assert json.loads(output.read_text())["selected"][0]["decision_index"] == 0


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


def test_saved_upstream_note_builds_separate_unlabeled_queue(tmp_path, monkeypatch):
    queue, _, digest, _ = _source_queue(tmp_path)
    labels = tmp_path / "source_labels"
    source_store = ReviewStore(queue, labels)
    source_store.save_note(digest, 1, "upstream_mistake",
                           "MST should have stayed unactivated")
    monkeypatch.setattr(create_noted_upstream_queue, "ExperimentalOcgcoreEngine",
                        lambda root: None)
    monkeypatch.setattr(create_noted_upstream_queue, "verify_trajectory", lambda *a: 2)
    monkeypatch.setattr(create_noted_upstream_queue, "audit_trajectory_visibility",
                        lambda *a: {"decisions": 2})
    output = tmp_path / "noted_upstream.json"
    path, unmatched = create_noted_upstream_queue.create_noted_upstream_queue(
        queue, output, tmp_path / "native", labels_dir=labels)
    assert path == output and unmatched == 0
    result = json.loads(output.read_text())
    assert result["purpose"] == "human_review_candidates_not_training_labels"
    assert result["source_queue_sha256"] == sha256_file(queue)
    assert result["selected"][0]["decision_index"] == 0
    assert result["selected"][0]["teacher_action"]["kind"] == "pass"
    assert "MST should have stayed unactivated" in output.with_suffix(".html").read_text()
    assert source_store.progress()["choices"] == []
    assert ReviewStore(output, tmp_path / "upstream_labels").progress()["choices"] == []


def test_context_note_can_offer_upstream_activation_without_becoming_label(
        tmp_path, monkeypatch):
    queue, _, digest, _ = _source_queue(tmp_path)
    labels = tmp_path / "source_labels"
    ReviewStore(queue, labels).save_note(
        digest, 1, "context", "MST activation was the earlier mistake")
    monkeypatch.setattr(create_noted_upstream_queue, "ExperimentalOcgcoreEngine",
                        lambda root: None)
    monkeypatch.setattr(create_noted_upstream_queue, "verify_trajectory", lambda *a: 2)
    monkeypatch.setattr(create_noted_upstream_queue, "audit_trajectory_visibility",
                        lambda *a: {"decisions": 2})
    output = tmp_path / "context_upstream.json"
    with pytest.raises(ValueError, match="no earlier optional activations"):
        create_noted_upstream_queue.create_noted_upstream_queue(
            queue, output, tmp_path / "native", labels_dir=labels)
    path, unmatched = create_noted_upstream_queue.create_noted_upstream_queue(
        queue, output, tmp_path / "native", labels_dir=labels,
        include_context_notes=True)
    assert path == output and unmatched == 0
    item = json.loads(output.read_text())["selected"][0]
    assert item["decision_index"] == 0
    assert item["source_note_kind"] == "context"
    assert item["teacher_action"]["kind"] == "pass"
    assert ReviewStore(output, tmp_path / "upstream_labels").progress()["choices"] == []


def test_noted_upstream_queue_links_note_to_matching_effect(tmp_path, monkeypatch):
    queue, replay, _, trajectory = _source_queue(tmp_path)
    initial, target = trajectory.decisions
    mst = replace(initial.selected_action, parameters={
        "code": 5318639, "location": 8, "sequence": 2})
    initial = replace(initial, selected_action=mst,
                      legal_actions=(mst, initial.legal_actions[1]))
    book = Action("book", "chain", 0, {"code": 14087893,
                                      "location": 8, "sequence": 3})
    unrelated = DecisionRecord(initial.observation,
                               (book, initial.legal_actions[1]), book)
    source = ChainLinkView(1, 5318639, 0, 8, 2)
    target = replace(target, observation=replace(
        target.observation, chain=(source,)))
    write_trajectory(replay, replace(trajectory, schema_version=2,
                                     decisions=(initial, unrelated, target)))
    digest = sha256_file(replay)
    listing = json.loads(queue.read_text())
    listing["selected"][0].update(trajectory_sha256=digest, decision_index=2,
                                    viewer_frame=3, legal_action_count=2)
    queue.write_text(json.dumps(listing))
    labels = tmp_path / "source_labels"
    ReviewStore(queue, labels).save_note(digest, 2, "upstream_mistake",
                                         "MST activation was the mistake")
    monkeypatch.setattr(create_noted_upstream_queue, "ExperimentalOcgcoreEngine",
                        lambda root: None)
    monkeypatch.setattr(create_noted_upstream_queue, "verify_trajectory", lambda *a: 3)
    monkeypatch.setattr(create_noted_upstream_queue, "audit_trajectory_visibility",
                        lambda *a: {"decisions": 3})
    output = tmp_path / "noted_upstream.json"
    create_noted_upstream_queue.create_noted_upstream_queue(
        queue, output, tmp_path / "native", labels_dir=labels)
    assert [item["decision_index"] for item in json.loads(output.read_text())[
        "selected"]] == [0]


def test_noted_upstream_queue_requires_a_saved_note(tmp_path):
    queue, _, _, _ = _source_queue(tmp_path)
    with pytest.raises(ValueError, match="no earlier optional activations"):
        create_noted_upstream_queue.create_noted_upstream_queue(
            queue, tmp_path / "noted_upstream.json", tmp_path / "native",
            labels_dir=tmp_path / "empty")
