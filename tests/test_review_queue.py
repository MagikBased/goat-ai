"""Candidate ranking and queue navigation stay deterministic."""

import hashlib
import json
import re
import shutil
import subprocess

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


def test_review_queue_can_rank_raw_logit_gaps_without_changing_default():
    candidates = [
        {"trajectory": "a", "decision_index": 1, "probability_margin": 0.8,
         "logit_margin": 0.3, "audit_flags": [], "_fingerprint": ("a",)},
        {"trajectory": "b", "decision_index": 2, "probability_margin": 0.6,
         "logit_margin": 3.0, "audit_flags": [], "_fingerprint": ("b",)},
    ]
    assert select_diverse_candidates(candidates, 1, 1)[0]["decision_index"] == 1
    assert select_diverse_candidates(candidates, 1, 1, rank_by="logit")[0][
        "decision_index"] == 2
    with pytest.raises(ValueError, match="positive"):
        select_diverse_candidates(candidates, 1, 1, rank_by="unknown")


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
    assert "Offline view: choices are not saved automatically" in html
    assert "weak flip summon" in html
    assert 'id="previous-item"' in html
    assert 'id="next-item"' in html
    assert 'id="queue-search"' in html


def test_review_index_distinguishes_shared_flagged_play_from_disagreement(tmp_path):
    queue = tmp_path / "queue.json"
    viewer = tmp_path / "game.html"
    viewer.write_text("player view")
    action = {"kind": "activate", "parameters": {"code": 19613556}}
    selected = [{"viewer": f"{viewer}#decision=3", "turn": 1,
                 "phase": "main1", "viewer_frame": 3,
                 "policy_action": action, "teacher_action": action,
                 "audit_flags": ["heavy_storm_negative_visible_trade"]}]
    html = write_review_index(selected, queue, tmp_path / "native").read_text()
    assert "Both agents played:" in html
    assert "Tactical suggests:" not in html
    assert "A flagged play can be one both agents made." in html


def test_review_index_names_comparison_policy_instead_of_tactical(tmp_path):
    queue = tmp_path / "queue.json"
    viewer = tmp_path / "game.html"
    viewer.write_text("player view")
    selected = [{"viewer": f"{viewer}#decision=4", "turn": 2,
                 "phase": "main1", "viewer_frame": 4,
                 "policy_action": {"kind": "normal_summon", "parameters": {}},
                 "teacher_action": {"kind": "set_monster", "parameters": {}},
                 "audit_flags": []}]
    html = write_review_index(selected, queue, tmp_path / "native",
                              comparison_label="Comparison policy").read_text()
    assert "Comparison policy suggests:" in html
    assert "Comparison policy suggests another play" in html
    assert "Tactical suggests:" not in html


def test_review_index_names_public_effect_options(tmp_path, monkeypatch):
    from scripts import shortlist_policy_disagreements as shortlist

    queue = tmp_path / "queue.json"
    viewer = tmp_path / "game.html"
    viewer.write_text("player view")
    card = 98045062
    first = (card << 20) | 1
    monkeypatch.setattr(shortlist, "_card_names", lambda codes, root: {
        card: "Enemy Controller"})
    monkeypatch.setattr(shortlist, "_option_texts", lambda codes, root: {
        first: "Change the battle position of an opponent's monster"})
    action = {"kind": "select_option", "parameters": {"prompt_id": first}}
    selected = [{"viewer": f"{viewer}#decision=4", "turn": 2,
                 "phase": "main1", "viewer_frame": 4,
                 "policy_action": action, "teacher_action": action,
                 "option_source_card": card, "audit_flags": []}]
    html = write_review_index(selected, queue, tmp_path / "native").read_text()
    assert "Review Enemy Controller effect choice" in html
    assert "Change the battle position of an opponent&#x27;s monster" in html


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


