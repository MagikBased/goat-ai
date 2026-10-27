# Simulator and data research (2026-10-24)

## Candidates

| Candidate | Advantages | Gaps / decision |
| --- | --- | --- |
| [Project Ignis / edo9300 ygopro-core](https://github.com/edo9300/ygopro-core) | Native, headless C API; seeded duels; core defines `DUEL_MODE_GOAT`; official Project Ignis scripts are widely used. | Need compile, supply database/scripts, parse all request/response messages, and validate historical rulings and visibility. **Selected engine direction.** Its modifications carry AGPL-3.0-or-later terms; review distribution obligations before shipping linked binaries. |
| [Fluorohydride ygopro-core](https://github.com/Fluorohydride/ygopro-core) | Mature C API and permissive MIT license. | Older branch lacks the explicitly researched GOAT mode; extra historical behavior would need validation or patches. |
| [YGO Agent / ygoenv](https://github.com/sbl1996/ygo-agent) | Headless, parallel EnvPool environment and action observations; Python integration exists; seeded games. | Its EDOPro source currently sets `duel_options_ = DUEL_MODE_MR5` in `ygoenv/ygoenv/edopro/edopro.h`. It also bounds options with `max_options` and supports a subset of cards. Adapting it requires a GOAT build, action and observation audit, and card coverage work. A prebuilt binary cannot simply be assumed GOAT-correct. |
| [WindBot](https://github.com/IceYGO/windbot) | Existing C# agent and duel message-handling examples. | Deck-specific strategies, not a rules engine or general-purpose policy. Useful protocol reference. |

No maintained Python package was verified to expose all ocgcore decisions with historical GOAT rules and safe player views. A direct C API bridge or a carefully patched ygoenv fork are the practical next options. Native workers can later support parallel duels; neither state cloning nor deterministic throughput has been demonstrated here.

**M0 prototype result:** A direct Python `ctypes` bridge to the pinned native core reached `MSG_SELECT_CHAIN` after the first player's six-card opening hand. This favors a direct binding for M1 because it avoids ygoenv's modern-rule hardcoding and fixed maximum option count. At M0, no complete duel, action enumeration, visibility audit, or throughput measurement had been completed. See [native setup](native_setup.md).

**M1 update:** The direct binding now completes narrow fixture duels and validates decks against Project Ignis's pinned [GOAT whitelist](https://github.com/ProjectIgnis/LFLists/blob/master/GOAT.lflist.conf). The list includes GOAT-specific card IDs such as `504700116` for Nobleman of Crossout. These IDs are absent from `cards.cdb` but present in [BabelCDB's `goat-entries.cdb`](https://github.com/ProjectIgnis/BabelCDB/blob/master/goat-entries.cdb), with scripts in [CardScripts' `goat` directory](https://github.com/ProjectIgnis/CardScripts/tree/master/goat). The bridge loads the pinned databases and selected card scripts. [GoatFormat.com's EDOPro guide](https://www.goatformat.com/home/what-is-edopro) explains why imported decks using current official card IDs may need GOAT variants. This does not prove all entries match the community's August 17, 2005 interpretation.

**Card asset inventory:** A pinned local audit of the 1,685 allowed whitelist IDs found metadata for 190 in `goat-entries.cdb`, 1,477 in `cards.cdb`, and 18 in [BabelCDB's `cards-unofficial.cdb`](https://github.com/ProjectIgnis/BabelCDB/blob/master/cards-unofficial.cdb). Among these IDs, 346 are normal monsters, 1,338 have a direct script path at the pinned CardScripts commit, and one alternate Jinzo ID has an alias script path. No allowed ID lacks a metadata row or a candidate script path. This is an inventory, not proof that all scripts load, follow historical TCG rulings, or yield supported native decisions. Reproduce it with `python scripts/audit_card_pool.py` after native setup.

## Historical correctness

[GoatFormat.com's mechanics guide](https://www.goatformat.com/basics.html) documents the first-player draw, historical priority for Ignition effects, field spell behavior, and many other deviations. [Its card pool and banlist](https://www.goatformat.com/cardpool.html) uses the April 2005 TCG Forbidden/Limited list and an August 17, 2005 event card pool. `DUEL_MODE_GOAT` includes flags for first-turn draw, old Ignition behavior, older field-spell handling, and further TCG timing differences in [core constants](https://github.com/edo9300/ygopro-core/blob/master/ocgapi_constants.h). This is promising but is not proof that all card scripts, errata, and rulings match the 2005 TCG. Pin and test concrete engine/database/script revisions before any correctness claim.

Required regression cases: first-turn draw; summon response and Ignition priority; trigger ordering and missed timing; chain resolution; Damage Step activation restrictions; flip effects; summon negation; field spells; representative pre-errata card interactions; and April 2005 deck legality. Ambiguous card-specific rulings need documented source and an explicit project decision.

## Replay and demonstration data

[Project Ignis FAQ](https://github.com/ProjectIgnis/projectignis.github.io/blob/main/faq.html) says old `.yrp` replays re-enact decisions against a matching core and scripts, whereas `.yrpX` stores resulting actions and remains viewable across engine updates. Neither statement guarantees the complete legal action set or each player's knowledge at every choice. The [EDOPro replay header and flags](https://github.com/edo9300/edopro/blob/d0f111d6f3e0d4ee529b88a869ae0a971954bae3/gframe/replay.h) and [container reader](https://github.com/edo9300/edopro/blob/d0f111d6f3e0d4ee529b88a869ae0a971954bae3/gframe/replay.cpp) define `yrp1` as saved Decks plus engine responses and `yrpX` as a packet stream, with optional LZMA compression and an extended four-word seed. GOAT AI has a bounded structural reader for these two EDOPro containers. It returns raw records only for future reconstruction and prints a privacy-preserving summary by default. A public YGOPro `yrp2` sample from [ygopro-yrp-encode](https://github.com/purerosefallen/ygopro-yrp-encode) is a distinct format and is rejected explicitly. Decision reconstruction, legal action recovery, and player-knowledge validation are **not implemented**. No EDOPro replay is yet admitted as a training trajectory. DuelingBook data and video-derived trajectories require rights and a separate extraction pipeline.

The reader was also checked against five actual `.yrpX` files from the
[MIT-licensed Project Echelon repository at commit `cc969ba`](https://github.com/COTFK/project-echelon/tree/cc969ba7ebfa48fbe149287d14aee096e4dfe422/replays),
kept only in ignored local cache. A 2021 file with SHA-256
`1bf72a6f2994e04bf64900c2caeec60e5d148e01eab224cd3cf2cc23a1f30ba5`
parsed as 497 packets; three other 2021–2022 files parsed as 443, 1,825,
and 157 packets; a 2023 extended-header file parsed as 268 packets. The
first real file exposed a difference from Python-produced synthetic LZMA:
EDOPro's raw stream can omit the end marker and emit one to three zero bytes
past the declared uncompressed size. The [upstream reader](https://github.com/edo9300/edopro/blob/d0f111d6f3e0d4ee529b88a869ae0a971954bae3/gframe/replay.cpp)
allocates only the declared output size. Our reader accepts at most eight
extra zero bytes and still rejects nonzero or excessive output; that eight-byte
bound is a defensive parser limit, not an EDOPro format guarantee. These are
modern packet-stream samples, not GOAT duels or demonstrations of recoverable
player decisions. A standalone real `yrp1` file and a permitted GOAT replay
remain unvalidated.

Packet inspection narrows the reconstruction path. All five sampled
`.yrpX` streams had **zero** `MSG_SELECT_*`/selection prompt packets, but each
had one `OLD_REPLAY_MODE` packet (`231`) containing a valid embedded `yrp1`
replay. The embedded files contain 65, 52, 251, 14, and 31 saved responses,
respectively, in the sample order above. The record type and upstream
handling are defined by [EDOPro's `common.h`](https://github.com/edo9300/edopro/blob/d0f111d6f3e0d4ee529b88a869ae0a971954bae3/gframe/common.h)
and [replay parser](https://github.com/edo9300/edopro/blob/d0f111d6f3e0d4ee529b88a869ae0a971954bae3/gframe/replay.cpp).
The intake API can now expose that embedded replay without printing its
private Deck IDs or responses. These five samples show that the packet
stream alone does not supply legal options, while the nested old-mode replay
may permit response reconstruction if the original engine/scripts can be
matched. A response byte sequence still does not identify the corresponding
player-visible observation or all legal actions. Do not train on it without
re-running and validating the duel.

The reader now retains the three `yrp1` duel settings that the pinned upstream
`Replay::ParseParams` reads: starting LP, opening hand size, and cards drawn
per turn. The inspection CLI screens those settings, two-player count, and
the exact native `DUEL_MODE_GOAT` flag value supported by this project. It
uses the embedded `yrp1` settings for `yrpX` when available. All five real
modern samples fail this setup screen: four differ in duel flags alone; the
2023 sample also differs in starting LP and opening hand size. A passing
screen is only a setup candidate. It does not prove a historical ruling,
card legality, the matching core/script revision, player-visible knowledge,
or reconstructible decisions. The CLI still omits player names, Deck IDs,
and response bytes from its report.

The pinned EDOPro [old replay startup](https://github.com/edo9300/edopro/blob/d0f111d6f3e0d4ee529b88a869ae0a971954bae3/gframe/old_replay_mode.cpp)
passes the replay's four 64-bit RNG words to `SetupDuel` and inserts Main and
Extra Deck cards in their recorded order before starting ocgcore. GOAT AI's
normal seeded duels previously applied a separate Python Deck shuffle and
derived the four RNG words from one integer. The native probe now has a
separate replay-start method using exact words and preordered Deck entries.
A native vanilla-fixture regression feeds that method the same inputs as an
ordinary seeded duel and checks every decoded prompt, acting-player view,
response transition, and terminal outcome across the whole duel. This proves
the replay startup path is deterministic on the pinned core. A separate
synthetic `yrp1` fixture now serializes the native responses of an entire
vanilla duel and reconstructs them through the experimental public adapter.
Every response maps to one legal action and the reconstructed observations
match the source native views, except for the adapter's additional public
attacker-slot hint. Altered or incomplete responses fail. The reader retains
custom rule-card IDs internally so this path can reject them; its public
summary reports only their count. This is **synthetic format coverage**, not
established compatibility with a real EDOPro replay, whose original core and
scripts may differ. Ambiguous responses and staged multi-card selections
still fail explicitly. No human demonstration import is claimed. Legacy
headers without four recorded RNG words also need a separately validated
RNG path.

An optional `--goat-whitelist .cache/goat-ai/banlist/GOAT.lflist.conf` screen
reads the embedded Decks and reports only the number of Main/Extra cards
absent from or forbidden by the pinned GOAT list, plus whether both Main
Decks have at least 40 cards. All five real samples fail this screen: their
Main Deck out-of-pool counts are 40, 53, 81, 112, and 12 respectively by
file date. This independently rules them out as GOAT training fixtures.
Passing the screen would only make a replay a candidate: it does not check
copy limits, historical scripts, rules flags, response reconstruction,
player visibility, or permission to train on that gameplay.

Reproduce the first real-file intake check without committing the replay:

```bash
mkdir -p .cache/goat-ai/replay_samples
curl -L --fail 'https://raw.githubusercontent.com/COTFK/project-echelon/cc969ba7ebfa48fbe149287d14aee096e4dfe422/replays/2021-02-15_02-41-18.yrpX' \
  -o .cache/goat-ai/replay_samples/echelon_2021_02_15.yrpX
sha256sum .cache/goat-ai/replay_samples/echelon_2021_02_15.yrpX
.venv/bin/python scripts/inspect_edopro_replay.py \
  .cache/goat-ai/replay_samples/echelon_2021_02_15.yrpX
```

## Licensing

The selected [modern core license](https://github.com/edo9300/ygopro-core/blob/master/LICENSE) includes AGPL-3.0-or-later for modifications and notes upstream MIT code. ygoenv carries MIT/Apache notices. Keep these dependencies external until their precise redistribution terms and asset licenses are documented. The project's MIT license covers only original project code.

