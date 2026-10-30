# GOAT AI

Research foundation for a general-purpose Yu-Gi-Oh! GOAT Format agent. The experimental adapter runs complete, seeded, headless duels with sourced GOAT Decks through a pinned native rules engine. It exposes player-visible observations and legal actions, and records replay-verifiable trajectories. Historical ruling coverage and competitive playing strength remain incomplete.

## Status

| Component | Status |
| --- | --- |
| Engine selection and source review | Initial research complete |
| Native GOAT-mode startup | Pinned core and assets reach the first decision; reproducible setup and first-turn draw checks |
| Complete headless duel | Experimental adapter completes sampled sourced-deck duels; arbitrary legal Decks and every historical ruling are not certified |
| Environment contract and illegal-action validation | Implemented |
| Player-visible observation schema | Own hand, initial Main Deck composition, and Extra Deck; public zones, battle position, face-up field-card age, face-up monster ATK/DEF/counters/current Type/original owner, pending public summon, chain links, bounded public events, known opponent field and hand cards, public Deck-top reveals, recipient-scoped card reveals, disabled zones, and the public Scapegoat summon restriction; broader reveal and restriction coverage pending |
| Random, heuristic, and CLI human agents; browser human play | Implemented; sampled sourced-deck games finish through the same observation/action boundary |
| JSON trajectory round trip | Schema v28 records player-visible decisions, public effect choices, terminal observation, Deck and native-asset hashes; older schemas remain readable, but changed native assets may require re-recording for exact verification |
| Tournaments | Seeded, seat-swapped sequential and spawned-process runners; paired score intervals and Wilson intervals for supported decks |
| Native throughput benchmark | Measures complete vanilla or sourced-deck duels, reset time, and single-process peak RSS; see `docs/benchmarks.md` |
| Allowed-card asset inventory | All 1,685 pinned whitelist IDs have metadata and a candidate script path; runtime coverage unverified |
| Experimental GOAT adapter | Sourced-deck protocol sweeps, source-backed ruling fixtures, exact replay checks, and bounded hidden-information audits exist; broad historical correctness remains an open gate |
| PyTorch policy | Visible-state action scorer with opt-in feature versions through v28; replay-verified imitation, preference, and self-play experiments exist. The selected v23 checkpoint remains the neural reference because recent self-play children have not shown a transferable held-out strength gain; see [evaluation](docs/evaluation.md) |
| Human EDOPro replay intake | Bounded `.yrp`/`.yrpX` parsing and synthetic response reconstruction exist. A real, authorized GOAT replay has not passed exact reconstruction; see [replay contributions](docs/replay_contributions.md) |
| Experimental EDOPro policy room | Optional local room runs the selected policy against EDOPro and saves native replay plus audited review-only decisions; one complete desktop GUI game has been verified, while the historical training gate remains open |

