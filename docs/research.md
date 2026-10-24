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

**M1 update:** The direct binding now completes a narrow vanilla-fixture duel and validates that fixture against Project Ignis's pinned [GOAT whitelist](https://github.com/ProjectIgnis/LFLists/blob/master/GOAT.lflist.conf). The list includes GOAT-specific pre-errata card IDs, so alias and script compatibility need explicit checks before broader deck support. This does not prove all entries match the community's August 17, 2005 interpretation.

## Historical correctness

[GoatFormat.com's mechanics guide](https://www.goatformat.com/basics.html) documents the first-player draw, historical priority for Ignition effects, field spell behavior, and many other deviations. [Its card pool and banlist](https://www.goatformat.com/cardpool.html) uses the April 2005 TCG Forbidden/Limited list and an August 17, 2005 event card pool. `DUEL_MODE_GOAT` includes flags for first-turn draw, old Ignition behavior, older field-spell handling, and further TCG timing differences in [core constants](https://github.com/edo9300/ygopro-core/blob/master/ocgapi_constants.h). This is promising but is not proof that all card scripts, errata, and rulings match the 2005 TCG. Pin and test concrete engine/database/script revisions before any correctness claim.

Required regression cases: first-turn draw; summon response and Ignition priority; trigger ordering and missed timing; chain resolution; Damage Step activation restrictions; flip effects; summon negation; field spells; representative pre-errata card interactions; and April 2005 deck legality. Ambiguous card-specific rulings need documented source and an explicit project decision.

## Replay and demonstration data

[Project Ignis FAQ](https://github.com/ProjectIgnis/projectignis.github.io/blob/main/faq.html) says old `.yrp` replays re-enact decisions against a matching core and scripts, whereas `.yrpX` stores resulting actions and remains viewable across engine updates. Neither statement guarantees the complete legal action set or each player's knowledge at every choice. Replay ingestion must reconstruct decisions with a pinned simulator and validate visibility; it is **not implemented**. DuelingBook data and video-derived trajectories require rights and a separate extraction pipeline. This repository serializes only its own structured trajectories.

## Licensing

The selected [modern core license](https://github.com/edo9300/ygopro-core/blob/master/LICENSE) includes AGPL-3.0-or-later for modifications and notes upstream MIT code. ygoenv carries MIT/Apache notices. Keep these dependencies external until their precise redistribution terms and asset licenses are documented. The project's MIT license covers only original project code.

