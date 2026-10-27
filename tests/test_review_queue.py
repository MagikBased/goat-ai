"""Candidate ranking keeps replay review diverse and deterministic."""

import pytest

from scripts.shortlist_policy_disagreements import (
    select_diverse_candidates,
    write_review_index,
)


def test_review_queue_prioritizes_margin_and_caps_prompt_and_replay():
    candidates = [
        {"trajectory": "b", "decision_index": 3, "probability_margin": 0.9,
         "audit_flags": [], "_fingerprint": ("activate", 1)},
        {"trajectory": "a", "decision_index": 2, "probability_margin": 0.8,
         "audit_flags": [], "_fingerprint": ("activate", 1)},
        {"trajectory": "b", "decision_index": 4, "probability_margin": 0.7,
         "audit_flags": [], "_fingerprint": ("attack", 2)},
        {"trajectory": "a", "decision_index": 1, "probability_margin": 0.7,
         "audit_flags": [], "_fingerprint": ("set", 3)},
    ]
    chosen = select_diverse_candidates(candidates, 3, 1)
    assert [(item["trajectory"], item["decision_index"]) for item in chosen] == [
        ("b", 3), ("a", 1)]
    assert all("_fingerprint" not in item for item in chosen)
    with pytest.raises(ValueError, match="positive"):
        select_diverse_candidates(candidates, 0, 1)


def test_review_queue_puts_visible_audit_before_confidence_margin():
    candidates = [
        {"trajectory": "a", "decision_index": 1, "probability_margin": 0.99,
         "audit_flags": [], "_fingerprint": ("pass",)},
        {"trajectory": "b", "decision_index": 2, "probability_margin": 0.0,
         "audit_flags": ["own_nobleman"], "_fingerprint": ("audit", "nobleman")},
    ]
    chosen = select_diverse_candidates(candidates, 1, 1)
    assert chosen[0]["decision_index"] == 2


def test_review_index_separates_player_label_and_hidden_reveal_views(tmp_path):
    queue = tmp_path / "review/queue.json"
    queue.parent.mkdir()
    viewer = queue.parent / "queue_viewers/game.html"
    viewer.parent.mkdir()
    viewer.write_text("player view")
    viewer.with_suffix(".review.html").write_text("reviewer view")
    selected = [{"viewer": f"{viewer}#decision=7", "turn": 2,
                 "phase": "main1", "viewer_frame": 7,
                 "policy_action": {"kind": "normal_summon", "parameters": {}},
                 "teacher_action": {"kind": "set_monster", "parameters": {}},
                 "audit_flags": ["weak_flip_summon"],
                 "probability_margin": 0.5}]
    index = write_review_index(selected, queue, tmp_path / "native")
    html = index.read_text()
    assert 'href="queue_viewers/game.html#decision=7"' in html
    assert 'href="queue_viewers/game.review.html#decision=7"' in html
    assert "labeling is disabled there" in html
    assert "weak flip summon" in html
