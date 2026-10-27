"""Exercise replay animations in a real browser when Chromium is available."""

import re
import shutil
import subprocess
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
