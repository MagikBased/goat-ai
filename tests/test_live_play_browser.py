"""Exercise live duel controls in a browser without a native game session."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_card_actions_phase_and_drag_destination(tmp_path):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const observation = {viewer:0, acting_player:0, turn_player:0, turn:2,
        phase:'main1', life_points:[8000,8000], hand:[{code:123,sequence:0}], field:[],
        graveyards:[[],[]], banished:[[],[]], extra_deck_counts:[0,0],
        deck_counts:[34,35], opponent_hand_count:5, public_history:[],
        known_opponent_hand_cards:[], known_opponent_field_cards:[],
        own_extra_deck:[], restrictions:[], chain:[]};
      const action = (kind, parameters = {}) => ({kind, parameters, actor:0, id:kind});
      const source = {code:123, location:2, controller:0, sequence:0};
      const initial = {id:'1234567890abcdef', human_seat:0, decisions:0,
        terminal:false, observation, card_names:{123:'Test Monster'},
        legal_actions:[action('normal_summon',source), action('set_monster',source),
          action('battle_phase'), action('end_phase')]};
      render(initial);
      document.querySelector('#own-hand .card').click();
      const cardButtons = [...document.querySelectorAll('#card-actions button')]
        .map(button => button.textContent);
      contextActions(source, document.querySelector('#own-monster .zone'),
        {location:4, controller:0, sequence:2});
      const dropButtons = [...document.querySelectorAll('#card-actions button')]
        .map(button => button.textContent);
      const phases = [...document.querySelectorAll('#phase button')]
        .filter(button => !button.disabled).map(button => button.textContent);
      const submitted = [];
      window.fetch = async (_path, options) => {
        const choice = JSON.parse(options.body);
        submitted.push(choice.action_index);
        if (choice.expected_decisions === 0) return new Response(JSON.stringify({
          ...initial, decisions:1, legal_actions:[
            action('place',{location:4,controller:0,sequence:0}),
            action('place',{location:4,controller:0,sequence:1}),
            action('place',{location:4,controller:0,sequence:2})]}));
        document.body.dataset.chosenPlace = String(choice.action_index);
        return new Response(JSON.stringify({...initial, decisions:2,
          observation:{...observation, phase:'main1'},
          legal_actions:[action('end_phase')]}));
      };
      choose(0, {location:4, controller:0, sequence:2}).then(() => {
        const canEnd = !document.querySelector('#end-turn').disabled;
        const destinationChoice = document.body.dataset.chosenPlace;
        document.querySelector('#end-turn').click();
        setTimeout(() => { document.body.dataset.playProbe = [cardButtons.join(','),
          dropButtons.join(','), phases.join(','),
          destinationChoice,
          canEnd, submitted.join(',')].join('|'); }, 0);
      });
    </script></body>"""
    path = tmp_path / "live_play.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=1200", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-play-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "Summon,Set,×|Summon,Set,×|BP,EP|2|true|0,2,0"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_drag_highlights_only_legal_targets_and_missing_art_keeps_name(tmp_path):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const own = {controller:0,zone:'monster',sequence:0,code:123,
        position:'faceup',orientation:'attack'};
      const enemy = {controller:1,zone:'monster',sequence:2,code:456,
        position:'faceup',orientation:'attack'};
      render({id:'1234567890abcdef',human_seat:0,decisions:0,terminal:false,
        card_names:{123:'Own Monster',456:'Enemy Monster'},
        observation:{viewer:0,acting_player:0,turn_player:0,turn:2,phase:'battle',
          life_points:[8000,8000],hand:[],field:[own,enemy],graveyards:[[],[]],
          banished:[[],[]],extra_deck_counts:[0,0],deck_counts:[34,35],
          opponent_hand_count:0,public_history:[],known_opponent_hand_cards:[],
          known_opponent_field_cards:[],own_extra_deck:[],restrictions:[],chain:[]},
        legal_actions:[{id:'0',kind:'attack',actor:0,
          parameters:{code:123,controller:0,location:4,sequence:0}}]});
      const card = document.querySelector('#own-monster .card');
      const start = new Event('dragstart', {bubbles:true});
      Object.defineProperty(start,'dataTransfer',{value:{effectAllowed:'',setData(){}}});
      card.dispatchEvent(start);
      const targets = [...document.querySelectorAll('.drop-target')];
      const enemyTarget = document.querySelector('#opp-monster .zone:nth-child(4)');
      const emptyTarget = document.querySelector('#opp-monster .zone:nth-child(3)');
      const over = new Event('dragover', {bubbles:true,cancelable:true});
      emptyTarget.dispatchEvent(over);
      const invalidPrevented = over.defaultPrevented;
      enemyTarget.dispatchEvent(new Event('drop', {bubbles:true,cancelable:true}));
      const buttons = [...document.querySelectorAll('#card-actions button')]
        .map(button => button.textContent);
      const image = card.querySelector('img'); image.dispatchEvent(new Event('error'));
      document.body.dataset.dragProbe = [targets.length,
        targets[0] === enemyTarget,invalidPrevented,buttons.join(','),
        card.textContent.includes('Own Monster · art unavailable')].join('|');
    </script></body>"""
    path = tmp_path / "live_drag.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=1200", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-drag-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "1|true|false|Attack,×|true"
