"""Browser checks for the live duel controls that replace legal-action lists."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_graceful_discard_cards_can_be_selected_on_hand(tmp_path):
    page = Path(__file__).resolve().parents[1] / "examples/play_game.html"
    probe = """<script>
      const observation = {turn:1, turn_player:0, acting_player:0, phase:'main1',
        life_points:[8000,8000], extra_deck_counts:[0,0], deck_counts:[30,30],
        hand:[{code:101,sequence:0},{code:102,sequence:1},{code:103,sequence:2}],
        opponent_hand_count:5, field:[], graveyards:[[],[]], banished:[[],[]],
        known_opponent_hand_cards:[], known_opponent_field_cards:[], own_extra_deck:[],
        restrictions:[], chain:[], public_history:[]};
      const card = (code, sequence) => ({code,controller:0,location:2,sequence});
      const choice = (cards) => ({kind:'select_cards', parameters:{cards}});
      const legal = [choice([card(101,0),card(102,1)]),
                     choice([card(101,0),card(103,2)]),
                     choice([card(102,1),card(103,2)])];
      let chosen = null;
      window.fetch = async (path, options) => {
        if (path === '/api/live/choice') {
          chosen = JSON.parse(options.body).action_index;
          return {ok:true,json:async () => ({id:'test',terminal:true,decisions:1,winner:0})};
        }
        throw new Error('probe only');
      };
      setTimeout(() => {
        render({id:'test',terminal:false,decisions:0,human_seat:0,
          observation,legal_actions:legal,card_names:{101:'A',102:'B',103:'C'}});
        const cards = document.querySelectorAll('#own-hand .card');
        cards[0].click(); cards[2].click();
        const ready = !byId('confirm-cards').disabled &&
          cards[0].classList.contains('selected') &&
          cards[2].classList.contains('selected');
        byId('confirm-cards').click();
        setTimeout(() => { document.body.dataset.selectionProbe =
          [ready,chosen,byId('card-selection').hidden].join('|'); }, 60);
      }, 60);
    </script></body>"""
    html = tmp_path / "live.html"
    html.write_text(page.read_text().replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=650", "--dump-dom",
        html.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-selection-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "true|1|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_set_monster_auto_places_and_passes_own_response_window(tmp_path):
    page = Path(__file__).resolve().parents[1] / "examples/play_game.html"
    probe = """<script>
      const observation = {turn:1, turn_player:0, acting_player:0, phase:'main1',
        life_points:[8000,8000], extra_deck_counts:[0,0], deck_counts:[35,35],
        hand:[{code:101,sequence:0}], opponent_hand_count:5, field:[],
        graveyards:[[],[]], banished:[[],[]], known_opponent_hand_cards:[],
        known_opponent_field_cards:[], own_extra_deck:[], restrictions:[],
        chain:[], public_history:[]};
      const wrap = (decisions, legal_actions) => ({id:'test',terminal:false,
        human_seat:0,decisions,observation,legal_actions,card_names:{101:'A'}});
      const set = {kind:'set_monster',parameters:{code:101,controller:0,
        location:2,sequence:0}};
      const place = {kind:'place',parameters:{controller:0,location:4,sequence:0}};
      const pass = {kind:'pass',parameters:{}};
      const chain = {kind:'chain',parameters:{code:101}};
      const responses = [wrap(1,[place]),wrap(2,[chain,pass]),
        wrap(3,[{kind:'end_phase',parameters:{}}])];
      const sent = [];
      window.fetch = async (path, options) => {
        if (path === '/api/live/choice') {
          sent.push(JSON.parse(options.body).action_index);
          return {ok:true,json:async () => responses.shift()};
        }
        throw new Error('probe only');
      };
      setTimeout(() => {
        render(wrap(0,[set]));
        choose(0).then(() => { document.body.dataset.placementProbe =
          [sent.join(','),state.decisions,byId('auto-place').checked].join('|'); });
      }, 60);
    </script></body>"""
    html = tmp_path / "live.html"
    html.write_text(page.read_text().replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=650", "--dump-dom",
        html.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-placement-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "0,0,1|3|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_manual_zone_toggle_leaves_placement_choice_for_player(tmp_path):
    page = Path(__file__).resolve().parents[1] / "examples/play_game.html"
    probe = """<script>
      const observation = {turn:1,turn_player:0,acting_player:0,phase:'main1',
        life_points:[8000,8000],extra_deck_counts:[0,0],deck_counts:[35,35],
        hand:[{code:101,sequence:0}],opponent_hand_count:5,field:[],
        graveyards:[[],[]],banished:[[],[]],known_opponent_hand_cards:[],
        known_opponent_field_cards:[],own_extra_deck:[],restrictions:[],
        chain:[],public_history:[]};
      const wrap = (decisions, legal_actions) => ({id:'test',terminal:false,
        human_seat:0,decisions,observation,legal_actions,card_names:{101:'A'}});
      const sent = [];
      window.fetch = async (path, options) => {
        if (path === '/api/live/choice') {
          sent.push(JSON.parse(options.body).action_index);
          return {ok:true,json:async () => wrap(1,[
            {kind:'place',parameters:{controller:0,location:4,sequence:0}},
            {kind:'place',parameters:{controller:0,location:4,sequence:1}}])};
        }
        throw new Error('probe only');
      };
      setTimeout(() => {
        render(wrap(0,[{kind:'set_monster',parameters:{code:101,controller:0,
          location:2,sequence:0}}]));
        byId('auto-place').checked = false;
        choose(0).then(() => { document.body.dataset.manualProbe =
          [sent.join(','),state.decisions,state.legal_actions.length].join('|'); });
      }, 60);
    </script></body>"""
    html = tmp_path / "live.html"
    html.write_text(page.read_text().replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=650", "--dump-dom",
        html.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-manual-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "0|1|2"
