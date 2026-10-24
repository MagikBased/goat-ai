# M0 native GOAT-mode probe

The probe in `goat_ai.engine.ocgcore_probe` calls the native C API through Python `ctypes`. It starts a seeded duel, loads cards and global scripts, processes native messages, and checks public counts. It now decodes a small subset of decisions and constructs a redacted observation for those states. It is **not** the general `GoatEnvironment` adapter. Raw core messages may contain private data and must stay inside the native layer.

## Pinned external sources

| Dependency | Revision | Use / license |
| --- | --- | --- |
| [edo9300/ygopro-core](https://github.com/edo9300/ygopro-core) | `baa3881d0bae48e9994f915f5c931be53c1ba8ef` | C++ duel core, AGPL-3.0-or-later modifications plus upstream MIT notices |
| [lua/lua](https://github.com/lua/lua) | `6e22fedb74cf0c9b6656e9fce8b7331db847c605` | Core's pinned submodule; see upstream license |
| [ProjectIgnis/CardScripts](https://github.com/ProjectIgnis/CardScripts) | `196eb043514e2cbc23ff891e3cfe31b89765ce49` | Global scripts and selected official/GOAT card scripts; see upstream license |
| [ProjectIgnis/BabelCDB](https://github.com/ProjectIgnis/BabelCDB) | `19339149fa5ee509327023f15a81d8ba4164c5a1` | Main, GOAT-variant, and unofficial/pre-errata card metadata; see upstream terms |
| [ProjectIgnis/LFLists](https://github.com/ProjectIgnis/LFLists) | `b95e30d7453bb9e692a08ae3081aeceb70582341` | GOAT whitelist and copy limits; see upstream terms |

The `cards.cdb` SHA-256 is `d5166c35296a6c65dcc0230c7bc0e9f25721639159b80fa78bf724be61183a6a`; `goat-entries.cdb` is `042ffc3de692245d13d144656a79a34cb114d291ddd0c93a21bee9c0e607b4b4`; `cards-unofficial.cdb` is `7753f01785fbf174be2ec3833610306b02a8ce2cb45ac09339ea50afe164bb6a`; `GOAT.lflist.conf` is `2159b6eb0868816860c4913571b514c27fd777755a09c358f250e6cc7cc5db37`. The GOAT flag value for the pinned API is `34226374444` (`DUEL_MODE_GOAT`). Setup checks all asset hashes and the binding checks API version 11.0. The pinned Lua submodule revision is supplied by the core commit.

Requires Linux, Git, a C++17 compiler, Python 3.10+, Meson 1.7+, and Ninja. From a clean clone:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,native]'
python scripts/setup_native.py
python scripts/probe_native.py --seed 42
python scripts/run_native_smoke.py --seed 42
python scripts/audit_card_pool.py
GOAT_AI_NATIVE_ROOT=.cache/goat-ai python -m pytest -q tests/test_ocgcore_probe.py
```

`setup_native.py` fetches the exact commits into ignored `.cache/goat-ai` and builds `libocgcore.so`. The first decision should be native message `16` (`MSG_SELECT_CHAIN`) for player 0, after draw events `(player 0, five)`, `(player 1, five)`, and `(player 0, one)`. Query counts should be hands `(6, 5)` and decks `(34, 35)` from 40-card starting decks. This checks startup behavior only; it does not establish historical ruling accuracy or legal-action completeness. The fixture passes the pinned Project Ignis GOAT whitelist, which still needs independent historical validation.

The core requests `c0.lua` and individual scripts even for vanilla monsters and generated Tokens; the probe accepts absent scripts only for `c0.lua`, database type-17 normal monsters, and Token cards. Missing effect scripts and global scripts fail. Assets are not committed or redistributed by this project.

`python scripts/setup_native.py --full-card-scripts` checks out the pinned
official, unofficial, GOAT, and pre-errata script directories for experimental
probes. The default keeps the small sparse checkout. Setup uses the Meson
executable beside the active Python interpreter when present, so an older
system Meson does not open a newer build directory.

## Protocol findings and next boundary

Native messages are length-prefixed binary frames. The first processed sequence includes opening draws, turn and phase changes, the first-turn draw, then `MSG_SELECT_CHAIN`. The adapter still must parse more request types and provide complete player-scoped redacted observations. The core's query functions can expose complete internal state, so calling them does not itself enforce information boundaries. Narrow complete-duel throughput has been measured in [the benchmark log](benchmarks.md); state cloning and broad historical card behavior remain unmeasured.

The direct `ctypes` path reaches the first decision with a small binding and no fixed action-list size. A narrow smoke runner now decodes zero-option chain windows, idle actions, and single-card selections, and completes a vanilla-fixture duel by ending turns and discarding at hand limit. The fixture has 40 cards, at most three copies each, and passes the pinned Project Ignis GOAT whitelist. Seed 42 terminates after 350 decisions with player 1 winning by deck-out. This is a real native duel; it does not cover arbitrary cards, full legal-action enumeration, or an agent-facing environment. Raw native choices remain internal. The smoke runner is a protocol regression, not a performance benchmark.

`OcgcoreProbe.observation(viewer)` queries only the viewer's own hand and counts for the opponent's hand and both decks. Field, graveyard, and banished-zone identities are redacted when facedown to the viewer. Monster attack/defense orientation comes from the native position query. Public `MSG_CHAINING` and `MSG_CHAIN_END` frames populate structured chain links; Book of Moon has an end-to-end chain regression. Native tests compare observations after changing only the opponent deck order and confirm that a set monster's ID is hidden from the opponent. This is an initial visibility boundary; private reveals, full action history, and all position interactions still need an audit.

`RestrictedOcgcoreEngine` validates 40-card fixture YDK decklists and allows three tested spells plus Cannon Soldier. It maps decoded native choices to `Action`s and keeps response bytes inside the engine. Tests cover terminal outcomes, trajectories, Pot's two-card draw, Book's chain response, Nobleman's banishing of a set monster, redaction of that target's hidden ID, and Cannon Soldier's Ignition priority after a summon. `MSG_SELECT_UNSELECT_CARD` choices are exposed for Cannon Soldier's tribute cost. GOAT variant metadata is read from `goat-entries.cdb` before the main database. Other effects remain unsupported. The bridge shuffles both decks deterministically from the duel seed before inserting cards into the native core, which otherwise draws from the supplied order.

`goat_ai.engine.decks` parses `.ydk` sections and checks main/side sizes, pinned whitelist membership, forbidden/limited/semi-limited counts, aliases, and Fusion Deck placement across all three pinned databases. A pre-errata Dark Magician of Chaos card and script are tested at native startup. The card-pool audit finds metadata and a candidate script path for all 1,685 allowed whitelist IDs. Only selected scripts are fetched by sparse checkout; decks with other effect cards fail explicitly in the restricted adapter. This is an asset and legality gate, not a historical behavior audit.

`ExperimentalOcgcoreEngine` relaxes the audited-card gate for whitelist-legal
main decks of at least 40 cards and Fusion Extra Decks. A 61-card native
startup test checks the absence of a 60-card maximum. It validates Side Deck
cards, requiring 0 or 15 by default; a community policy allows 0–15. Side
cards are unused in a single duel. The adapter still fails on unsupported native
decisions. Its synthetic control-style probe exercises effect cards, generated Sheep Tokens, yes/no,
tribute, position, and race selections. `python scripts/probe_control_deck.py
--seed 42` completes one pinned random duel in 1,251 decisions, winner seat
1. This covers that seed and action path only. A separate differential test
replaces an opponent's opening-hand effect monster and then sets each version
facedown; the acting player's observations and legal actions agree at both
decision points while private native queries confirm the identities differ.
This is an initial visibility regression, not a full information-flow audit.
Yes/no and indexed option requests now carry their native prompt identifiers
in structured actions. Those identifiers are not yet mapped to readable
historical card text; their information boundary still needs an audit. Card
effects, hidden-information memory, untested requests, Extra Deck effect
interactions, sideboarding, and historical rulings remain unaudited. Do not use the experimental adapter for
policy training or competitive claims.

Use this binding for M1 unless broader protocol coverage or measured throughput shows a concrete reason to adopt a patched ygoenv fork. Expand request and response handling, effect-card support, and visibility audits before claiming general GOAT coverage.