The selected direction is [Project Ignis/edo9300 ocgcore](https://github.com/edo9300/ygopro-core), configured with its `DUEL_MODE_GOAT` flag, historical card data and scripts, and an audited Python-facing decision adapter. A 2005 banlist alone is insufficient. See [research](docs/research.md), [architecture](docs/architecture.md), and [roadmap](docs/roadmap.md).

## Install and check

Requires Python 3.10+. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python examples/show_contract.py
```

PyTorch is an optional training dependency: `python -m pip install -e '.[ml]'`. The first policy and replay-verified behavioral cloning path are described in [the ML notes](docs/ml.md).

Tests are run locally; this repository does not use GitHub Actions. After native setup, run `GOAT_AI_NATIVE_ROOT=.cache/goat-ai python -m pytest -q` for the full native suite and `ruff check .` for lint.

The API is `GoatEnvironment(player1_deck, player2_deck, seed, engine=...)`; `reset()`, `legal_actions()`, `step()`, `is_terminal()`, `result()`, and `trajectory()` are defined. Pass `ExperimentalOcgcoreEngine` for sourced GOAT Decks or `RestrictedOcgcoreEngine` for the narrow audited fixture subset. The default raises `SimulatorUnavailable` until the caller explicitly selects an installed engine.

## Native setup (Linux)

The native adapters call a pinned ocgcore build with `DUEL_MODE_GOAT`. Raw core messages remain inside the adapter. The experimental adapter uses player-scoped queries, redacts hidden card identities in observations and action parameters, and has differential visibility and exact replay tests. These tests cover sampled interactions, not every legal GOAT card.

```bash
python -m pip install -e '.[dev,native]'
python scripts/setup_native.py
python scripts/probe_native.py --seed 42
python scripts/run_native_smoke.py --seed 42
GOAT_AI_NATIVE_ROOT=.cache/goat-ai python -m pytest -q tests/test_ocgcore_probe.py
```

Setup downloads and builds external dependencies under ignored `.cache/goat-ai/`. See [native setup](docs/native_setup.md) for pinned revisions, licensing, and the probe's limits.

The smoke runner validates its 40-card fixture against a pinned Project Ignis GOAT whitelist, decodes empty chain windows, idle choices, and single-card selections, then ends turns and discards at hand limit until the native core reports a winner. This is a protocol regression for one simple fixture, not a general GOAT environment or an agent-strength benchmark.

The restricted `RestrictedOcgcoreEngine` connects the same native core to `GoatEnvironment` for 40-card fixture decks using the tested cards. To run a real duel between two fixture decks with a `RandomAgent`:

```bash
python examples/play_vanilla.py --seed 42 --trajectory replays/vanilla_42.json
python examples/play_vanilla.py --human-seat 0
python scripts/benchmark_native.py --games 3 --seed 42
python scripts/benchmark_native.py --engine experimental --deck-a examples/decks/goat_control_lolmarcus_2020.ydk --deck-b examples/decks/chaos_turbo_riclar_2020.ydk --games 10 --seed 9700 --max-decisions 3000
python scripts/audit_card_pool.py
python scripts/evaluate_native.py --agent-a heuristic --agent-b random --seeds 10
python scripts/evaluate_native.py --engine experimental --agent-a combat_heuristic --agent-b heuristic --both-deck-assignments --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk --seeds 2
python scripts/evaluate_native.py --agent-a random --agent-b random --seeds 4 --workers 2
```

To verify a saved fixture trajectory against the current pinned native assets:

```bash
python scripts/verify_trajectory.py replays/vanilla_42.json
```

The verifier replays each selected action, compares the visible observation
and complete legal-action list at every decision, and checks the winner. New
recordings also check rules-profile, deck-file, and loaded native-asset hashes. Use
`--deck1` and `--deck2` when the original YDK paths have moved. It cannot
prove that a card interaction is historically correct; it detects divergence
from the engine and assets used for the replay.

## Play and record a GOAT duel

### Experimental EDOPro room

The local game creation page now has **Play in EDOPro**. Start it with
`start_review_viewer.sh` or `python scripts/launch_review_server.py --game-creator`.
Choose a published AI Deck and press **Start EDOPro room**. When the page says
the room is running, join `127.0.0.1:7911` through EDOPro's LAN host-address
screen. The page shows the latest room sessions and links a recording only
after independent replay reconstruction succeeds. Each session stays in the
ignored `.cache/goat-ai/edopro_games/<session-id>/` folder. The room process
continues if you close the browser tab. Start another room after the first
duel ends. The local page needs the optional host and pinned assets described
below; it reports a missing prerequisite instead of starting an unpatched room.
After a verified duel, press **Confirm my choices** beside its replay. The
scrollable list shows optional decisions from the human seat with links to
their viewer frames. Check only actions you personally chose; EDOPro may answer
some prompts automatically. **Save confirmations** writes and verifies
`<game>.human_labels.json` beside the recording. Reopening the dialog restores
the saved checkmarks, and unchecking one removes that confirmation. These
annotations remain review-only while EDOPro training admission is closed.

You can play the selected PyTorch policy through an EDOPro LAN room using the
optional external `mostwanted7/ygo-agent` host. The host is AGPL-3.0-or-later,
installed separately; it is not included in this MIT repository. The EDOPro
installation, matching native mirror root, checkpoint and Deck are local files.
After [native setup](docs/native_setup.md), prepare the host's ignored asset
layout and start the locally tested pinned-core room:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/prepare_pinned_edopro_host.py
PYTHONPATH=src:.cache/goat-ai/edopro_probe/ygo_agent_host \
  .venv/bin/python scripts/serve_edopro_policy.py \
  --host-root .cache/goat-ai/edopro_pinned_host \
  --mirror-root .cache/goat-ai --historical-pinned \
  --checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --ai-deck examples/decks/warrior_montague_clash.ydk \
  --human-authorization self_recorded
```

In EDOPro choose **LAN → Host address**, enter `127.0.0.1` and port `7911`,
select your GOAT Deck, then ready up. The AI occupies seat 2. This is a private
localhost room for one game; `--bind` and `--port` can change its listener.
The script prints the save location, defaulting to ignored
`.cache/goat-ai/edopro_games/`. It writes EDOPro's `.yrpX` and a metadata file;
if every host response matches the native mirror and the duel reaches a native
terminal, it also writes a player-visible `.review.json` trajectory. Open that
JSON in the local replay viewer. You can also render a standalone local viewer
with `python scripts/render_replay.py <game>.review.json --native-root .cache/goat-ai --output <game>.html`.
The pinned room loads the project's
checksum-guarded historical script corrections without modifying the source
checkout. Its records are marked `edopro_pinned_historical` and **excluded
from automatic training** until broader historical correctness and more
desktop-client prompts are validated. A surrender or disconnect saves the replay
and metadata. When the mirrored decisions are synchronized, it also saves
their player-visible prefix as `.review.json`, marked `interrupted` with no
native-duel winner. The viewer labels its last frame **Recording stopped**.
This prefix remains excluded from training. See [the live room research](docs/research.md#edopro-live-client-bridge-probe-2026-10-30).

One EDOPro 41.0.2 desktop duel on this pinned room completed in seven turns.
The human used the GUI's End Phase and hand-size discard controls; the room
saved 165 responses with zero retries and zero Lua errors. Independent
reconstruction matched all 165 player-visible decisions and the terminal
result. This validates that specific path, not every possible EDOPro prompt.
New room recordings also store a SHA-256 identifier for each Deck's sorted
Main and Extra Deck composition. Verification checks those identifiers against
the Decks embedded in the EDOPro replay; it does not expose shuffled Deck order.
Older recordings without identifiers still verify their decisions and outcome.
Use `--human-authorization self_recorded` only for your own authorized games.
It records the human client's seat and permission in the replay metadata and
review trajectory. EDOPro can answer some prompts automatically, so this does
not prove which responses were deliberate clicks; those records remain excluded
from raw behavioral-cloning intake until that distinction and the historical
rules gate are resolved.
An explicit `self_recorded` annotation on an EDOPro review trajectory now
requires that authorization, the human client seat, and the exact action that
was played. This permits retrospective confirmation of specific human choices
without labeling the AI's actions or an unplayed alternative as human play.
The training command still rejects EDOPro sources pending the remaining gates.
For a manually confirmed choice, put its zero-based `decision_index` and
recorded legal `action_index` in a schema-v1 `self_recorded` annotation tied to
the review JSON's SHA-256. Check it with
`python scripts/verify_edopro_human_labels.py <game>.yrpX <labels>.json --native-root .cache/goat-ai`.
The checker independently reconstructs the duel before accepting the label;
its output remains review-only.
To create that annotation after watching your own authorized duel, use the
one-based **Decision** numbers shown in the viewer:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/confirm_edopro_human_actions.py \
  .cache/goat-ai/edopro_games/game-001-seed-NNN.yrpX 12 37
```

Replace `NNN` with your saved seed and `12 37` with decisions you personally
confirm choosing. The script independently verifies the replay, rejects AI
turns and forced choices, and writes a checked `.human_labels.json` beside it.
It will not replace a different existing label file. This is a review aid;
the EDOPro training gate remains closed.

The external host package remains a separate AGPL dependency and must be on
`PYTHONPATH`. The locally tested checkout is
`https://github.com/mostwanted7/ygo-agent.git` at
`c017f3c20d78b01e6398a41d33e023cf20236ae1`, placed in the ignored
`.cache/goat-ai/edopro_probe/ygo_agent_host` directory. The checkpoint is a
local generated file; substitute another
compatible checkpoint path if needed. To rerun the TCP-room regression:

```bash
GOAT_AI_EDOPRO_HOST_ROOT=.cache/goat-ai/edopro_pinned_host \
GOAT_AI_EDOPRO_MIRROR_ROOT=.cache/goat-ai \
GOAT_AI_EDOPRO_HISTORICAL=1 \
PYTHONPATH=src:.:.cache/goat-ai/edopro_probe/ygo_agent_host \
  .venv/bin/pytest -q tests/test_edopro_policy_room.py
```

Without these external assets and the AGPL host package, this test skips.
For a completed game or interrupted prefix, verify that the review JSON
matches the saved native EDOPro replay on the same assets:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/verify_edopro_live_game.py \
  .cache/goat-ai/edopro_games/game-001-seed-NNN.yrpX \
  --native-root .cache/goat-ai
```

Replace `NNN` with the seed printed in the saved filename. This checks every
recorded visible decision and, for complete games, the native outcome. It
still reports `training_admitted: false`.

### Local terminal play

To play a GOAT Deck yourself in the terminal and save a local demonstration:

```bash
PYTHONPATH=src:. .venv/bin/python examples/play_goat.py \
  --deck1 examples/decks/goat_control_lolmarcus_2020.ydk \
  --deck2 examples/decks/chaos_turbo_riclar_2020.ydk \
  --human-seat 0 --opponent tactical --seed 42 \
  --trajectory replays/my_goat_duel_42.json
```

The command shows card names and the player-visible field. Enter a numbered
legal action; use `n`/`p` to page through long lists, `/text` to search, or
`/` to clear the search. Action numbers stay stable while filtering. It saves
only after the complete duel passes
native replay verification and the visibility audit. `--human-seat 1` plays
the second Deck; `--opponent random` or `--opponent policy --checkpoint PATH`
changes the opponent. The recording is marked `self_recorded` and stored in
ignored `replays/`. A terminal may be cumbersome for large card-choice lists;
the saved game can be opened in the replay viewer afterward. See
[replay contribution rules](docs/replay_contributions.md) before sharing it.

## View a replay

To create an AI-versus-AI game in the browser, start the local game creator:

```bash
./start_game_creator.sh
```

Choose two Decks, two agents (Random, Tactical, or the selected neural v23
checkpoint), and a seed. The server runs a complete native GOAT duel, verifies
its trajectory and player visibility, then opens a replay with both players'
hidden cards available to the reviewer. The AI agents still receive only their
own legal player-visible observations. Generated games stay in ignored
`.cache/goat-ai/user_games/`; the page lists recent games so you can reopen
them. Add a legal `.ydk` file to `examples/decks/` to use a custom Deck.
The creator is also linked from replay pages served on localhost.
Recent games show clickable **review flags** for simple player-visible
mistake patterns. These are prompts to inspect, not correctness judgments or
training labels; clicking one opens the recorded decision frame.
If a selected-policy game has flagged policy decisions, **Review policy
choices** opens a separate save-enabled queue. Its label view shows only what
the AI could see at that moment; **Reveal all cards** remains a distinct
inspection view with labeling disabled. Saved choices are kept in the local
review-label folder. Queue creation replays the duel, audits player visibility,
and reproduces the recorded policy choices from the pinned checkpoint. Saved
choices require replay and visibility validation before use for training.
Reopening an existing game queue refreshes its generated viewer pages while
retaining the queue identity and any locally saved labels.

To play a duel yourself in the browser, open `/games/play` on the same local
server. Choose the human seat, two Decks, and a Random, Tactical, or selected
neural opponent. A fresh seed is filled automatically; use the dice button to
roll another or type a seed to reproduce a duel. Click a card to open icon
buttons for its legal actions beside the card. Drag a card to a highlighted
field zone or opposing monster to choose
a placement or attack target; when the engine offers a matching next choice,
the dragged destination is used. Empty or occupied zones that cannot accept the
drag are not highlighted. Visible card faces and card backs load from the local
server's art cache; missing artwork displays the card name instead.
When an effect asks for multiple cards, such as Graceful Charity's two
discards, click the cards in your hand or on the field, then press **Confirm
selected cards**. Click a selected card again to undo it. The advanced action
list remains available for debugging; required Yes/No, card, position, and
effect-option decisions open a choice dialog. When one card offers
multiple effect modes, its action buttons show distinct descriptions from the
pinned card database; the full text appears on hover and in the advanced list.
Open placement zones are
chosen automatically after a Summon or Set; uncheck **Automatically choose open
card zones** to select the zone yourself. By default, the live UI passes through
optional chain-response windows on both turns, then returns to the next
actionable decision. Check **Pause at each chain response** before an opponent
action you may want to answer with a Trap or quick effect; uncheck it to resume
automatic passing. A reload starts with automatic passing enabled, and the
sidebar explains when this pause is holding a chain response.
The server resolves optional Chain/Pass windows by default, so progress does
not depend on a browser timer. It automatically declines a native chain window
whenever **Pass** is available and response pausing is off, including after an
AI move. Such passes stay in the verified
trajectory and unfinished-game journal. When response pausing is enabled,
available Chain responses stop for your choice. Hover or focus a card to enlarge
it; your own face-down cards preview their known faces, while unknown opponent cards stay
concealed. Scroll over the previewed card to resize it.
On desktop, the field fits both players' zones and hands in the viewport; the
sidebar scrolls independently when its details are expanded.
The live board uses the replay viewer's vertical phase rail. Click a Graveyard
or banished zone to inspect the visible cards with images; Deck zones display
card backs and remaining counts while keeping live Deck order hidden. Live play
and generated replay viewers have a shared **Sound on/off** control that keeps
its setting in this browser. For local personal use, run
`python scripts/setup_local_duel_sounds.py` to download pinned EDOPro effects
into ignored `.cache/goat-ai/duel_sounds/`. Its `CREDITS.md` lists each source
and license. The viewer uses synthesized cues when local files are unavailable,
including when opened offline. Browsers may wait for a click before playing
audio. No game sound files are committed to Git; see
[EDOPro's sound credits](https://github.com/ProjectIgnis/Distribution/blob/master/sound/CREDITS.md).
Click a future phase to pass through intermediate priority windows. Enable
**Pause at each chain response** to keep response windows after your activations.
Use **Pass** for individual responses, or use **End turn** to pass through
intermediate windows, enter the End Phase, and finish the turn in one click.
Consecutive automatic Pass choices
are resolved before the next board decision appears. Visible AI card changes
are shown in order with a short entrance animation. Unusual prompts and every
legal choice remain available under **All legal actions** in the sidebar.
The board and controls use only the human player's visible observation and
native legal actions. On completion the server replay-verifies the duel,
checks player visibility, and saves a `human_web` self-recording and full
postgame replay under `.cache/goat-ai/user_games/`. Only the human seat is
admitted as a raw demonstration. The recording marks deliberate human choices;
automatic passes, phase travel, and automatic zone placements remain in the
verified replay but are excluded from imitation labels. Older `human_web`
recordings without this choice provenance are viewable but are not admitted
to raw imitation training. Unfinished games are journaled under ignored
`.cache/goat-ai/user_games/_in_progress/`. Reopen their `#game=...` URL after
restarting the server to reconstruct the duel from its seed and recorded
actions. Changed decks, AI checkpoint, native assets, or decisions fail closed.
Only completed, replay-verified games enter the `human_web` replay folder;
**Leave unfinished duel** discards the journal. The browser is an experimental local play interface, subject to
the same unresolved GOAT ruling coverage as the native adapter.
An unfinished journal can also supply explicit human decisions to behavioral
cloning without pretending the duel ended. For example:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  --human-journal .cache/goat-ai/user_games/_in_progress/GAME_ID.json \
  --native-root .cache/goat-ai --engine experimental \
  --feature-version 23 --output .cache/goat-ai/human_prefix_pilot.pt
```

The trainer copies the private journal into ignored
`.cache/goat-ai/human_journal_snapshots/`, replays every saved action on the
pinned native core, checks each saved observation and legal-action digest, and
trains only explicit, non-forced human choices. The checkpoint records the
snapshot hash and marks the duel as partial with no outcome. Keep the
checkpoint experimental until separate held-out play shows a strength gain.
The board lists public Graveyard and banished cards, your Extra Deck and known
opponent cards, and card names in the legal-action menu without exposing the
opponent's private hand or Deck order. Missing card images are fetched from the
existing YGOPRODeck image source when first shown and cached locally in
ignored `replays/card_images/`; historical card IDs use their printed-card
artwork alias. If an image is unavailable, the card name remains visible.

The offline [replay viewer](examples/replay_viewer.html) shows each recorded decision as a board snapshot from the acting player's visible view. Record and render a Scapegoat fixture duel:

```bash
python examples/play_vanilla.py \
  --deck1 examples/decks/scapegoat_probe.ydk \
  --deck2 examples/decks/vanilla_probe.ydk \
  --engine experimental --seed 3 \
  --trajectory replays/scapegoat_3.json
python scripts/render_replay.py replays/scapegoat_3.json
xdg-open replays/scapegoat_3.html
```

The generated HTML is self-contained and shows card names when the pinned card database is installed. To open **multiple** replay JSON files from one viewer without seeing `Card #...`, generate a local catalog viewer once:

```bash
python scripts/render_replay.py --catalog-viewer
xdg-open replays/goat_viewer.html
```

Choose each replay **JSON** with **Open trajectory**. Open a generated replay **HTML** directly in your browser; selecting that HTML through **Open trajectory** will not load it. The catalog viewer embeds names for the 1,685 legal GOAT IDs and generated Tokens from your local card databases; no card database or catalog is committed to Git. A per-replay HTML generated by `render_replay.py` also embeds this catalog, so opening a different JSON in that page keeps names available. Opening the bare `examples/replay_viewer.html` template directly has no database and shows card IDs with a notice explaining how to generate the named viewer.

With **Skip passes and placement** enabled, playback skips routine pass decisions even when the field changed since the previous decision. It still stops once on a newly built chain if that chain would resolve before the next meaningful choice, so a chained Trap can be seen face up. During a chain, numbered icons appear over the source card zones, Graveyards, or banished piles. Life-point changes and field-to-pile movement appear at the next displayed frame. Previously generated HTML embeds its own copy of the viewer; regenerate it with `scripts/render_replay.py` to pick up viewer fixes.

Face-up cards with Spell Counters show a numbered counter badge on the field and in the enlarged card preview. The badge uses the counter count recorded in the player-visible observation; it does not reveal counters on hidden cards.

The replay field keeps the same player at the bottom as decisions pass between players. It starts with the recorded learner or demonstrator seat when available; use **Switch sides** in the sidebar to change it. Action locations use fixed P1/P2 labels; the decision details still identify whose player-visible snapshot is being shown. Load a verified reviewer reveal if you want both hands visible throughout the replay.

If the original JSON is missing, `python scripts/extract_embedded_replay.py REPLAY.html OUTPUT.json` restores it from a generated standalone viewer and checks the embedded SHA-256. Catalog-only viewers have no trajectory to restore.

The sidebar identifies agents when the trajectory records their provenance. See the [early replay decision audit](docs/replay_audit.md) for frame-specific findings and the experimental `--tactical-guard` option for learned-policy match recording and evaluation.

To review queued policy decisions without downloading or moving label files,
start the [local review server](docs/replay_audit.md) from the repository root:

```bash
./start_review_viewer.sh
```

This opens the newest local review queue or recheck queue in your browser. To open a specific
queue, pass its `queue.json` path as an argument. The launcher reuses a running
server for that queue and writes startup logs to
`.cache/goat-ai/review_server.log`.

Open the printed `http://127.0.0.1` address to save choices automatically.
Opening `queue.html` as a `file://` page only offers a manual download;
its choices are lost if you leave without exporting them. The save-enabled
server accepts labels only for decisions listed in the opened queue.

On Cinnamon/Linux Mint, run
`.venv/bin/python scripts/install_review_shortcut.py` once to add **GOAT AI
Review Viewer** to the app menu and pinned taskbar apps. If Cinnamon is already
running, its taskbar may show the new pin after the next session reload.

Choosing a legal action saves it to an
ignored local folder and restores it when you return; no reviewer name is
needed. Use **☆ Bookmark** on a queue card or in the replay bar to save an
item for later without choosing a play. Bookmarks are stored separately from
training labels. The legal-action list marks the recorded action **AI played**;
clicking that row only points to the explicit **Approve AI-played action**
button. Clicking an alternative action saves that choice directly. The viewer
confirms whether your saved choice matches the recorded play. Validate saved choices
before training on them.

The renderer also reads card-effect choice text from the local databases, so prompts such as Enemy Controller's two modes have distinct labels. Position and monster-Type choices use names. If a database has no text for a particular option, the viewer labels it by choice number.

The duel board keeps both fields and hands on one screen at desktop sizes; replay loading, playback controls, legal actions, and other details scroll in the right sidebar. Hands show the upper half of each card to leave room for the field. Hover or focus any card to see a larger preview; use the mouse wheel over it to resize the preview from a small card up to the largest card that fits the screen. Banished and Extra Deck stacks flank each centered hand, and the phases run vertically at the right edge of the field. Field Spell Zones sit left of the Monster Zones, while Graveyards sit right of the Spell/Trap Zones. Monsters rotate to show attack and defense position. The viewing player is always at the bottom. Use its slider, arrow keys, or Play button to step through decisions; `#decision=11` opens a particular decision. **Prev common** and **Next common** jump to decisions with at least two legal actions involving a card found in five or more of the six sourced tournament Main Decks. This small sample guides review; it does not measure GOAT metagame play rates. Staged card choices show the required selection count and already selected cards. The legal-action list shows 100 entries at a time, with a button for more. New schema-v18 recordings also include a final frame with the terminal field and Life Points; older recordings end on the last decision. Public Deck-top reveals, cards shown only to the acting player, known opponent hand identities, active disabled field zones, and the acting player's starting Deck composition appear on new recordings. Known hand cards are listed in the sidebar without assigning them to hidden hand slots.

Click a Deck, Extra Deck, Graveyard, or banished zone on the field to inspect
its cards. The sidebar no longer repeats the pile and starting Deck lists.

For a **reviewer-only** view with both hands face up and Set card identities on hover, generate a verified page for the replay:

```bash
python scripts/render_replay.py replays/tournament_verified_18500/game_00029_seed_18500.json --output replays/latest_game.html --reviewer-reveal
xdg-open replays/latest_game.html
```

This also writes `replays/latest_game.review.json`. To use the catalog viewer instead, open the original trajectory with **Open trajectory**, then load that sidecar with **Reviewer reveals**. The sidecar is tied to the exact trajectory SHA-256; the generator first replays and verifies every observation, legal action, deck hash, native asset hash, and result. The original trajectory and `GoatEnvironment` observation API remain player-visible. Reviewer mode disables decision labeling, so revealed information cannot be included in human training labels. The sidecar and generated page contain hidden information and stay in ignored `replays/`; keep them out of training input. If the original decks moved, pass `--deck1` and `--deck2` with their new paths.

Click a Deck, Graveyard, Banished, or Extra Deck stack to open a scrollable card popup. Graveyards display their public cards. The regular player-visible view shows your recorded *starting* Deck composition and Extra Deck identities; opposing hidden identities remain concealed. Reviewer mode shows both starting Deck compositions, Extra Decks, and concealed banished cards; it still does not show the order of cards remaining in either Deck. The duel field has colored zone outlines, card stacks, Life Point badges, and phase indicators inspired by tabletop replay layouts. Attack targets get an arrow from the attacker and red corner markers; active chain targets keep those markers. Life Point numbers and pill fill animate between frames, with 8000 LP filling the pill and higher totals remaining visually full. When a field card is visible before a decision and appears in a Graveyard or banished pile afterward, its displayed card moves to that pile. These movements are interpolation between recorded decision snapshots, not a reconstruction of every native animation frame. Motion respects the browser's reduced-motion setting.

The current GOAT-only native trigger-order patch changes the simulator binary fingerprint. Older replays still open in the viewer, but reviewer-only sidecars for them require a matching old native build or a freshly recorded trajectory on the patched build.

To set up artwork automatically for one replay, cache its visible cards and regenerate the catalog viewer:

```bash
python -m scripts.setup_card_images replays/tournament_verified_18500/game_00029_seed_18500.json
python scripts/render_replay.py --catalog-viewer
xdg-open replays/goat_viewer.html
```

Pass several replay paths to cache their combined card set, for example `replays/tournament_verified_18500/*.json`. The images live in ignored `replays/card_images/` and are loaded locally by the generated viewer. The setup script downloads each small card face once at a modest rate from [YGOPRODeck's documented image server](https://ygoprodeck.com/api-guide/); it uses base-card artwork for historical script variant IDs. It also downloads checksum-pinned [EDOPro `cover.png` and `cover2.png` textures](https://github.com/ProjectIgnis/Distribution/tree/master/textures) for the two card backs. To set up only those backs, run `python -m scripts.setup_card_images --card-back-only` and regenerate the viewer. The textures and card art are local visual assets, excluded from the project's MIT-licensed Git repository. Artwork is a visual aid: printed card text in a current image may differ from the historical effect enforced by the pinned simulator. You can also use **Card images** in the viewer sidebar to select your own local folder of numbered JPG, PNG, or WebP files, including `cover.png` and `cover2.png`. The browser reads those files locally and does not upload them; use the picker again after reloading. Without images, names and drawn card backs still display. The viewer does not open EDOPro `.yrp`/`.yrpX` files. Replays and generated HTML live in ignored `replays/`.

To inspect an EDOPro replay container's format and record counts, run
`python scripts/inspect_edopro_replay.py path/to/replay.yrpX`. The summary
omits player names and card IDs. To test whether its saved responses reconstruct
on your pinned native assets, add `--reconstruct-native .cache/goat-ai`.
That optional check reports counts and provenance hashes only. A native match
does not certify the replay's original core/scripts, historical rulings,
training permission, or compatibility with the visual viewer.

To review a decision, expand **All legal actions** in the sidebar and click a
choice. Enter your name or alias, confirm that you created the labels and
authorize their use, then download the local JSON label file. It stores
decision and action indexes tied to the source trajectory's SHA-256; it does
not upload the replay. The training CLI replay-verifies the exact source file,
checks player-visible action safety, and rejects stale or illegal labels:

```bash
OMP_NUM_THREADS=1 python scripts/train_behavioral_clone.py \
  replays/scapegoat_3.json \
  --annotation ~/Downloads/goat_ai_labels_seed_3.json \
  --engine experimental --output checkpoints/reviewed_smoke.pt
```

This is a pipeline example using retrospective labels. Such labels are not
live human gameplay recordings or evidence of a stronger policy; see
[the ML notes](docs/ml.md).

For a replay that shows a two-zone choice and the resulting disabled Monster Zones, run `python examples/record_ground_collapse.py`, then `python scripts/render_replay.py replays/ground_collapse_3.json` and open `replays/ground_collapse_3.html`. This uses the experimental adapter and verifies the full seeded duel before writing the trajectory.

The play example prints the winner and decision count and optionally writes a JSON trajectory. `--human-seat` uses the same action API for a CLI player. The evaluation command swaps candidate seats for each seed and reports matchup and seat results; see [the evaluation log](docs/evaluation.md). Supported decision types remain limited to the tested decks, and unsupported requests fail explicitly. The default environment still fails closed because general GOAT effects and visibility cases are unfinished. The benchmark includes reset and Python action selection; results are specific to this fixture and machine.

For experimental effect-card coverage, run:

```bash
python scripts/setup_native.py --full-card-scripts
python scripts/probe_control_deck.py --seed 42
python scripts/probe_control_deck.py --seed 0 --seeds 50
python scripts/probe_control_deck.py --deck examples/decks/control_probe.ydk --opponent-deck examples/decks/chaos_probe.ydk --seed 0 --seeds 10
python scripts/probe_control_deck.py --deck examples/decks/chaos_turbo_riclar_2020.ydk --opponent-deck examples/decks/control_probe.ydk --seed 1 --seeds 20
python scripts/probe_control_deck.py --deck examples/decks/goat_control_lolmarcus_2020.ydk --opponent-deck examples/decks/chaos_turbo_riclar_2020.ydk --seed 1 --seeds 20
python scripts/probe_control_deck.py --deck examples/decks/warrior_montague_clash.ydk --opponent-deck examples/decks/chaos_turbo_riclar_2020.ydk --seed 1 --seeds 10
python scripts/probe_control_deck.py --deck examples/decks/flip_control_goatformat_guide.ydk --opponent-deck examples/decks/chaos_turbo_riclar_2020.ydk --seed 31 --seeds 10
python scripts/probe_random_decks.py --seeds 10 --max-decisions 3000
```

The Chaos Turbo Main Deck follows the [Riccardo Lari 2020 championship list](https://www.goatformat.com/chaos-turbo.html), using pinned GOAT/pre-errata card IDs. The published list does not specify an Extra Deck, so this fixture leaves it empty. This probe tests native decision coverage with random play; it does not measure competitive strength or prove every card ruling.

The Goat Control Main Deck follows the [Lolmarcus 2020 championship list](https://www.goatformat.com/goat-control.html). Its published list omits the Extra Deck; the fixture adds three Thousand-Eyes Restricts as a documented test choice so Metamorphosis has a legal summon. Seeds 1–20 completed 20/20 random-agent duels against the Chaos Turbo fixture with Goat Control in seat 0. This is protocol coverage under pinned scripts.

The Flip Control Main Deck follows the [GoatFormat guide list](https://www.goatformat.com/flip-control.html). It is a representative guide list, not an attributed tournament submission. The source omits an Extra Deck, so this fixture leaves it empty. Paired random-agent duels against Chaos Turbo and Goat Control are recorded in the [evaluation log](docs/evaluation.md); they test native protocol coverage, not the archetype’s competitive strength.

The random-deck probe deterministically generates whitelist-legal 40-card
decks and writes its deck files and JSON report under ignored `.cache/goat-ai/random-probe/`.
It is a native protocol coverage check, not a historical correctness or playing-strength test.
On the currently pinned local assets, seeds 0–9 completed 10/10 duels in
12,006 decisions; the report SHA-256 is
`de9e1d0aa4695fe223d6a1b7fa4690958374ba632f58431dde706ec5e6149d01`.
The earlier 12,382-decision result is reproducible with project source at
`6611e1b` and the same pinned native assets. Commit `b84e0d8` changed the
order of Deck-search actions to hide native Deck slots: seeds 6 and 9 changed
from 1,295 and 1,249 decisions to 1,397 and 771, respectively; the other
eight seeds retained their counts. `RandomAgent` selects by action index, so
this privacy fix changed its choices and subsequent duel paths. These counts
measure protocol coverage, not comparable agent strength.
For generated decks made entirely from sourced tournament cards, use
`--card-pool tournament --verify-replays`. Add `--distinct-opponents` to pair
two independently generated legal decks in each duel; see
[competitive action coverage](docs/competitive_action_coverage.md).

The sample is a synthetic control-style protocol probe, not a sourced
tournament decklist. On pinned assets, seeds 0–49 all reached terminal states
with seeded random actions after effect yes/no decoding was added; seed 42
ends after 1,251 decisions with winner seat 1. This is neither a playing-strength benchmark
nor a historical-rulings validation. `ExperimentalOcgcoreEngine` accepts
whitelist-legal main decks of at least 40 cards and Fusion Extra Decks; the Side Deck is
validated but unused in a single duel. Historical 0-or-15 Side Deck sizing is
the default; `RulesProfile(side_deck_policy="community")` permits a shorter
Side Deck. The adapter may fail on unhandled
native requests. Its action semantics and player-visible observations must be
audited before using it for training or competitive evaluation.

The second synthetic Chaos-style probe includes a Fusion Deck and additional
search and discard effects. Ten seeds completed in each seat order against
the control probe. These results show protocol coverage for the sampled
random action paths; they do not establish card-by-card correctness.

## Contributions and data

Original code is MIT licensed. Third-party engines, scripts, and card databases are separate dependencies under their own licenses and are not vendored here. Do not commit replay collections, models, card databases, or binaries. Only ingest gameplay data you have permission to use.

