"""Exercise live duel controls in a browser without a native game session."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_multiple_card_effect_modes_have_distinct_live_labels(tmp_path):
    page = Path(__file__).resolve().parents[1] / "examples/play_game.html"
    probe = """<script>
      const spell = {code:38275183,controller:0,location:8,sequence:0};
      const choices = [0,1].map(option => ({id:String(option),kind:'chain',actor:0,
        parameters:{...spell,effect_option:option}}));
      const observation = {turn:3,turn_player:1,acting_player:0,phase:'main1',
        life_points:[8000,8000],extra_deck_counts:[0,0],deck_counts:[30,30],
        hand:[],opponent_hand_count:5,field:[{code:38275183,controller:0,
          zone:'spell_trap',sequence:0,position:'facedown'}],
        graveyards:[[],[]],banished:[[],[]],known_opponent_hand_cards:[],
        known_opponent_field_cards:[],own_extra_deck:[],restrictions:[],
        chain:[{index:1,controller:1,card_code:14087893}],public_history:[]};
      setTimeout(() => {
        try {
          render({id:'test',terminal:false,decisions:0,human_seat:0,observation,
            legal_actions:choices,card_names:{38275183:'Spell Shield Type-8'},
            action_effect_texts:{0:'Negate a Spell targeting one monster',
              1:'Send a Spell from hand to negate a Spell'}});
          document.querySelector('#own-spell .card').click();
          const tray = [...document.querySelectorAll('#card-actions button.effect-choice')];
          const advanced = [...document.querySelectorAll('#action-list button')];
          document.body.dataset.effectProbe = [tray.length,
            tray[0].textContent.includes('targeting one monster'),
            tray[1].textContent.includes('Send a Spell'),
            advanced[0].textContent !== advanced[1].textContent].join('|');
        } catch(error) { document.body.dataset.effectProbe = error.message; }
      },60);
    </script></body>"""
    html = tmp_path / "effect_modes.html"
    html.write_text(page.read_text().replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=500", "--dump-dom",
        html.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-effect-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1000:]
    assert match.group(1) == "2|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
@pytest.mark.parametrize("width,height", [(1920, 1080), (800, 700)])
def test_setup_generates_seed_and_dice_replaces_invalid_value(tmp_path, width, height):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const field = document.getElementById('seed');
      const initial = Number(field.value);
      field.value = '-1';
      document.getElementById('roll-seed').click();
      const rolled = Number(field.value);
      const setup = document.getElementById('setup').getBoundingClientRect();
      const selectsFit = [...document.querySelectorAll('#setup select')].every(select => {
        const box = select.getBoundingClientRect();
        return box.left >= setup.left + 10 && box.right <= setup.right - 10;
      });
      document.body.dataset.seedProbe = [
        Number.isInteger(initial) && initial >= 0 && initial <= 4294967295,
        Number.isInteger(rolled) && rolled >= 0 && rolled <= 4294967295,
        field.checkValidity(),
        document.getElementById('roll-seed').type === 'button',
        selectsFit
      ].join('|');
    </script></body>"""
    path = tmp_path / "live_seed.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", f"--window-size={width},{height}",
        "--virtual-time-budget=1200", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-seed-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "true|true|true|true|true"


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
    assert match.group(1) == "Summon,Set,×|Summon,Set,×|BP,M2,EP|2|true|0,2,0"


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


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
@pytest.mark.parametrize("width,height", [(1920, 1080), (1365, 768), (1920, 600)])
def test_desktop_board_keeps_both_hands_and_card_art_in_view(tmp_path, width, height):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const hand = Array.from({length:5}, (_,sequence) => ({code:123,sequence}));
      render({id:'1234567890abcdef',human_seat:0,decisions:0,terminal:false,
        card_names:{123:'Test Monster'},
        observation:{viewer:0,acting_player:0,turn_player:0,turn:2,phase:'main1',
          life_points:[8000,8000],hand,field:[{controller:0,zone:'monster',
            sequence:0,code:123,position:'faceup',orientation:'attack'}],
          graveyards:[[],[]],banished:[[],[]],extra_deck_counts:[0,0],
          deck_counts:[34,35],opponent_hand_count:5,public_history:[],
          known_opponent_hand_cards:[],known_opponent_field_cards:[],
          own_extra_deck:[],restrictions:[],chain:[]},legal_actions:[]});
      const board = document.querySelector('#board').getBoundingClientRect();
      const ownHand = document.querySelector('#own-hand').getBoundingClientRect();
      const card = document.querySelector('#own-monster .card').getBoundingClientRect();
      const zoneRect = document.querySelector('#own-monster .zone:nth-child(2)').getBoundingClientRect();
      const handCard = document.querySelector('#own-hand .card').getBoundingClientRect();
      const rows = ['opp-spell','opp-monster','own-monster','own-spell'];
      const rowHeights = rows.map(id => document.getElementById(id).getBoundingClientRect().height);
      document.querySelectorAll('.card').forEach(element => element.remove());
      const emptyHeights = rows.map(id => document.getElementById(id).getBoundingClientRect().height);
      document.body.dataset.layoutProbe = [
        Math.round(board.bottom) <= window.innerHeight - 10,
        Math.round(ownHand.bottom) <= Math.round(board.bottom),
        card.height > 20 && card.height <= zoneRect.height,
        card.width > 10 && card.width <= zoneRect.width,
        handCard.height > ownHand.height && handCard.top >= ownHand.top,
        rowHeights.every((height,index) => Math.abs(height-emptyHeights[index]) < 1),
        document.documentElement.scrollHeight <= window.innerHeight + 1
      ].join('|');
    </script></body>"""
    path = tmp_path / f"live_layout_{width}_{height}.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", f"--window-size={width},{height}",
        "--virtual-time-budget=1200", "--dump-dom", path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-layout-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "true|true|true|true|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_live_piles_show_visible_cards_and_deck_back_without_hidden_identity(tmp_path):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      render({id:'1234567890abcdef',human_seat:0,decisions:0,terminal:false,
        card_names:{123:'Public Monster',456:'Private Card'},
        observation:{viewer:0,acting_player:0,turn_player:0,turn:2,phase:'main1',
          life_points:[8000,8000],hand:[],field:[],graveyards:[
            [{code:123,sequence:0,position:'faceup'}],[]],
          banished:[[],[{code:null,sequence:0,position:'facedown'}]],
          extra_deck_counts:[0,0],deck_counts:[34,35],opponent_hand_count:0,
          public_history:[],known_opponent_hand_cards:[],known_opponent_field_cards:[],
          own_extra_deck:[],restrictions:[],chain:[]},legal_actions:[]});
      const board = document.getElementById('board');
      const phase = document.getElementById('phase').getBoundingClientRect();
      const field = document.getElementById('own-monster').getBoundingClientRect();
      const deck = document.querySelector('#own-monster .pile');
      const deckBack = deck.querySelector('img')?.getAttribute('src')?.endsWith('/cover.png');
      const ownGY = document.querySelector('#own-spell .pile:last-child');
      ownGY.click();
      const graveOk = document.getElementById('pile-dialog').open &&
        document.getElementById('pile-list').textContent.includes('Public Monster') &&
        document.querySelector('#pile-list img')?.getAttribute('src')?.endsWith('/123.jpg');
      document.getElementById('pile-dialog').close();
      const oppBanished = document.querySelector('#opp-spell .pile:first-child');
      oppBanished.click();
      const hiddenOk = document.getElementById('pile-list').textContent.includes('Face-down card') &&
        !document.getElementById('pile-list').textContent.includes('Private Card') &&
        document.querySelector('#pile-list img')?.getAttribute('src')?.endsWith('/cover.png');
      document.body.dataset.pileProbe = [deckBack,graveOk,hiddenOk,
        phase.left >= field.right,board.scrollHeight <= board.clientHeight].join('|');
    </script></body>"""
    path = tmp_path / "live_piles.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--window-size=1365,768",
        "--virtual-time-budget=1200", "--dump-dom", path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-pile-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "true|true|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_duel_audio_mute_and_event_mapping_in_browser(tmp_path):
    examples = Path(__file__).resolve().parents[1] / "examples"
    template = (examples / "play_game.html").read_text()
    audio = (examples / "duel_audio.js").read_text()
    template = template.replace('<script src="/examples/duel_audio.js"></script>',
                                f"<script>{audio}</script>")
    probe = """<script>
      const button = document.querySelector('[data-duel-mute]');
      const initial = window.DuelAudio.muted;
      button.click();
      const flipped = window.DuelAudio.muted;
      button.click();
      document.body.dataset.audioProbe = [
        initial !== flipped,
        window.DuelAudio.muted === initial,
        button.getAttribute('aria-pressed') === String(!initial),
        window.DuelAudio.action('normal_summon') === 'summon',
        window.DuelAudio.action('activate') === 'activate',
        window.DuelAudio.action('attack') === 'attack',
        window.DuelAudio.action('change_position') === 'move',
        window.DuelAudio.action('end_phase') === 'phase'
      ].join('|');
    </script></body>"""
    path = tmp_path / "live_audio.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=1200", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-audio-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "true|true|true|true|true|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_phase_travel_passes_priority_and_hold_stops_after_one_step(tmp_path):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const base = {viewer:0,acting_player:0,turn_player:0,turn:2,phase:'main1',
        life_points:[8000,8000],hand:[{code:123,sequence:0}],field:[],
        graveyards:[[],[]],banished:[[],[]],extra_deck_counts:[0,0],
        deck_counts:[34,35],opponent_hand_count:5,public_history:[],
        known_opponent_hand_cards:[],known_opponent_field_cards:[],
        own_extra_deck:[],restrictions:[],chain:[]};
      const action = (kind, parameters = {}) => ({id:kind,kind,actor:0,parameters});
      const make = (decision, phase, kinds) => ({id:'1234567890abcdef',human_seat:0,
        decisions:decision,terminal:false,card_names:{123:'Test Monster'},
        observation:{...base,phase},legal_actions:kinds.map(kind => action(kind,
          kind === 'normal_summon' ? {code:123,location:2,controller:0,sequence:0} : {}))});
      const snapshots = [make(0,'main1',['normal_summon','pass']),
        make(1,'main1',['battle_phase']), make(2,'battle',['main2']),
        make(3,'main2',['end_phase']), make(4,'end',['pass']),
        {...make(5,'draw',['battle_phase']),observation:{...base,turn:3,phase:'draw'}}];
      render(snapshots[0]);
      document.querySelector('#own-hand .card').click();
      const tray = document.getElementById('card-actions').getBoundingClientRect();
      const board = document.getElementById('board').getBoundingClientRect();
      const trayFits = tray.top >= board.top && tray.bottom <= board.bottom &&
        !document.getElementById('card-actions').textContent.includes('Test Monster');
      const chosen = [];
      window.fetch = async (_path, options) => {
        const request = JSON.parse(options.body);
        chosen.push(snapshots[request.expected_decisions].legal_actions[request.action_index].kind);
        return new Response(JSON.stringify(snapshots[request.expected_decisions + 1]));
      };
      travelToPhase('end').then(async () => {
        const reached = state.observation.turn === 3 &&
          chosen.join(',') === 'pass,battle_phase,main2,end_phase,pass';
        chosen.length = 0;
        render(snapshots[0]);
        document.getElementById('hold-priority').checked = true;
        await travelToPhase('end');
        document.body.dataset.phaseTravelProbe = [trayFits,reached,
          state.observation.phase === 'main1',chosen.join(',') === 'pass'].join('|');
      });
    </script></body>"""
    path = tmp_path / "phase_travel.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--window-size=1365,768",
        "--virtual-time-budget=1200", "--dump-dom", path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-phase-travel-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "true|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_end_turn_advances_across_priority_passes_and_end_phase(tmp_path):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const base = {viewer:0,acting_player:0,turn_player:0,turn:2,phase:'main1',
        life_points:[8000,8000],hand:[],field:[],graveyards:[[],[]],banished:[[],[]],
        extra_deck_counts:[0,0],deck_counts:[34,35],opponent_hand_count:5,
        public_history:[],known_opponent_hand_cards:[],known_opponent_field_cards:[],
        own_extra_deck:[],restrictions:[],chain:[]};
      const action = kind => ({id:kind,kind,actor:0,parameters:{}});
      const wrap = (decisions, observation, legal_actions) => ({
        id:'1234567890abcdef',human_seat:0,decisions,terminal:false,
        card_names:{},observation,legal_actions});
      const snapshots = [
        wrap(0,base,[action('chain'),action('pass')]),
        wrap(1,base,[action('end_phase')]),
        wrap(2,{...base,phase:'end'},[action('chain'),action('pass')]),
        wrap(3,{...base,phase:'end'},[action('pass')]),
        wrap(4,{...base,turn:4,phase:'main1'},[action('end_phase')])];
      const chosen = [];
      window.fetch = async (_path, options) => {
        const request = JSON.parse(options.body);
        chosen.push(snapshots[request.expected_decisions].legal_actions[
          request.action_index].kind);
        return new Response(JSON.stringify(snapshots[request.expected_decisions + 1]));
      };
      render(snapshots[0]);
      document.getElementById('end-turn').click();
      setTimeout(() => { document.body.dataset.endTurnProbe =
        [chosen.join(','),state.observation.turn,state.decisions,
         !document.getElementById('end-turn').disabled].join('|'); },120);
    </script></body>"""
    path = tmp_path / "end_turn.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=800", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-end-turn-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "pass,end_phase,pass,pass|4|4|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_own_activation_passes_its_chain_unless_priority_is_held(tmp_path):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const base = {viewer:0,acting_player:0,turn_player:0,turn:2,phase:'main1',
        life_points:[8000,8000],hand:[],field:[],graveyards:[[],[]],banished:[[],[]],
        extra_deck_counts:[0,0],deck_counts:[34,35],opponent_hand_count:5,
        public_history:[],known_opponent_hand_cards:[],known_opponent_field_cards:[],
        own_extra_deck:[],restrictions:[],chain:[]};
      const action = kind => ({id:kind,kind,actor:0,parameters:{}});
      const initial = {id:'1234567890abcdef',human_seat:0,decisions:0,terminal:false,
        card_names:{},observation:base,legal_actions:[action('activate')]};
      const chained = {...initial,decisions:1,observation:{...base,chain:[
        {index:1,controller:0,card_code:123,targets:[]}]},
        legal_actions:[action('chain'),action('pass')]};
      const resolved = {...initial,decisions:2,legal_actions:[action('end_phase')]};
      const chosen = [];
      window.fetch = async (_path, options) => {
        const request = JSON.parse(options.body);
        chosen.push([request.action_index,request.manual]);
        return new Response(JSON.stringify(request.expected_decisions === 0 ? chained : resolved));
      };
      render(initial);
      choose(0).then(() => setTimeout(() => {
        const passed = chosen.length === 2 && state.decisions === 2 &&
          chosen[0][1] === true && chosen[1][1] === false;
        chosen.length = 0;
        render(initial);
        document.getElementById('hold-priority').checked = true;
        choose(0).then(() => setTimeout(() => {
          document.body.dataset.priorityProbe = [passed,chosen.length === 1,
            state.decisions === 1].join('|');
        }, 30));
      }, 30));
    </script></body>"""
    path = tmp_path / "priority.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=1200", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-priority-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_turning_off_chain_pause_resumes_automatic_pass(tmp_path):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const observation = {turn:2,turn_player:1,acting_player:0,phase:'main1',
        life_points:[8000,8000],hand:[],field:[],graveyards:[[],[]],banished:[[],[]],
        extra_deck_counts:[0,0],deck_counts:[35,35],opponent_hand_count:5,
        known_opponent_hand_cards:[],known_opponent_field_cards:[],own_extra_deck:[],
        restrictions:[],chain:[{index:1,controller:1,card_code:123}],public_history:[]};
      const action = kind => ({kind,id:kind,actor:0,parameters:{}});
      const initial = {id:'1234567890abcdef',decisions:0,human_seat:0,terminal:false,
        observation,legal_actions:[action('chain'),action('pass')],card_names:{}};
      const next = {...initial,decisions:1,legal_actions:[action('end_phase')]};
      const chosen = [];
      window.fetch = async (_path, options) => {
        const request = JSON.parse(options.body);
        chosen.push([request.action_index,request.manual]);
        return new Response(JSON.stringify(next));
      };
      const pause = document.getElementById('hold-priority');
      const defaultOff = !pause.checked && pause.autocomplete === 'off';
      pause.checked = true;
      render(initial);
      const explained = document.getElementById('message').textContent.includes(
        'Turn off the pause');
      pause.checked = false;
      pause.dispatchEvent(new Event('change'));
      setTimeout(() => { document.body.dataset.resumeProbe = [defaultOff,explained,
        chosen.length === 1,chosen[0]?.[0] === 1,chosen[0]?.[1] === false,
        state.decisions === 1].join('|'); },80);
    </script></body>"""
    path = tmp_path / "resume_pass.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=900", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-resume-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "true|true|true|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
