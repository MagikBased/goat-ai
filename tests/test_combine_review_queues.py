"""Combined review sessions keep checkpoint and source-decision identity."""

import json

import pytest

from scripts.combine_review_queues import combine_selected


def queue(tmp_path, name, decision, *, checkpoint="b" * 64, viewer=None):
    path = tmp_path / name
    viewer = viewer or tmp_path / "view.html"
    viewer.write_text("viewer", encoding="utf-8")
    action = {"kind": "pass", "parameters": {}}
    item = {
        "trajectory": str(tmp_path / "replay.json"),
        "trajectory_sha256": "a" * 64,
        "decision_index": decision,
        "viewer_frame": decision + 1,
        "seat": 0,
        "turn": 1,
        "phase": "main1",
        "legal_action_count": 2,
        "policy_action": action,
        "teacher_action": action,
        "audit_flags": [],
        "viewer": f"{viewer}#decision={decision + 1}",
    }
    payload = {"schema_version": 1,
               "purpose": "human_review_candidates_not_training_labels",
               "checkpoint_sha256": checkpoint, "selected": [item]}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


def test_combined_queue_retains_distinct_source_decisions(tmp_path):
    first = queue(tmp_path, "first.json", 0)
    second = queue(tmp_path, "second.json", 1)
    combined = combine_selected([first, second], tmp_path / "combined.json")
    assert len(combined["selected"]) == 2
    assert [item["decision_index"] for item in combined["selected"]] == [0, 1]
    assert combined["checkpoint_sha256"] == "b" * 64
    assert len(combined["source_queue_sha256"]) == 2


def test_combined_queue_rejects_checkpoint_or_decision_overlap(tmp_path):
    first = queue(tmp_path, "first.json", 0)
    different = queue(tmp_path, "different.json", 1, checkpoint="c" * 64)
    duplicate = queue(tmp_path, "duplicate.json", 0)
    with pytest.raises(ValueError, match="different policy checkpoints"):
        combine_selected([first, different], tmp_path / "combined.json")
    with pytest.raises(ValueError, match="duplicate review decision"):
        combine_selected([first, duplicate], tmp_path / "combined.json")


def test_combined_queue_rejects_viewer_outside_session(tmp_path):
    first = queue(tmp_path, "first.json", 0)
    second = queue(tmp_path, "second.json", 1, viewer=tmp_path.parent / "outside.html")
    with pytest.raises(ValueError, match="below combined queue folder"):
        combine_selected([first, second], tmp_path / "combined.json")
