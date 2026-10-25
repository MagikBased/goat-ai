# GOAT AI

Research foundation for a general-purpose Yu-Gi-Oh! GOAT Format agent. A restricted native adapter runs complete duels with 40-card normal-monster decks and selected scripted cards: Pot of Greed, Book of Moon, the GOAT variant of Nobleman of Crossout, and Cannon Soldier. General effect-card support and historical rules validation are unfinished. No competitive playing strength is claimed.

## Status

| Component | Status |
| --- | --- |
| Engine selection and source review | Initial research complete |
| Native GOAT-mode startup | First decision reached with pinned core/assets; historical correctness unverified |
| Complete headless duel | Restricted native adapter reaches terminal through `GoatEnvironment`; general card support unfinished |
| Environment contract and illegal-action validation | Implemented |
| Player-visible observation schema | Own hand, initial Main Deck composition, and Extra Deck; public zones, battle position, chain links, bounded public events, known opponent field cards, public Deck-top reveals, recipient-scoped card reveals, disabled zones, and the public Scapegoat summon restriction; broader reveal and restriction coverage pending |
| Random, heuristic, CLI human agents | Implemented; random agent completes vanilla native duels |
| JSON trajectory round trip | Schema v11 records the player's initial Main Deck as a sorted card multiset alongside recipient-scoped and public reveals; earlier schemas remain readable and replay-verifiable |
| Tournaments | Seeded, seat-swapped sequential and spawned-process runners; paired score intervals and Wilson intervals for supported decks |
| Native throughput benchmark | Implemented for vanilla fixture only; see `docs/benchmarks.md` |
| Allowed-card asset inventory | All 1,685 pinned whitelist IDs have metadata and a candidate script path; runtime coverage unverified |
| Experimental control probe | One seeded 40-card synthetic control-style deck reaches a native terminal state with full scripts; behavior and visibility unaudited |
| PyTorch policy | Version-3 visible-state action scorer uses public known-card slots; seat-labeled verified imitation, snapshot-pool self-play experiment, and held-out evaluation exist; heuristic imitation is a measured baseline, not a strength claim |

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
python scripts/audit_card_pool.py
python scripts/evaluate_native.py --agent-a heuristic --agent-b random --seeds 10
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

The generated HTML is self-contained and shows card names when the pinned card database is installed. The duel board keeps both fields and hands on one screen at desktop sizes; playback controls, legal actions, graveyards, and other details scroll in the right sidebar. The viewing player is always at the bottom. Use its slider, arrow keys, or Play button to step through decisions; `#decision=11` opens a particular decision. Public Deck-top reveals, cards shown only to the acting player, active disabled field zones, and the acting player's starting Deck composition appear on new recordings. You can also open `examples/replay_viewer.html` directly and choose any saved GOAT AI JSON trajectory, in which case cards appear by ID. The viewer has no card art or animations and does not open EDOPro `.yrp`/`.yrpX` files. Replays and generated HTML live in ignored `replays/`.

For a replay that shows a two-zone choice and the resulting disabled Monster Zones, run `python examples/record_ground_collapse.py`, then `python scripts/render_replay.py replays/ground_collapse_3.json` and open `replays/ground_collapse_3.html`. This uses the experimental adapter and verifies the full seeded duel before writing the trajectory.

The play example prints the winner and decision count and optionally writes a JSON trajectory. `--human-seat` uses the same action API for a CLI player. The evaluation command swaps candidate seats for each seed and reports matchup and seat results; see [the evaluation log](docs/evaluation.md). Supported decision types remain limited to the tested decks, and unsupported requests fail explicitly. The default environment still fails closed because general GOAT effects and visibility cases are unfinished. The benchmark includes reset and Python action selection; results are specific to this fixture and machine.

For experimental effect-card coverage, run:

```bash
python scripts/setup_native.py --full-card-scripts
python scripts/probe_control_deck.py --seed 42
python scripts/probe_control_deck.py --seed 0 --seeds 50
python scripts/probe_control_deck.py --deck examples/decks/control_probe.ydk --opponent-deck examples/decks/chaos_probe.ydk --seed 0 --seeds 10
python scripts/probe_random_decks.py --seeds 10 --max-decisions 3000
```

The random-deck probe deterministically generates whitelist-legal 40-card
decks and writes its deck files and JSON report under ignored `.cache/goat-ai/random-probe/`.
It is a native protocol coverage check, not a historical correctness or playing-strength test.
On the pinned assets, seeds 0–9 completed 10/10 duels in 12,382 decisions;
repeating the command produced the same report SHA-256
`8709934ca9d23d88cc0fb8b73fcfccb387d2eaa9097374660bcf6c9a68c730f9`.

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

