# GOAT AI

Research foundation for a general-purpose Yu-Gi-Oh! GOAT Format agent. A restricted native adapter runs complete duels with 40-card normal-monster decks and selected scripted cards: Pot of Greed, Book of Moon, the GOAT variant of Nobleman of Crossout, and Cannon Soldier. General effect-card support and historical rules validation are unfinished. No competitive playing strength is claimed.

## Status

| Component | Status |
| --- | --- |
| Engine selection and source review | Initial research complete |
| Native GOAT-mode startup | First decision reached with pinned core/assets; historical correctness unverified |
| Complete headless duel | Restricted native adapter reaches terminal through `GoatEnvironment`; general card support unfinished |
| Environment contract and illegal-action validation | Implemented |
| Player-visible observation schema | Own hand, initial Main Deck composition, and Extra Deck; public zones, battle position, face-up monster ATK/DEF/counters, chain links, bounded public events, known opponent field and hand cards, public Deck-top reveals, recipient-scoped card reveals, disabled zones, and the public Scapegoat summon restriction; broader reveal and restriction coverage pending |
| Random, heuristic, CLI human agents | Implemented; random agent completes vanilla native duels |
| JSON trajectory round trip | Schema v18 records the final player-visible terminal observation; earlier schemas remain readable. Publicly known opponent hand cards and set-monster control memory are also tracked. Affected old recordings need re-recording for exact replay verification |
| Tournaments | Seeded, seat-swapped sequential and spawned-process runners; paired score intervals and Wilson intervals for supported decks |
| Native throughput benchmark | Measures complete vanilla or sourced-deck duels, reset time, and single-process peak RSS; see `docs/benchmarks.md` |
| Allowed-card asset inventory | All 1,685 pinned whitelist IDs have metadata and a candidate script path; runtime coverage unverified |
| Experimental control probe | One seeded 40-card synthetic control-style deck reaches a native terminal state with full scripts; behavior and visibility unaudited |
| PyTorch policy | Visible-state action scorer with versioned features through the opt-in v16 combat representation; seat-labeled replay-verified imitation and snapshot-pool self-play experiments exist. V16 beat RandomAgent and HeuristicAgent on held-out decks, but a 62-game self-play continuation did not beat its parent. See [evaluation](docs/evaluation.md) |

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

The API is `GoatEnvironment(player1_deck, player2_deck, seed, engine=...)`; `reset()`, `legal_actions()`, `step()`, `is_terminal()`, `result()`, and `trajectory()` are defined. Pass `RestrictedOcgcoreEngine` for the restricted native path. The default engine raises `SimulatorUnavailable` because general GOAT support is unfinished.

## Native setup (Linux)

The M0 probe calls a real, pinned ocgcore build with `DUEL_MODE_GOAT`. Its raw messages stay inside the adapter. The restricted adapter uses player-visible queries and redacts hidden card identities in observations and action parameters. Visibility tests now include a targeted set opponent monster.

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

## View a replay

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

Choose each replay JSON with **Open trajectory**. The catalog viewer embeds names for the 1,685 legal GOAT IDs and generated Tokens from your local card databases; no card database or catalog is committed to Git. A per-replay HTML generated by `render_replay.py` also embeds this catalog, so opening a different JSON in that page keeps names available. Opening the bare `examples/replay_viewer.html` template directly has no database and shows card IDs with a notice explaining how to generate the named viewer.

The renderer also reads card-effect choice text from the local databases, so prompts such as Enemy Controller's two modes have distinct labels. Position and monster-Type choices use names. If a database has no text for a particular option, the viewer labels it by choice number.

The duel board keeps both fields and hands on one screen at desktop sizes; playback controls, legal actions, and other details scroll in the right sidebar. The viewing player is always at the bottom. Use its slider, arrow keys, or Play button to step through decisions; `#decision=11` opens a particular decision. **Prev common** and **Next common** jump to decisions with at least two legal actions involving a card found in five or more of the six sourced tournament Main Decks. This small sample guides review; it does not measure GOAT metagame play rates. Staged card choices show the required selection count and already selected cards. The legal-action list shows 100 entries at a time, with a button for more. New schema-v18 recordings also include a final frame with the terminal field and Life Points; older recordings end on the last decision. Public Deck-top reveals, cards shown only to the acting player, known opponent hand identities, active disabled field zones, and the acting player's starting Deck composition appear on new recordings. Known hand cards are listed in the sidebar without assigning them to hidden hand slots.

Click either **Deck** on the board or a **Graveyard** stack to open a scrollable card popup. Graveyards display their public cards. Your Deck popup displays the recorded *starting* composition and current count; it cannot identify cards remaining in the Deck. The opponent's Deck popup shows only its count. Banished piles have the same popup; concealed cards remain concealed. The duel field has colored zone outlines, card stacks, Life Point badges, and phase indicators inspired by tabletop replay layouts. It animates new cards, flips, draws, attacks, and the current phase; animation respects the browser's reduced-motion setting.

To set up artwork automatically for one replay, cache its visible cards and regenerate the catalog viewer:

```bash
python -m scripts.setup_card_images replays/tournament_verified_18500/game_00029_seed_18500.json
python scripts/render_replay.py --catalog-viewer
xdg-open replays/goat_viewer.html
```

Pass several replay paths to cache their combined card set, for example `replays/tournament_verified_18500/*.json`. The images live in ignored `replays/card_images/` and are loaded locally by the generated viewer. The setup script downloads each small image once at a modest rate from [YGOPRODeck's documented image server](https://ygoprodeck.com/api-guide/); it uses base-card artwork for historical script variant IDs. Artwork is a visual aid: printed card text in a current image may differ from the historical effect enforced by the pinned simulator. You can also use **Card images** at the top of the viewer to select your own local folder of numbered JPG, PNG, or WebP files. The browser reads those files locally and does not upload them; use the picker again after reloading. Without images, names and card backs still display. The viewer does not open EDOPro `.yrp`/`.yrpX` files. Replays and generated HTML live in ignored `replays/`.

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
The previously reported 12,382-decision result was an earlier recorded run;
the cause of the difference has not been isolated. The unchanged pre-change
probe script produces the current 12,006-decision result, so the older hash
is retained only as historical data.
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

