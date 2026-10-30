"""Browser checks for the live duel controls that replace legal-action lists."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_optional_effect_decline_is_not_labeled_as_pass(tmp_path):
    page = Path(__file__).resolve().parents[1] / "examples/play_game.html"
    probe = """<script>
      const observation = {turn:1,turn_player:0,acting_player:0,phase:'end',
        life_points:[8000,8000],extra_deck_counts:[0,0],deck_counts:[35,35],
        hand:[],opponent_hand_count:5,field:[],graveyards:[[],[]],banished:[[],[]],
        known_opponent_hand_cards:[],known_opponent_field_cards:[],own_extra_deck:[],
        restrictions:[],chain:[],public_history:[]};
      const wrap = actions => ({id:'test',terminal:false,human_seat:0,decisions:0,
        observation,legal_actions:actions,card_names:{}});
      setTimeout(() => {
        render(wrap([{kind:'no',parameters:{}},{kind:'yes',parameters:{}}]));
        const effect = byId('pass-action').hidden && byId('end-turn').disabled &&
          [...document.querySelectorAll('#choice-dialog button')].some(button =>
            button.textContent.includes('No'));
        render(wrap([{kind:'cancel',parameters:{}},
          {kind:'select_card',parameters:{code:123,location:2,controller:0,sequence:0}}]));
        const selection = byId('pass-action').hidden && byId('end-turn').disabled;
        render(wrap([{kind:'pass',parameters:{}}]));
        const forced = byId('pass-action').hidden;
        byId('hold-priority').checked = true;
        render(wrap([{kind:'chain',parameters:{code:123}},
          {kind:'pass',parameters:{}}]));
        document.body.dataset.passLabelProbe =
          [effect,selection,forced,!byId('pass-action').hidden].join('|');
      },40);
    </script></body>"""
    html = tmp_path / "live.html"
    html.write_text(page.read_text().replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=650", "--dump-dom",
        html.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-pass-label-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "true|true|true|true"


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
          const request = JSON.parse(options.body);
          sent.push(request.action_index + ':' + request.manual);
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
    assert match.group(1) == "0:true,0:false,1:false|3|true"


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


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_own_set_card_previews_face_without_revealing_opponent_set(tmp_path):
    page = Path(__file__).resolve().parents[1] / "examples/play_game.html"
    probe = """<script>
      const observation = {turn:1,turn_player:0,acting_player:0,phase:'main1',
        life_points:[8000,8000],extra_deck_counts:[0,0],deck_counts:[35,35],
        hand:[],opponent_hand_count:5,
        field:[{code:101,controller:0,zone:'monster',sequence:0,
          position:'facedown',orientation:'defense'},
          {code:null,controller:1,zone:'monster',sequence:0,
          position:'facedown',orientation:'defense'}],
        graveyards:[[],[]],banished:[[],[]],known_opponent_hand_cards:[],
        known_opponent_field_cards:[],own_extra_deck:[],restrictions:[],
        chain:[],public_history:[]};
      window.fetch = async () => { throw new Error('probe only'); };
      setTimeout(() => {
        render({id:'test',terminal:false,decisions:0,human_seat:0,
          observation,legal_actions:[{kind:'end_phase',parameters:{}}],
          card_names:{101:'Known Set Monster'}});
        const own = document.querySelector('#own-monster .card');
        const opponent = document.querySelector('#opp-monster .card');
        own.dispatchEvent(new Event('pointerover',{bubbles:true}));
        const preview = byId('card-preview');
        const ownVisible = !preview.hidden &&
          preview.querySelector('img')?.getAttribute('src') ===
            '/replays/card_images/101.jpg';
        own.dispatchEvent(new Event('pointerout',{bubbles:true}));
        opponent.dispatchEvent(new Event('pointerover',{bubbles:true}));
        document.body.dataset.previewProbe = [ownVisible,preview.hidden,
          own.dataset.previewCode,opponent.dataset.previewCode || 'hidden'].join('|');
      }, 60);
    </script></body>"""
    html = tmp_path / "live.html"
    html.write_text(page.read_text().replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=650", "--dump-dom",
        html.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-preview-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "true|true|101|hidden"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_old_server_page_auto_passes_consecutive_response_windows(tmp_path):
    page = Path(__file__).resolve().parents[1] / "examples/play_game.html"
    probe = """<script>
      const observation = {turn:1,turn_player:0,acting_player:0,phase:'draw',
        life_points:[8000,8000],extra_deck_counts:[0,0],deck_counts:[35,35],
        hand:[],opponent_hand_count:5,field:[],graveyards:[[],[]],banished:[[],[]],
        known_opponent_hand_cards:[],known_opponent_field_cards:[],
        own_extra_deck:[],restrictions:[],chain:[],public_history:[]};
      const pass = {kind:'pass',parameters:{}};
      const chain = {kind:'chain',parameters:{code:101}};
      const wrap = (decisions, legal_actions) => ({id:'old-server',terminal:false,
        human_seat:0,decisions,observation,legal_actions,card_names:{101:'Quick effect'}});
      const replies = [wrap(1,[pass]),{
        ...wrap(2,[chain,pass]),observation:{...observation,turn_player:1}},
        wrap(3,[{kind:'end_phase',parameters:{}}])];
      const sent = [];
      window.fetch = async (path, options) => {
        if (path === '/api/live/choice') {
          const request = JSON.parse(options.body);
          sent.push(request.action_index + '@' + request.expected_decisions +
            ':' + request.manual);
          return {ok:true,json:async () => replies.shift()};
        }
        throw new Error('probe only');
      };
      setTimeout(() => render(wrap(0,[pass])), 40);
      setTimeout(() => { document.body.dataset.forcedPassProbe =
        [sent.join(','),state.decisions,state.legal_actions.length].join('|'); }, 280);
    </script></body>"""
    html = tmp_path / "live.html"
    html.write_text(page.read_text().replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=700", "--dump-dom",
        html.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-forced-pass-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "0@0:false,0@1:false,1@2:false|3|1"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_optional_chain_auto_passes_on_both_turns_unless_paused(tmp_path):
    page = Path(__file__).resolve().parents[1] / "examples/play_game.html"
    probe = """<script>
      const observation = {turn:1,turn_player:0,acting_player:0,phase:'main1',
        life_points:[8000,8000],extra_deck_counts:[0,0],deck_counts:[35,35],
        hand:[],opponent_hand_count:5,field:[],graveyards:[[],[]],banished:[[],[]],
        known_opponent_hand_cards:[],known_opponent_field_cards:[],own_extra_deck:[],
        restrictions:[],chain:[],public_history:[]};
      const pass = {kind:'pass',parameters:{}};
      const chain = {kind:'chain',parameters:{code:101}};
      const wrap = (id, decisions, observation, legal_actions) => ({id,
        terminal:false,human_seat:0,decisions,observation,legal_actions,
        card_names:{101:'Quick effect'}});
      const sent = [];
      window.fetch = async (path, options) => {
        if (path !== '/api/live/choice') throw new Error('probe only');
        const request = JSON.parse(options.body);
        sent.push(request.id + ':' + request.action_index + ':' + request.manual +
          ':' + request.hold_priority);
        return {ok:true,json:async () => wrap(request.id,1,observation,
          [{kind:'end_phase',parameters:{}}])};
      };
      setTimeout(() => render(wrap('own',0,observation,[chain,pass])),40);
      setTimeout(() => {
        byId('hold-priority').checked = true;
        render(wrap('hold',0,{...observation,turn_player:1,
          chain:[{controller:1,card_code:102}]},[chain,pass]));
      },120);
      setTimeout(() => {
        byId('hold-priority').checked = false;
        render(wrap('opponent',0,{...observation,turn_player:1,
          chain:[{controller:1,card_code:102}]},[chain,pass]));
      },200);
      setTimeout(() => { document.body.dataset.optionalPassProbe = sent.join(','); },300);
    </script></body>"""
    html = tmp_path / "live.html"
    html.write_text(page.read_text().replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=750", "--dump-dom",
        html.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-optional-pass-probe="([^"]*)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "own:1:false:false,opponent:1:false:false"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_choice_resolves_consecutive_pass_windows_before_showing_board(tmp_path):
    page = Path(__file__).resolve().parents[1] / "examples/play_game.html"
    probe = """<script>
      const observation = {turn:1,turn_player:0,acting_player:0,phase:'main1',
        life_points:[8000,8000],extra_deck_counts:[0,0],deck_counts:[35,35],
        hand:[],opponent_hand_count:5,field:[],graveyards:[[],[]],banished:[[],[]],
        known_opponent_hand_cards:[],known_opponent_field_cards:[],own_extra_deck:[],
        restrictions:[],chain:[],public_history:[]};
      const action = kind => ({kind,parameters:{}});
      const wrap = (decisions, legal_actions) => ({id:'test',terminal:false,
        human_seat:0,decisions,observation,legal_actions,card_names:{}});
      const replies = [wrap(1,[action('pass')]),
        wrap(2,[action('chain'),action('pass')]),
        wrap(3,[action('pass')]),wrap(4,[action('end_phase')])];
      const sent = [];
      window.fetch = async (path, options) => {
        if (path !== '/api/live/choice') throw new Error('probe only');
        const request = JSON.parse(options.body);
        sent.push(request.action_index + ':' + request.manual);
        return {ok:true,json:async () => replies.shift()};
      };
      setTimeout(() => {
        render(wrap(0,[action('select_card')]));
        choose(0).then(() => { document.body.dataset.passesProbe =
          [sent.join(','),state.decisions,state.legal_actions[0].kind].join('|'); });
      },40);
    </script></body>"""
    html = tmp_path / "live.html"
    html.write_text(page.read_text().replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=650", "--dump-dom",
        html.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-passes-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "0:true,0:false,1:false,0:false|4|end_phase"
