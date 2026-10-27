"""Candidate ranking and queue navigation stay deterministic."""

import re
import shutil
import subprocess
import json

import pytest

from scripts.refresh_review_queue import refresh_review_queue
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
    assert 'id="previous-item"' in html
    assert 'id="next-item"' in html
    assert 'id="queue-search"' in html


def test_refresh_rejects_changed_trajectory(tmp_path):
    queue = tmp_path / "queue.json"
    replay = tmp_path / "replay.json"
    replay.write_text("changed")
    queue.write_text(json.dumps({"selected": [{
        "trajectory": str(replay), "trajectory_sha256": "0" * 64,
        "viewer": str(tmp_path / "viewer.html") + "#decision=1",
    }]}))
    with pytest.raises(ValueError, match="trajectory hash differs"):
        refresh_review_queue(queue, tmp_path, index_only=True)


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_review_queue_navigation_stays_in_one_page(tmp_path):
    queue = tmp_path / "review/queue.json"
    queue.parent.mkdir()
    viewers = queue.parent / "queue_viewers"
    viewers.mkdir()
    selected = []
    for number in (1, 2):
        viewer = viewers / f"game{number}.html"
        viewer.write_text(f"<html><body>Game {number}</body></html>")
        viewer.with_suffix(".review.html").write_text("<html><body>Reveal</body></html>")
        selected.append({"viewer": f"{viewer}#decision={number}",
                         "turn": number, "phase": "main1", "viewer_frame": number,
                         "policy_action": {"kind": "pass", "parameters": {}},
                         "teacher_action": {"kind": "end_phase", "parameters": {}},
                         "audit_flags": []})
    index = write_review_index(selected, queue, tmp_path / "native")
    probe = """<script>
      document.querySelector('.review-card .primary').click();
      const first = document.getElementById('item-position').textContent;
      const replayFrameProbe = document.getElementById('stage-frame');
      window.dispatchEvent(new MessageEvent('message', {source: replayFrameProbe.contentWindow,
        data: {type: 'goat-ai-review-label-state', pending: true}}));
      window.confirm = () => false;
      document.getElementById('next-item').click();
      const protectedItem = document.getElementById('item-position').textContent;
      window.confirm = () => true;
      document.getElementById('next-item').click();
      const second = document.getElementById('item-position').textContent;
      document.getElementById('toggle-reveal').click();
      const reveal = document.getElementById('stage-frame').src.includes('.review.html');
      document.getElementById('back-to-queue').click();
      document.body.dataset.queueProbe = [first, protectedItem, second, reveal,
        document.getElementById('stage').hidden].join('|');
    </script>"""
    index.write_text(index.read_text().replace("</html>", probe + "</html>"))
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=400", "--dump-dom",
        index.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-queue-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "1 / 2|1 / 2|2 / 2|true|true"