def test_refresh_visible_pages_preserves_existing_reviewer_reveal(tmp_path, monkeypatch):
    from scripts import refresh_review_queue as refresh_module

    queue = tmp_path / "queue.json"
    replay = tmp_path / "replay.json"
    replay.write_text("recorded duel", encoding="utf-8")
    digest = hashlib.sha256(replay.read_bytes()).hexdigest()
    viewer = tmp_path / "game.html"
    reveal = viewer.with_suffix(".review.html")
    reveal.write_text("previously verified hidden cards", encoding="utf-8")
    selected = [{"trajectory": str(replay), "trajectory_sha256": digest,
                 "viewer": str(viewer) + "#decision=1"}]
    queue.write_text(json.dumps({"selected": selected}), encoding="utf-8")
    rendered = []

    def render(source, output, native_root, *, reviewer_reveal=False):
        rendered.append((source, output, reviewer_reveal))
        if reviewer_reveal:
            raise AssertionError("old hidden-card reveal must not be recomputed")
        output.write_text("updated visible layout", encoding="utf-8")

    monkeypatch.setattr(refresh_module, "render_replay", render)
    monkeypatch.setattr(refresh_module, "write_review_index",
                        lambda items, path, root: path.with_suffix(".html"))
    assert refresh_review_queue(queue, tmp_path, skip_reviewer_reveal=True) == (1, 1)
    assert rendered == [(replay, viewer, False)]
    assert viewer.read_text(encoding="utf-8") == "updated visible layout"
    assert reveal.read_text(encoding="utf-8") == "previously verified hidden cards"
    assert json.loads(queue.read_text(encoding="utf-8"))["selected"] == selected


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
                         "trajectory_sha256": str(number) * 64,
                         "decision_index": number,
                         "turn": number, "phase": "main1", "viewer_frame": number,
                         "policy_action": {"kind": "pass", "parameters": {}},
                         "teacher_action": {"kind": "end_phase", "parameters": {}},
                         "audit_flags": []})
    index = write_review_index(selected, queue, tmp_path / "native")
    probe = """<script>
      (async () => {
      document.querySelector('.review-card .primary').click();
      await new Promise(resolve => setTimeout(resolve, 0));
      const first = document.getElementById('item-position').textContent;
      const replayFrameProbe = document.getElementById('stage-frame');
      window.dispatchEvent(new MessageEvent('message', {source: replayFrameProbe.contentWindow,
        data: {type: 'goat-ai-review-label-state', pending: true}}));
      window.confirm = () => false;
      document.getElementById('next-item').click();
      await new Promise(resolve => setTimeout(resolve, 0));
      const protectedItem = document.getElementById('item-position').textContent;
      window.confirm = () => true;
      document.getElementById('next-item').click();
      await new Promise(resolve => setTimeout(resolve, 0));
      const second = document.getElementById('item-position').textContent;
      document.getElementById('toggle-reveal').click();
      await new Promise(resolve => setTimeout(resolve, 0));
      const reveal = document.getElementById('stage-frame').src.includes('.review.html');
      document.getElementById('back-to-queue').click();
      labels.set(bookmarkKey(items[1]), 0); progressMode = true; updateProgress();
      openItem(0);
      await new Promise(resolve => setTimeout(resolve, 0));
      const skipped = document.getElementById('next-item').disabled;
      document.getElementById('show-labeled').click();
      const restored = !document.getElementById('next-item').disabled;
      notes.set(bookmarkKey(items[0]), 'upstream_mistake'); updateProgress();
      const noted = !document.querySelector('.review-card .note-status').hidden &&
        document.getElementById('review-progress').textContent.includes('1 noted');
      document.body.dataset.queueProbe = [first, protectedItem, second, reveal,
        skipped, restored, noted].join('|');
      })();
    </script>"""
    index.write_text(index.read_text().replace("</html>", probe + "</html>"))
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=400", "--dump-dom",
        index.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-queue-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "1 / 2|1 / 2|2 / 2|true|true|true|true"
