"""Candidate ranking and queue navigation stay deterministic."""

import hashlib
import json
import re
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from goat_ai.actions import Action
from scripts.refresh_review_queue import refresh_review_queue
from scripts.shortlist_policy_disagreements import (
    activation_matches_chain_source,
    optional_upstream_activation,
    recorded_policy_options,
    select_diverse_candidates,
    visible_ring_guard_alternative,
    write_review_index,
)


def test_review_queue_rebuilds_recorded_guard_versions_without_extra_facts():
    facts = {511000824: (4, 0, 0)}
    assert recorded_policy_options("greedy", facts) == {}
    assert recorded_policy_options("greedy_own_loss_guard_v1", facts) == {
        "own_loss_guard": True, "own_loss_guard_version": 1, "card_facts": None}
    assert recorded_policy_options("greedy_own_loss_guard_v2", facts) == {
        "own_loss_guard": True, "own_loss_guard_version": 2, "card_facts": facts}
    assert recorded_policy_options("greedy_own_loss_guard_v3", facts) == {
        "own_loss_guard": True, "own_loss_guard_version": 3, "card_facts": None}
    with pytest.raises(ValueError, match="unsupported policy inference"):
        recorded_policy_options("greedy_unknown", facts)


def test_review_queue_ring_suggestion_applies_full_v3_mask():
    import torch

    from goat_ai.observations import CardView, Observation

    own_monster = CardView(0, "monster", "faceup", 49881766, 0,
                           "attack", 1900, 1500)
    own_spell = CardView(0, "spell_trap", "facedown", 45986603, 0)
    view = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(own_monster, own_spell),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    ring = Action("ring", "activate", 0, {"code": 511000824})
    storm = Action("storm", "activate", 0, {"code": 19613556})
    summon = Action("summon", "normal_summon", 0, {"code": 71413901})
    assert visible_ring_guard_alternative(
        view, (ring, storm, summon), torch.tensor([3.0, 2.0, 1.0])) == summon


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


def test_focused_review_keeps_distinct_contexts_for_same_card_action():
    cases = [
        {"trajectory": "a", "decision_index": 10, "probability_margin": 0.9,
         "audit_flags": ["nobleman_only_own_set_monster"],
         "_fingerprint": ("activate", 504700116)},
        {"trajectory": "b", "decision_index": 20, "probability_margin": 0.8,
         "audit_flags": ["nobleman_only_own_set_monster"],
         "_fingerprint": ("activate", 504700116)},
    ]
    assert len(select_diverse_candidates(cases, 2, 1)) == 1
    focused = select_diverse_candidates(cases, 2, 1, dedupe_fingerprints=False)
    assert [(item["trajectory"], item["decision_index"]) for item in focused] == [
        ("a", 10), ("b", 20)]


def test_forced_own_target_review_returns_to_optional_activation():
    breaker = 71413901
    pass_action = Action("pass", "pass", 1)
    activate = Action("breaker", "chain", 1, {"code": breaker})
    target = Action("own trap", "select_card", 1, {"controller": 1})
    prior_view = SimpleNamespace(turn=4, acting_player=1)
    forced_view = SimpleNamespace(
        turn=4, acting_player=1,
        chain=(SimpleNamespace(card_code=breaker, controller=1,
                               location=4, sequence=2),),
    )
    replay = SimpleNamespace(decisions=(
        SimpleNamespace(observation=prior_view, selected_action=activate,
                        legal_actions=(activate, pass_action)),
        SimpleNamespace(observation=forced_view, selected_action=target,
                        legal_actions=(target,)),
    ))
    assert optional_upstream_activation(replay, 1) == 0
    replay.decisions[0].legal_actions = (activate,)
    assert optional_upstream_activation(replay, 1) is None


def test_upstream_effect_link_distinguishes_unrelated_and_same_name_activations():
    source = SimpleNamespace(card_code=5318639, controller=0,
                             location=8, sequence=2)
    def action(code, slot):
        return Action(str(slot), "chain", 0,
                      {"code": code, "location": 8, "sequence": slot})
    assert activation_matches_chain_source(action(5318639, 2), source)
    assert not activation_matches_chain_source(action(5318639, 1), source)
    assert not activation_matches_chain_source(action(14087893, 2), source)
    # Activating from hand moves the card to the public Spell/Trap Zone.
    assert activation_matches_chain_source(Action(
        "hand", "activate", 0, {"code": 5318639, "location": 2,
                                  "sequence": 0}), source)
    pass_action = Action("pass", "pass", 0)
    target = Action("target", "select_card", 0)
    view = SimpleNamespace(turn=3, acting_player=0)
    forced = SimpleNamespace(turn=3, acting_player=0, chain=(source,))
    replay = SimpleNamespace(decisions=(
        SimpleNamespace(observation=view, selected_action=action(5318639, 2),
                        legal_actions=(action(5318639, 2), pass_action)),
        SimpleNamespace(observation=view, selected_action=action(14087893, 3),
                        legal_actions=(action(14087893, 3), pass_action)),
        SimpleNamespace(observation=forced, selected_action=target,
                        legal_actions=(target,)),
    ))
    assert optional_upstream_activation(replay, 2) == 0


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
    assert 'id="review-upstream"' in html
    assert "/api/review/upstream" in html


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
      notes.set(bookmarkKey(items[0]), 'reject_recorded'); updateProgress();
      document.getElementById('show-labeled').click();
      const rejectionReviewed = document.getElementById('review-progress').textContent
        .includes('2 of 2 review items reviewed') &&
        document.querySelector('.review-card').hidden &&
        document.querySelector('.review-card .label-status').textContent === '✓ Rejected';
      document.getElementById('show-labeled').click();
      let prompts = 0;
      window.confirm = () => { prompts++; return false; };
      window.dispatchEvent(new MessageEvent('message', {source: replayFrameProbe.contentWindow,
        data: {type: 'goat-ai-review-label-state', pending: true, saving: true}}));
      document.getElementById('next-item').click();
      await new Promise(resolve => setTimeout(resolve, 0));
      const waitedForSave = document.getElementById('item-position').textContent === '1 / 2';
      window.dispatchEvent(new MessageEvent('message', {source: replayFrameProbe.contentWindow,
        data: {type: 'goat-ai-review-label-state', pending: false, saving: false}}));
      await new Promise(resolve => setTimeout(resolve, 0));
      const advancedAfterSave = document.getElementById('item-position').textContent === '2 / 2';
      document.body.dataset.queueProbe = [first, protectedItem, second, reveal,
        skipped, restored, noted, rejectionReviewed, waitedForSave, advancedAfterSave, prompts].join('|');
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
    assert match.group(1) == "1 / 2|1 / 2|2 / 2|true|true|true|true|true|true|true|0"