@pytest.mark.parametrize("width,height", [(1920, 1080), (1365, 768)])
def test_context_menu_centers_and_suppresses_card_preview(tmp_path, width, height):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const observation = {viewer:0,acting_player:0,turn_player:0,turn:1,phase:'main1',
        life_points:[8000,8000],hand:[{code:123,sequence:0}],field:[],
        graveyards:[[],[]],banished:[[],[]],extra_deck_counts:[0,0],
        deck_counts:[35,35],opponent_hand_count:5,public_history:[],
        known_opponent_hand_cards:[],known_opponent_field_cards:[],
        own_extra_deck:[],restrictions:[],chain:[]};
      render({id:'1234567890abcdef',decisions:0,human_seat:0,terminal:false,
        observation,card_names:{123:'Test Card'},legal_actions:[
          {id:'0',kind:'set_monster',actor:0,
            parameters:{code:123,location:2,controller:0,sequence:0}}]});
      const card = document.querySelector('#own-hand .card');
      showPreview(card);
      const previewWasVisible = !document.getElementById('card-preview').hidden;
      card.click();
      const tray = document.getElementById('card-actions');
      const previewHidden = document.getElementById('card-preview').hidden;
      const board = document.getElementById('board').getBoundingClientRect();
      const rect = tray.getBoundingClientRect();
      const source = card.getBoundingClientRect();
      document.body.dataset.menuProbe = [previewWasVisible,previewHidden,
        rect.left >= board.left && rect.right <= board.right,
        rect.top >= board.top && rect.bottom <= board.bottom,
        Math.abs((rect.left + rect.right)/2 - (source.left + source.right)/2) < 5].join('|');
    </script></body>"""
    path = tmp_path / f"centered_menu_{width}_{height}.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", f"--window-size={width},{height}",
        "--virtual-time-budget=700", "--dump-dom", path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-menu-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "true|true|true|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_required_yes_no_uses_choice_dialog(tmp_path):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const observation = {viewer:0,acting_player:0,turn_player:0,turn:1,phase:'main1',
        life_points:[8000,8000],hand:[],field:[],graveyards:[[],[]],banished:[[],[]],
        extra_deck_counts:[0,0],deck_counts:[35,35],opponent_hand_count:5,
        public_history:[],known_opponent_hand_cards:[],known_opponent_field_cards:[],
        own_extra_deck:[],restrictions:[],chain:[]};
      render({id:'1234567890abcdef',decisions:0,human_seat:0,terminal:false,
        observation,card_names:{},legal_actions:['yes','no'].map((kind,id) =>
          ({id:String(id),kind,actor:0,parameters:{}}))});
      const dialog = document.getElementById('choice-dialog');
      const yesNo = [dialog.open,
        document.getElementById('choice-title').textContent === 'Use this effect?',
        [...dialog.querySelectorAll('button')].map(button => button.textContent).join(',')];
      render({id:'1234567890abcdef',decisions:1,human_seat:0,terminal:false,
        observation,card_names:{},legal_actions:[0,1].map(index =>
          ({id:String(index),kind:'select_card',actor:0,
            parameters:{location:2,controller:1}}))});
      document.body.dataset.choiceProbe = [...yesNo,
        dialog.open && [...dialog.querySelectorAll('button')].every(button =>
          button.textContent.includes('choice'))]
        .join('|');
    </script></body>"""
    path = tmp_path / "yes_no_dialog.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=700", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-choice-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "true|true|Yes,No|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_ai_card_sets_are_presented_one_at_a_time(tmp_path):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const action = kind => ({id:kind,kind,actor:0,parameters:{}});
      const base = {viewer:0,acting_player:0,turn_player:0,turn:1,phase:'main1',
        life_points:[8000,8000],hand:[],field:[],graveyards:[[],[]],banished:[[],[]],
        extra_deck_counts:[0,0],deck_counts:[35,35],opponent_hand_count:5,
        public_history:[],known_opponent_hand_cards:[],known_opponent_field_cards:[],
        own_extra_deck:[],restrictions:[],chain:[]};
      const facedown = sequence => ({controller:1,zone:'spell_trap',sequence,
        code:null,position:'facedown',orientation:'attack'});
      const first = {...base,field:[facedown(0)]};
      const second = {...base,field:[facedown(0),facedown(1)]};
      const initial = {id:'1234567890abcdef',decisions:0,human_seat:0,
        terminal:false,observation:base,card_names:{},legal_actions:[action('end_phase')]};
      const final = {...initial,decisions:3,observation:second,
        legal_actions:[action('end_phase')],presentation_frames:[
          {observation:first,kind:'set_spell_trap',origin:'agent'},
          {observation:second,kind:'set_spell_trap',origin:'agent'}]};
      render(initial);
      const seen = [];
      new MutationObserver(() => {
        const count = document.querySelectorAll('#opp-spell .card').length;
        if (count && !seen.some(entry => entry[0] === count))
          seen.push([count,performance.now()]);
      }).observe(document.getElementById('opp-spell'),{childList:true,subtree:true});
      window.fetch = async () => new Response(JSON.stringify(final));
      choose(0).then(() => {
        document.body.dataset.framesProbe = [seen.map(item => item[0]).join(','),
          seen.length === 2 && seen[1][1] - seen[0][1] >= 320,
          state.decisions === 3].join('|');
      });
    </script></body>"""
    path = tmp_path / "ai_frames.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=1600", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-frames-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "1,2|true|true"


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_large_card_name_prompt_is_searchable_without_rendering_every_option(tmp_path):
    template = (Path(__file__).resolve().parents[1] / "examples/play_game.html").read_text()
    probe = """<script>
      const observation = {viewer:0,acting_player:0,turn_player:0,turn:1,phase:'main1',
        life_points:[8000,8000],hand:[],field:[],graveyards:[[],[]],banished:[[],[]],
        extra_deck_counts:[0,0],deck_counts:[35,35],opponent_hand_count:5,
        public_history:[],known_opponent_hand_cards:[],known_opponent_field_cards:[],
        own_extra_deck:[],restrictions:[],chain:[]};
      const legal_actions = Array.from({length:250},(_,index) =>
        ({id:String(index),kind:'announce_card',actor:0,parameters:{code:index+1}}));
      render({id:'1234567890abcdef',decisions:0,human_seat:0,terminal:false,
        observation,card_names:{201:'Target Card'},legal_actions});
      const dialog = document.getElementById('choice-dialog');
      const search = document.getElementById('choice-search');
      const initial = dialog.querySelectorAll('#choice-options button').length;
      search.value = 'Target Card';
      search.dispatchEvent(new Event('input'));
      document.body.dataset.searchProbe = [dialog.open,!search.hidden,
        initial === 100,dialog.querySelectorAll('#choice-options button').length === 1,
        dialog.querySelector('#choice-options button').textContent.includes('Target Card')]
        .join('|');
    </script></body>"""
    path = tmp_path / "large_choice_dialog.html"
    path.write_text(template.replace("</body>", probe), encoding="utf-8")
    result = subprocess.run([
        shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=700", "--dump-dom",
        path.as_uri(),
    ], capture_output=True, text=True, timeout=20, check=True)
    match = re.search(r'data-search-probe="([^"]+)"', result.stdout)
    assert match, result.stderr[-1200:]
    assert match.group(1) == "true|true|true|true|true"
