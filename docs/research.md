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
player decisions. A real `yrp1` sample and a permitted GOAT replay remain
unvalidated.

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

