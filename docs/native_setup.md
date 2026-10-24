# M0 native GOAT-mode probe

The probe in `goat_ai.engine.ocgcore_probe` calls the native C API through Python `ctypes`. It starts a seeded duel, loads cards and global scripts, processes native messages until the first response request, and checks public counts. It does **not** decode legal actions or provide a player-visible observation. Raw core messages may contain private data.

## Pinned external sources

| Dependency | Revision | Use / license |
| --- | --- | --- |
| [edo9300/ygopro-core](https://github.com/edo9300/ygopro-core) | `baa3881d0bae48e9994f915f5c931be53c1ba8ef` | C++ duel core, AGPL-3.0-or-later modifications plus upstream MIT notices |
| [lua/lua](https://github.com/lua/lua) | `6e22fedb74cf0c9b6656e9fce8b7331db847c605` | Core's pinned submodule; see upstream license |
| [ProjectIgnis/CardScripts](https://github.com/ProjectIgnis/CardScripts) | `196eb043514e2cbc23ff891e3cfe31b89765ce49` | Global Lua scripts; see upstream license |
| [ProjectIgnis/BabelCDB](https://github.com/ProjectIgnis/BabelCDB) | `19339149fa5ee509327023f15a81d8ba4164c5a1` | Card metadata; see upstream terms |
| [ProjectIgnis/LFLists](https://github.com/ProjectIgnis/LFLists) | `b95e30d7453bb9e692a08ae3081aeceb70582341` | GOAT whitelist and copy limits; see upstream terms |

The `cards.cdb` SHA-256 is `d5166c35296a6c65dcc0230c7bc0e9f25721639159b80fa78bf724be61183a6a`; the `GOAT.lflist.conf` SHA-256 is `2159b6eb0868816860c4913571b514c27fd777755a09c358f250e6cc7cc5db37`. The GOAT flag value for the pinned API is `34226374444` (`DUEL_MODE_GOAT`). Setup checks both asset hashes and the binding checks API version 11.0. The pinned Lua submodule revision is supplied by the core commit.

Requires Linux, Git, a C++17 compiler, Python 3.10+, Meson 1.7+, and Ninja. From a clean clone:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,native]'
python scripts/setup_native.py
python scripts/probe_native.py --seed 42
python scripts/run_native_smoke.py --seed 42
GOAT_AI_NATIVE_ROOT=.cache/goat-ai python -m pytest -q tests/test_ocgcore_probe.py
```

`setup_native.py` fetches the exact commits into ignored `.cache/goat-ai` and builds `libocgcore.so`. The first decision should be native message `16` (`MSG_SELECT_CHAIN`) for player 0, after draw events `(player 0, five)`, `(player 1, five)`, and `(player 0, one)`. Query counts should be hands `(6, 5)` and decks `(34, 35)` from 40-card starting decks. This checks startup behavior only; it does not establish historical ruling accuracy or legal-action completeness. The fixture's card-pool legality remains unverified.

The core requests `c0.lua` and individual scripts even for vanilla monsters; the probe accepts absent scripts only for `c0.lua` and database type-17 normal monsters. Missing effect scripts and global scripts fail. Assets are not committed or redistributed by this project.

## Protocol findings and next boundary

Native messages are length-prefixed binary frames. The first processed sequence includes opening draws, turn and phase changes, the first-turn draw, then `MSG_SELECT_CHAIN`. The next adapter must parse every request type, choose a response using the engine's response protocol, and provide player-scoped redacted observations. The core's query functions can expose complete internal state, so calling them does not itself enforce information boundaries. State cloning, complete-game throughput, and historical card behavior remain unmeasured.

The direct `ctypes` path reaches the first decision with a small binding and no fixed action-list size. A narrow smoke runner now decodes zero-option chain windows, idle actions, and single-card selections, and completes a vanilla-fixture duel by ending turns and discarding at hand limit. The fixture has 40 cards, at most three copies each, and passes the pinned Project Ignis GOAT whitelist. Seed 42 terminates after 350 decisions with player 1 winning by deck-out. This is a real native duel; it does not cover arbitrary cards, full legal-action enumeration, safe player observations, or an agent-facing environment. Raw native choices remain internal. The smoke runner is a protocol regression, not a performance benchmark.

`goat_ai.engine.decks` parses `.ydk` sections and checks main/side sizes, pinned whitelist membership, forbidden/limited/semi-limited counts, and aliases in the pinned database. This is an initial deck legality gate. The whitelist and card data still need an independent historical audit, and effect-card scripts are not yet fetched by the sparse M0 setup.

Use this binding for M1 unless broader protocol coverage or measured throughput shows a concrete reason to adopt a patched ygoenv fork. Implement full response handling and player-visible observation construction before connecting it to `GoatEnvironment`.
