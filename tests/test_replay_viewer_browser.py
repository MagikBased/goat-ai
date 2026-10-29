"""Exercise replay animations in a real browser when Chromium is available."""

import re
import shutil
import subprocess
from copy import deepcopy

import pytest

from scripts.render_replay import _embed_viewer


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_spell_counter_badge_tracks_public_count_and_hover_preview(tmp_path):
    first = _observation()
    first["field"][0]["counters"] = [[1, 1]]
    second = deepcopy(first)
    second["field"][0]["counters"] = [[1, 2], [2, 1]]
    third = deepcopy(second)
    third["field"][0]["position"] = "facedown"
    fourth = deepcopy(first)
    fourth["field"][0]["counters"] = [[2, 1]]
    action = {"id": "pass", "kind": "pass", "actor": 0, "parameters": {}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": observation, "selected_action": action,
         "legal_actions": [action]} for observation in (first, second, third, fourth)]}
    html = _embed_viewer(replay, "0" * 64, {1: "Breaker"}, {}, {})
    probe = """<script>
      const badge = () => document.querySelector('#board .spell-counter-badge');
      const first = badge()?.getAttribute('aria-label');
      showCardPreview(badge().closest('.card'));
      const preview = document.querySelector('#hand-preview .spell-counter-badge')
        ?.getAttribute('aria-label');
      goatAiNavigateToDecision(2);
      const second = badge()?.getAttribute('aria-label');
      goatAiNavigateToDecision(3);
      const hidden = badge() === null;
      goatAiNavigateToDecision(4);
      const otherType = badge() === null;
      document.body.dataset.spellCounterProbe =
        [first, preview, second, hidden, otherType].join('|');
    </script></body>"""
    path = tmp_path / "spell_counter.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-spell-counter-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "1 Spell Counter|1 Spell Counter|2 Spell Counters|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_faceup_monster_effect_has_burst_without_replaying_on_same_frame(tmp_path):
    faceup = _observation()
    facedown = deepcopy(faceup)
    facedown["field"][0]["position"] = "facedown"
    effect = {"id": "effect", "kind": "activate", "actor": 0,
              "parameters": {"controller": 0, "location": 4,
                             "sequence": 0, "code": 1}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": faceup, "selected_action": effect,
         "legal_actions": [effect]},
        {"observation": facedown, "selected_action": effect,
         "legal_actions": [effect]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {1: "Breaker"}, {}, {})
    probe = """<script>
      const count = () => document.querySelectorAll('#board .effect-burst').length;
      const first = count();
      render(); const sameFrame = count();
      goatAiNavigateToDecision(2); const facedown = count();
      goatAiNavigateToDecision(1); const returned = count();
      document.body.dataset.effectProbe = [first, sameFrame, facedown, returned].join('|');
    </script></body>"""
    path = tmp_path / "effect_burst.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-effect-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "1|0|0|1"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_faceup_spell_trap_effect_has_burst(tmp_path):
    observation = _observation()
    observation["field"].append({"controller": 0, "zone": "spell_trap",
                                 "sequence": 0, "code": 3, "position": "faceup"})
    effect = {"id": "effect", "kind": "activate", "actor": 0,
              "parameters": {"controller": 0, "location": 8,
                             "sequence": 0, "code": 3}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": observation, "selected_action": effect,
         "legal_actions": [effect]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {3: "Continuous Spell"}, {}, {})
    probe = """<script>
      document.body.dataset.effectProbe =
        document.querySelectorAll('#board .effect-burst').length;
    </script></body>"""
    path = tmp_path / "spell_effect_burst.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-effect-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "1"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_reviewer_deck_popup_shows_remaining_cards_top_first(tmp_path):
    observation = _observation()
    observation["deck_counts"] = [3, 2]
    action = {"id": "pass", "kind": "pass", "actor": 0, "parameters": {}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": observation, "selected_action": action,
         "legal_actions": [action]},
    ]}
    reviewer = {"schema_version": 1, "source_trajectory_sha256": "0" * 64,
                "frames": [{"hands": [[], []], "field": {}, "banished": [[], []],
                            "extra": [[], []], "decks": [[11, 22, 33], [44, 55]],
                            "remaining_decks": [[11, 22, 11], [55, 44]]}]}
    html = _embed_viewer(replay, "0" * 64,
                         {11: "Alpha", 22: "Beta", 44: "Delta", 55: "Echo"},
                         {}, {}, reviewer)
    probe = """<script>
      document.querySelector('[data-deck-player="0"]').click();
      const first = [...document.querySelectorAll('#pile-scroll .pile-card-caption')]
        .map(card => card.textContent);
      const note = byId('pile-note').textContent;
      byId('pile-close').click();
      document.querySelector('[data-deck-player="1"]').click();
      const second = [...document.querySelectorAll('#pile-scroll .pile-card-caption')]
        .map(card => card.textContent);
      document.body.dataset.deckOrder = [first.join(','), second.join(','),
        note.includes('top card first')].join('|');
    </script></body>"""
    path = tmp_path / "ordered_decks.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-deck-order="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "1. Alpha,2. Beta,3. Alpha|1. Echo,2. Delta|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_hash_only_navigation_updates_board_after_label(tmp_path):
    first = _observation()
    second = deepcopy(first)
    second["turn"] = 2
    action = {"id": "pass", "kind": "pass", "actor": 0, "parameters": {}}
    other = {"id": "end", "kind": "end_phase", "actor": 0, "parameters": {}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": first, "selected_action": action,
         "legal_actions": [action, other]},
        {"observation": second, "selected_action": action,
         "legal_actions": [action, other]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {}, {}, {})
    probe = """<script>
      annotations.set(0, 1); labelsExported = true;
      location.hash = '#decision=2';
      setTimeout(() => { document.body.dataset.hashNav = [index,
        byId('jump').value, byId('turn').textContent.includes('Turn 2'),
        annotations.get(0)].join('|'); }, 100);
    </script></body>"""
    path = tmp_path / "same_replay_nav.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-hash-nav="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "1|2|true|1"


