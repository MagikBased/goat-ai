"""Exercise replay animations in a real browser when Chromium is available."""

import re
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.render_replay import _embed_viewer


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
      setTimeout(() => {
        const life = document.querySelector('.life[data-player="0"]');
        document.body.dataset.animationProbe = [arrow, corners, travel,
          destinationWaits, !document.querySelector('.incoming-pile'),
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
    assert match.group(1) == "true|true|true|true|true|true|7000 LP|87.5%"


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
        trap?.title, document.querySelectorAll('.card-flip').length].join('|');
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
    assert match.group(1) == "2|false|Second Trap|1"


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
