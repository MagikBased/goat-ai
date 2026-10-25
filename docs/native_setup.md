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

The pinned CardScripts `utility.lua` has upstream SHA-256 `59ebe317dbec0ef5134f485f039bbe0cee031aa68e6d0ac028123a318ee2cd2a`. At load time the native binding checks that exact hash, then changes the GOAT Deck-confirm recipient from the searching player to the opponent and requires remaining LP to exceed a fixed cost in `Cost.PayLP`. The resulting loaded-script SHA-256 is `04c4555a7491a6fa958688f270e28a3212255cfbc23e390040cfb18969936b24` and is recorded in every replay manifest. The upstream checkout stays unchanged; a different upstream utility script fails closed. This is a modification of an [AGPL-3.0 CardScripts file](https://github.com/ProjectIgnis/CardScripts/blob/master/COPYING), separate from the MIT license for GOAT AI's original code. The recipient choice follows [GoatFormat's historical verification rule](https://www.goatformat.com/basics.html); a Spy-specific primary ruling is still being sought. The cost restriction follows [GOAT Rule #16](https://www.goatformat.com/basics.html); scripts with their own LP-cost code still need individual audits.

The pinned Pot of Greed script has upstream SHA-256 `c827d7f30d746cdd74bdcbdd9ef5d1612fd6fdb6cc07d981b7a780c7231ba6f7`. Its in-memory GOAT draw gate checks `Duel.IsPlayerCanDraw(tp,0)` so a draw-prohibiting effect still blocks activation while too few cards in Deck do not. The loaded-script SHA-256 is `f5fe5f873c46953ff998c04558dfdc0546856e683041204feb647f91bfec9065`. The modification follows [GOAT Rule #16's overdraw clause](https://www.goatformat.com/basics.html). Replay manifests made before this correction have a different effective Pot hash and require fresh recordings for exact verification.

The pinned Graceful Charity script has upstream SHA-256 `12b5a5730b6dea2c1bf3eb379f0d436263786c1ac882e197580e4c72dede3eb5`. The same GOAT overdraw correction changes its activation gate to `Duel.IsPlayerCanDraw(tp,0)` without changing the draw/discard operation. Its loaded-script SHA-256 is `5ab8c1b6aa3dfca5e5409926115089f9a12584f260c1a7e2d31867040e30f89d`. Older replay manifests that loaded Graceful likewise require fresh recordings for exact verification.

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

`OcgcoreProbe.observation(viewer)` queries only the viewer's own hand and counts for the opponent's hand and both decks. It also supplies the viewer's own initial Main Deck composition, sorted by card ID so the input YDK order and shuffled native Deck order cannot enter the observation. Field, graveyard, and banished-zone identities are redacted when facedown to the viewer. Monster attack/defense orientation comes from the native position query. Public `MSG_CHAINING` and `MSG_CHAIN_END` frames populate structured chain links; Book of Moon has an end-to-end chain regression. A bounded `public_history` records observed turn, phase, attack, Damage Step, and chain start/end events, without card IDs. `known_opponent_cards` retains IDs of opponent field cards seen face-up immediately before a public face-down position change; `known_opponent_field_cards` also maps each ID to its controller, field zone, and slot. Public moves to non-field zones, sets, swaps, and set-card shuffles invalidate that slot memory; a known face-down card moved between field slots carries its existing memory to the new slot. If control of a face-down field card changes, both its former controller and new controller can know its identity; the adapter records the addressed move or swap at the new slot, without using raw IDs from ordinary hidden moves. `MSG_CONFIRM_DECKTOP` records public Deck-top reveals; `MSG_CONFIRM_CARDS` records a sorted card multiset only in the addressed player's view, without native Deck sequence numbers. When the addressed reveal identifies a face-down opponent field card, its native field slot is retained as recipient-visible known-card memory while its current field view stays face-down. A Nobleman of Crossout Flip-monster branch checks both recipients and full-duel replay verification. Trap Dustshoot permits opponent-hand card choices only after a fresh recipient-addressed reveal; Exchange retains its reveal across its two consecutive choices. Public `MSG_FIELD_DISABLED` records active zone restrictions. Public `MSG_PLAYER_HINT` add/remove frames for GOAT Scapegoat populate `restrictions` for the affected player until the hint is removed; other restriction hints are not yet interpreted. Native tests compare observations after changing only the opponent deck order and confirm that a never-revealed set monster's ID is hidden. This is an initial visibility boundary; other reveal types, richer action history, and position interactions still need an audit.

`RestrictedOcgcoreEngine` validates 40-card fixture YDK decklists and allows three tested spells plus Cannon Soldier. It maps decoded native choices to `Action`s and keeps response bytes inside the engine. Tests cover terminal outcomes, trajectories, Pot's two-card draw, Book's chain response, Nobleman's banishing of a set monster, redaction of that target's hidden ID, and Cannon Soldier's Ignition priority after a summon. `MSG_SELECT_UNSELECT_CARD` choices are exposed for Cannon Soldier's tribute cost. GOAT variant metadata is read from `goat-entries.cdb` before the main database. Other effects remain unsupported. The bridge shuffles both decks deterministically from the duel seed before inserting cards into the native core, which otherwise draws from the supplied order.

`goat_ai.engine.decks` parses `.ydk` sections and checks main/side sizes, pinned whitelist membership, forbidden/limited/semi-limited counts, aliases, and Fusion Deck placement across all three pinned databases. A pre-errata Dark Magician of Chaos card and script are tested at native startup. The card-pool audit finds metadata and a candidate script path for all 1,685 allowed whitelist IDs. Only selected scripts are fetched by sparse checkout; decks with other effect cards fail explicitly in the restricted adapter. This is an asset and legality gate, not a historical behavior audit.

`ExperimentalOcgcoreEngine` relaxes the audited-card gate for whitelist-legal
main decks of at least 40 cards and Fusion Extra Decks. A 61-card native
startup test checks the absence of a 60-card maximum. It validates Side Deck
cards, requiring 0 or 15 by default; a community policy allows 0–15. Side
cards are unused in a single duel. The adapter still fails on unsupported native
decisions. Its synthetic control-style probe exercises effect cards, generated Sheep Tokens, yes/no,
tribute, position, and race selections. `python scripts/probe_control_deck.py
--seed 42` completes one pinned random duel in 1,116 decisions, winner seat
1. The same synthetic deck completed seeds 0–49 with random actions after
decoding `MSG_SELECT_EFFECTYN`. The 50-seed protocol probe was run in two
batches (0–11 and 12–49); all 50 reached terminal states, with 550–1,454
decisions per duel. These runs do not validate card behavior or strategy. A separate differential test
replaces an opponent's opening-hand effect monster and then sets each version
facedown; the acting player's observations and legal actions agree at both
decision points while private native queries confirm the identities differ.
Another differential fixture sets Dust Tornado versus Sakuretsu Armor from
opponent hands and confirms that the next acting-player observation and legal
actions match while private Spell/Trap Zone queries show different identities.
An end-to-end Dust Tornado fixture then chooses between two set opponent Traps,
one with alternate hidden identities. The target-selection observations and
two-action lists match, each action carries only the public zone and slot, and
selecting the changed slot destroys the actual target in either duel.
This is an initial visibility regression, not a full information-flow audit.
Generic yes/no, effect yes/no, and indexed option requests now carry native
prompt identifiers
in structured actions. Those identifiers are not yet mapped to readable
historical card text; their information boundary still needs an audit. Card
effects, hidden-information memory, untested requests, Extra Deck effect
interactions, sideboarding, and historical rulings remain unaudited. Do not use the experimental adapter for
policy training or competitive claims.

The synthetic `examples/decks/chaos_probe.ydk` adds search, discard, and
Special Summon effects plus three Fusion cards. Against the control probe,
ten seeded random duels reached terminal in each seat order (20/20) on the
pinned assets. The observed decision counts were 584–1,255 with control in
seat 0 and 866–1,194 with Chaos in seat 0. A test gates four seeds per seat
order. These paths do not demonstrate that every effect in either deck was
activated. The observation now includes the acting player's own Fusion Deck
identities. A differential test changes only the opponent's Fusion cards and
confirms the acting player's observation and legal actions stay identical.

Use this binding for M1 unless broader protocol coverage or measured throughput shows a concrete reason to adopt a patched ygoenv fork. Expand request and response handling, effect-card support, and visibility audits before claiming general GOAT coverage.