def _observation(*, life=9000, target_on_field=True, pending_attack=False,
                 destination="graveyards"):
    attacker = {"controller": 0, "zone": "monster", "sequence": 0,
                "code": 1, "position": "faceup", "orientation": "attack"}
    target = {"controller": 1, "zone": "monster", "sequence": 0,
              "code": 2, "position": "faceup", "orientation": "attack"}
    return {
        "viewer": 0, "acting_player": 0, "turn": 1, "turn_player": 0,
        "phase": "battle", "life_points": [life, 8000], "hand": [],
        "field": [attacker, target] if target_on_field else [attacker],
        "graveyards": [[], [target] if not target_on_field and destination == "graveyards" else []],
        "banished": [[], [target] if not target_on_field and destination == "banished" else []],
        "opponent_hand_count": 0,
        "deck_counts": [35, 35], "extra_deck_counts": [0, 0],
        "chain": [], "public_history": [], "restrictions": [],
        "pending_attack": {"controller": 0, "zone": "monster", "sequence": 0}
        if pending_attack else None,
    }


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_inspecting_ai_played_row_does_not_create_review_label(tmp_path):
    first = {"id": "played", "kind": "battle_phase", "actor": 0, "parameters": {}}
    other = {"id": "other", "kind": "end_phase", "actor": 0, "parameters": {}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": _observation(), "selected_action": first,
         "legal_actions": [first, other]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {}, {}, {})
    probe = """<script>
      const played = document.querySelector('#legal button.recorded');
      played.click();
      const inspected = annotations.size === 0 &&
        byId('review-instructions').textContent.includes('Use Approve AI-played action');
      document.querySelector('#legal button:not(.recorded)').click();
      const alternativeSaved = annotations.get(0) === 1;
      byId('clear-label').click();
      byId('label-recorded').click();
      document.body.dataset.reviewProbe = [inspected, alternativeSaved,
        annotations.get(0) === 0].join('|');
    </script></body>"""
    path = tmp_path / "review_clicks.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=300", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-review-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_local_review_only_enables_decisions_offered_by_queue(tmp_path):
    played = {"id": "played", "kind": "battle_phase", "actor": 0, "parameters": {}}
    other = {"id": "other", "kind": "end_phase", "actor": 0, "parameters": {}}
    decision = {"observation": _observation(), "selected_action": played,
                "legal_actions": [played, other]}
    replay = {"seed": 1, "source": "test", "winner": 0,
              "decisions": [decision, decision]}
    html = _embed_viewer(replay, "0" * 64, {}, {}, {})
    probe = """<script>
      localReviewMode = true;
      localReviewableFrames = new Set([0]);
      labelsExported = true;
      index = 0; render();
      const offered = !byId('choose-alternative').hidden &&
        !document.querySelector('#legal button:not(.recorded)').disabled;
      index = 1; render();
      const blocked = byId('choose-alternative').hidden &&
        document.querySelector('#legal button:not(.recorded)').disabled &&
        byId('annotation-status').textContent.includes('Outside this review queue');
      document.body.dataset.offeredProbe = [offered, blocked].join('|');
    </script></body>"""
    path = tmp_path / "offered_frames.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=300", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-offered-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_offline_queue_does_not_offer_unsavable_action_labels(tmp_path):
    played = {"id": "played", "kind": "battle_phase", "actor": 0, "parameters": {}}
    other = {"id": "other", "kind": "end_phase", "actor": 0, "parameters": {}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": _observation(), "selected_action": played,
         "legal_actions": [played, other]},
    ]}
    viewer = tmp_path / "viewer.html"
    viewer_html = _embed_viewer(replay, "0" * 64, {}, {}, {})
    probe = """<script>setTimeout(() => {
      const alternative = document.querySelector('#legal button:not(.recorded)');
      alternative.click();
      parent.postMessage({type: 'offline-probe', result: [
        alternative.disabled,
        document.getElementById('choose-alternative').hidden,
        document.getElementById('review-instructions').textContent.includes(
          'This queue is open as a file'),
        annotations.size === 0,
        !goatAiReviewNavigationState().pending].join('|')}, '*');
    }, 100)</script></body>"""
    viewer.write_text(viewer_html.replace("</body>", probe), encoding="utf-8")
    queue = tmp_path / "queue.html"
    queue.write_text("""<iframe id="viewer" src="viewer.html"></iframe><script>
      window.addEventListener('message', event => {
        if (event.data?.type === 'offline-probe')
          document.body.dataset.offlineProbe = event.data.result;
      });
    </script>""", encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        queue.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-offline-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "true|true|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_failed_clear_can_be_retried_without_exporting_empty_labels(tmp_path):
    played = {"id": "played", "kind": "battle_phase", "actor": 0, "parameters": {}}
    other = {"id": "other", "kind": "end_phase", "actor": 0, "parameters": {}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": _observation(), "selected_action": played,
         "legal_actions": [played, other]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {}, {}, {})
    probe = """<script>
      (async () => {
        localReviewMode = true; localReviewableFrames = new Set([0]);
        annotations.set(0, 1); labelsExported = true; render();
        let calls = 0;
        window.fetch = async () => ({ok: ++calls > 1,
          json: async () => calls > 1 ? {saved: true} : {error: 'temporary failure'}});
        byId('clear-label').click();
        await saveQueue;
        const failed = saveError && !labelsExported &&
          byId('clear-label').textContent === 'Retry clear' &&
          !byId('clear-label').disabled && byId('manual-review-export').hidden;
        byId('clear-label').click();
        await saveQueue;
        document.body.dataset.clearProbe = [failed, calls === 2,
          !saveError, labelsExported, annotations.size === 0].join('|');
      })();
    </script></body>"""
    path = tmp_path / "retry_clear.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=300", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-clear-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "true|true|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_outdated_local_review_server_disables_unsavable_choices(tmp_path):
    played = {"id": "played", "kind": "battle_phase", "actor": 0, "parameters": {}}
    other = {"id": "other", "kind": "end_phase", "actor": 0, "parameters": {}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": _observation(), "selected_action": played,
         "legal_actions": [played, other]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {}, {}, {})
    probe = """<script>
      // This server can return review state but predates the save protocol.
      window.fetch = async path => ({ok: true, json: async () =>
        path === '/api/review/version' ? {api_version: 1} :
        {choices: [], offered: [0], saved: true}});
      loadLocalReview('0'.repeat(64)).then(() => {
        document.body.dataset.outdatedProbe = [localReviewUnavailable,
          byId('choose-alternative').hidden,
          document.querySelector('#legal button:not(.recorded)').disabled,
          byId('review-instructions').textContent.includes('outdated')].join('|');
      });
    </script></body>"""
    path = tmp_path / "outdated_server.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=300", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-outdated-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "true|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_search_selects_alternative_beyond_first_100_actions(tmp_path):
    played = {"id": "played", "kind": "pass", "actor": 0, "parameters": {}}
    alternatives = [
        {"id": f"choice-{number}", "kind": "announce_number", "actor": 0,
         "parameters": {"number": number}}
        for number in range(150)
    ]
    alternatives[-1]["parameters"]["number"] = 7777
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": _observation(), "selected_action": played,
         "legal_actions": [played, *alternatives]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {}, {}, {})
    probe = """<script>
      const initial = document.querySelectorAll('#legal li').length === 100;
      byId('choose-alternative').click();
      const opened = byId('legal-details').open &&
        document.activeElement === byId('legal-filter');
      const filter = byId('legal-filter');
      filter.value = '7777';
      filter.dispatchEvent(new Event('input', {bubbles: true}));
      const found = document.querySelectorAll('#legal li').length === 1 &&
        byId('legal-filter-count').textContent === '1 matching action';
      document.querySelector('#legal button').click();
      document.body.dataset.searchProbe = [initial, opened, found,
        annotations.get(0) === 150,
        byId('annotation-status').textContent.includes('different from AI played')].join('|');
    </script></body>"""
    path = tmp_path / "search_actions.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=300", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-search-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "true|true|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
@pytest.mark.parametrize("destination", ["graveyards", "banished"])
def test_attack_target_life_fill_and_field_card_movement(tmp_path, destination):
    attack = {"id": "0", "kind": "attack", "actor": 0,
              "parameters": {"code": 1, "location": 4, "controller": 0, "sequence": 0}}
    target = {"id": "0", "kind": "select_card", "actor": 0,
              "parameters": {"code": 2, "location": 4, "controller": 1, "sequence": 0}}
    passed = {"id": "0", "kind": "pass", "actor": 0, "parameters": {}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": _observation(), "selected_action": attack,
         "legal_actions": [attack]},
        {"observation": _observation(pending_attack=True),
         "selected_action": target, "legal_actions": [target]},
        {"observation": _observation(life=7000, target_on_field=False,
                                      destination=destination),
         "selected_action": passed, "legal_actions": [passed]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {1: "Attacker", 2: "Target"}, {}, {})
    probe = """<script>
      byId('skip').checked = false;
      index = 1; render();
      const arrow = Boolean(document.querySelector('.attack-line'));
      const corners = Boolean(document.querySelector('.target-marker'));
      move(1);
      const travel = Boolean(document.querySelector('.travel-card'));
      const destinationWaits = Boolean(document.querySelector('.incoming-pile'));
      const noChainBadge = !document.querySelector('.chain-link-badge');
      setTimeout(() => {
        const life = document.querySelector('.life[data-player="0"]');
        document.body.dataset.animationProbe = [arrow, corners, travel,
          destinationWaits, !document.querySelector('.incoming-pile'), noChainBadge,
          lifeFraction(12000) === 1, life.querySelector('.life-value').textContent,
          life.querySelector('.life-fill').style.width].join('|');
      }, 650);
    </script></body>"""
    path = tmp_path / "animation.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=850", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-animation-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "true|true|true|true|true|true|true|7000 LP|87.5%"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_skip_passes_keeps_newly_chained_trap_face_up(tmp_path):
    first = _observation()
    first["field"] = [
        {"controller": 0, "zone": "spell_trap", "sequence": 0,
         "code": 1, "position": "faceup"},
        {"controller": 1, "zone": "spell_trap", "sequence": 0,
         "code": None, "position": "facedown"},
    ]
    first["chain"] = [{"index": 1, "card_code": 1, "controller": 0,
                       "location": 8, "sequence": 0, "targets": []}]
    second = deepcopy(first)
    third = deepcopy(first)
    third["field"][1].update(code=2, position="faceup")
    third["chain"].append({"index": 2, "card_code": 2, "controller": 1,
                           "location": 8, "sequence": 0, "targets": []})
    passed = {"id": "pass", "kind": "pass", "actor": 0, "parameters": {}}
    chained = {"id": "chain", "kind": "chain", "actor": 1,
               "parameters": {"code": 2, "location": 8, "controller": 1, "sequence": 0}}
    replay = {"seed": 2, "source": "test", "winner": 0, "decisions": [
        {"observation": first, "selected_action": passed, "legal_actions": [passed]},
        {"observation": second, "selected_action": chained, "legal_actions": [chained]},
        {"observation": third, "selected_action": passed, "legal_actions": [passed]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {1: "First Trap", 2: "Second Trap"}, {}, {})
    probe = """<script>
      index = 1; render();
      move(1);
      const trap = document.querySelector('[data-field-key="1:spell_trap:0"]');
      document.body.dataset.chainProbe = [index, trap?.classList.contains('facedown'),
        trap?.title, document.querySelectorAll('.card-flip').length,
        document.querySelector('.chain-link-badge')?.getAttribute('aria-label'),
        document.querySelector('.chain-link-badge strong')?.textContent,
        Boolean(document.querySelector('.chain-link-badge svg path'))].join('|');
    </script></body>"""
    path = tmp_path / "chained_trap.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-chain-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "2|false|Second Trap|1|Chain Link 2: Second Trap|2|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_chain_links_follow_source_zones_and_piles_open_from_field(tmp_path):
    observation = _observation()
    observation["field"].append({"controller": 1, "zone": "spell_trap", "sequence": 0,
                                 "code": 3, "position": "faceup"})
    observation["chain"] = [
        {"index": 1, "card_code": 1, "controller": 0, "location": 4,
         "sequence": 0, "targets": []},
        {"index": 2, "card_code": 3, "controller": 1, "location": 8,
         "sequence": 0, "targets": []},
        {"index": 3, "card_code": 4, "controller": 0, "location": 16,
         "sequence": 0, "targets": []},
        {"index": 4, "card_code": 5, "controller": 1, "location": 32,
         "sequence": 0, "targets": []},
        {"index": 5, "card_code": 6, "controller": 0, "location": 8,
         "sequence": 5, "targets": []},
        {"index": 6, "card_code": 1, "controller": 0, "location": 4,
         "sequence": 0, "targets": []},
    ]
    action = {"id": "pass", "kind": "pass", "actor": 0, "parameters": {}}
    replay = {"seed": 2, "source": "test", "winner": 0, "decisions": [
        {"observation": observation, "selected_action": action,
         "legal_actions": [action]},
    ]}
    html = _embed_viewer(replay, "0" * 64,
                         {1: "Monster", 3: "Trap", 4: "GY effect",
                          5: "Banished effect", 6: "Field effect"}, {}, {})
    probe = """<script>
      const badges = [...document.querySelectorAll('.chain-link-badge')];
      const locations = badges.sort((a, b) => Number(a.querySelector('strong').textContent) -
        Number(b.querySelector('strong').textContent)).map(badge => {
        const parent = badge.closest('.slot');
        return parent?.dataset.zoneKind ?
          `${parent.dataset.zonePlayer}:${parent.dataset.zoneKind}:${parent.dataset.zoneSequence}` :
          parent?.dataset.graveyardPlayer != null ? `graveyard:${parent.dataset.graveyardPlayer}` :
          parent?.dataset.banishedPlayer != null ? `banished:${parent.dataset.banishedPlayer}` : 'unknown';
      });
      document.querySelector('[data-graveyard-player="0"]').click();
      const graveyardOpens = byId('pile-dialog').open && byId('pile-title').textContent.includes('Graveyard');
      byId('pile-close').click();
      document.querySelector('[data-deck-player="0"]').click();
      const deckOpens = byId('pile-dialog').open && byId('pile-title').textContent.includes('Deck');
      document.body.dataset.chainZones = [badges.length, locations.join(','),
        Boolean(document.querySelector('.centerline .chain-link-badge')),
        Boolean(byId('piles')), Boolean(byId('decklist')),
        graveyardOpens, deckOpens].join('|');
    </script></body>"""
    path = tmp_path / "chain_zones.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-chain-zones="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == (
        "6|0:monster:0,1:spell_trap:0,graveyard:0,banished:1,0:spell_trap:5,0:monster:0"
        "|false|false|false|true|true"
    )


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_board_seat_stays_fixed_when_decision_viewer_changes(tmp_path):
    first = _observation()
    second = deepcopy(first)
    second.update(viewer=1, acting_player=1, hand=[{"controller": 1,
                  "zone": "hand", "position": "hidden", "code": 3, "sequence": 0}],
                  opponent_hand_count=2)
    passed = {"id": "pass", "kind": "pass", "actor": 0, "parameters": {}}
    other_pass = {**passed, "actor": 1}
    replay = {"seed": 3, "source": "self_play_rl", "winner": 0,
              "skill_metadata": {"learner_seat": 0}, "decisions": [
        {"observation": first, "selected_action": passed, "legal_actions": [passed]},
        {"observation": second, "selected_action": other_pass,
         "legal_actions": [other_pass]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {1: "Attacker", 2: "Target", 3: "Hand"}, {}, {})
    probe = """<script>
      const seats = () => [...document.querySelectorAll('.duel-side')]
        .map(side => side.dataset.player).join(',');
      const first = seats();
      index = 1; render();
      const afterPass = seats();
      const bottomHandHidden = document.querySelector('.duel-side:last-child .hand-back') !== null;
      byId('board-seat').click();
      document.body.dataset.seatProbe = [first, afterPass, bottomHandHidden,
        seats(), byId('board-seat').textContent].join('|');
    </script></body>"""
    path = tmp_path / "fixed_seat.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-seat-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "1,0|1,0|true|0,1|P2 at bottom · Switch sides"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_skip_passes_does_not_stop_at_each_changed_board_view(tmp_path):
    first = _observation()
    other = deepcopy(first)
    other.update(viewer=1, acting_player=1, hand=[], opponent_hand_count=0)
    changed = deepcopy(first)
    changed["field"].append({"controller": 0, "zone": "spell_trap", "sequence": 0,
                             "code": 3, "position": "facedown"})
    other_changed = deepcopy(other)
    other_changed["field"] = deepcopy(changed["field"])
    other_changed["field"][-1]["code"] = None
    passed0 = {"id": "pass0", "kind": "pass", "actor": 0, "parameters": {}}
    passed1 = {"id": "pass1", "kind": "pass", "actor": 1, "parameters": {}}
    played0 = {"id": "play0", "kind": "activate", "actor": 0,
               "parameters": {"code": 1, "location": 4, "controller": 0, "sequence": 0}}
    played1 = {"id": "play1", "kind": "activate", "actor": 1,
               "parameters": {"code": 2, "location": 4, "controller": 1, "sequence": 0}}
    replay = {"seed": 4, "source": "test", "winner": 0, "decisions": [
        {"observation": first, "selected_action": played0, "legal_actions": [played0]},
        {"observation": other, "selected_action": passed1, "legal_actions": [passed1]},
        {"observation": changed, "selected_action": passed0, "legal_actions": [passed0]},
        {"observation": other_changed, "selected_action": passed1,
         "legal_actions": [passed1]},
        {"observation": changed, "selected_action": played0, "legal_actions": [played0]},
        {"observation": other_changed, "selected_action": played1,
         "legal_actions": [played1]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {1: "First", 2: "Second", 3: "Set"}, {}, {})
    probe = """<script>
      const seats = () => [...document.querySelectorAll('.duel-side')]
        .map(side => side.dataset.player).join(',');
      move(1);
      const first = [index, seats(), byId('action').textContent].join(':');
      move(1);
      document.body.dataset.passProbe = [first, index, seats(),
        byId('action').textContent].join('|');
    </script></body>"""
    path = tmp_path / "skip_pass_perspective.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-pass-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == (
        "4:1,0:activate · First · P1 Monster 1|5|1,0|"
        "activate · Second · P2 Monster 1")


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_perspective_change_does_not_animate_hidden_card_disclosure(tmp_path):
    first = _observation()
    first["field"] = [
        {"controller": 0, "zone": "spell_trap", "sequence": 0,
         "code": 3, "position": "facedown"},
        {"controller": 1, "zone": "spell_trap", "sequence": 0,
         "code": None, "position": "facedown"},
    ]
    other = deepcopy(first)
    other.update(viewer=1, acting_player=1)
    other["field"][0]["code"] = None
    other["field"][1]["code"] = 4
    actual_placement = deepcopy(other)
    actual_placement["field"].append({
        "controller": 1, "zone": "monster", "sequence": 0,
        "code": 5, "position": "faceup", "orientation": "attack"})
    actions = [{"id": str(i), "kind": "pass", "actor": player, "parameters": {}}
               for i, player in enumerate((0, 1, 1))]
    replay = {"seed": 5, "source": "test", "winner": 0, "decisions": [
        {"observation": observation, "selected_action": action,
         "legal_actions": [action]}
        for observation, action in zip((first, other, actual_placement), actions)
    ]}
    html = _embed_viewer(replay, "0" * 64, {3: "Set A", 4: "Set B", 5: "New"}, {}, {})
    probe = """<script>
      byId('skip').checked = false;
      move(1);
      const viewpointOnly = [index, document.querySelectorAll('.card-flip').length,
        document.querySelectorAll('.card-arrive').length,
        document.querySelectorAll('.travel-card').length].join(':');
      move(1);
      document.body.dataset.viewAnimationProbe = [viewpointOnly, index,
        document.querySelectorAll('.card-arrive').length].join('|');
    </script></body>"""
    path = tmp_path / "viewpoint_animation.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-view-animation-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "1:0:0:0|2|1"

@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_public_faceup_age_appears_on_card_hover(tmp_path):
    observation = _observation()
    observation["field"][0]["faceup_turns"] = 3
    action = {"id": "0", "kind": "pass", "actor": 0, "parameters": {}}
    replay = {"seed": 1, "source": "test", "winner": 0, "decisions": [
        {"observation": observation, "selected_action": action,
         "legal_actions": [action]},
    ]}
    html = _embed_viewer(replay, "0" * 64, {1: "Attacker", 2: "Target"}, {}, {})
    probe = """<script>
      const card = document.querySelector('.card[data-field-key="0:monster:0"]');
      document.body.dataset.ageProbe = card?.title.includes('Face-up for 3 turn boundaries')
        ? 'visible' : 'missing';
    </script></body>"""
    path = tmp_path / "public_age.html"
    path.write_text(html.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=300", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-age-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "visible"
