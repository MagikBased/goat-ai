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

### EDOPro live-client bridge probe (2026-10-30)

The active [Project Ignis WindBot fork](https://github.com/ProjectIgnis/windbot)
is an EDOPro-compatible room client. At inspected commit
`bffe6b62679c8b2fafea8f59740e03a132517da4`, its
[`BinaryClient`](https://github.com/ProjectIgnis/windbot/blob/bffe6b62679c8b2fafea8f59740e03a132517da4/YGOSharp.Network/BinaryClient.cs)
uses a two-byte little-endian payload length, excluding the header, with
maximum payload 65,535 bytes. The payload begins with a one-byte packet type.
[`GameClient`](https://github.com/ProjectIgnis/windbot/blob/bffe6b62679c8b2fafea8f59740e03a132517da4/Game/GameClient.cs)
sends player info and room join/create packets, and
[`GameBehavior`](https://github.com/ProjectIgnis/windbot/blob/bffe6b62679c8b2fafea8f59740e03a132517da4/Game/GameBehavior.cs)
answers duel prompts with `CtosMessage.Response`. Our optional
`goat_ai.edopro.framing` implements and tests only this outer packet boundary;
it has not connected to a room, parsed duel prompts, or produced a training
trajectory. The inspected source remains outside the repository and no bot
code has been copied.

The Project Ignis [FAQ](https://github.com/ProjectIgnis/projectignis.github.io/blob/main/faq.html)
says its packaged WindBot supports Master Rule 3 and later and forcing older
rules is unsupported. EDOPro itself can host GOAT, but whether a custom GOAT AI
client can complete a GOAT room duel remains an integration test, not a proven
capability. No EDOPro installation was found in the current local workspace.
The next verification is a local GOAT room connection with one legal decision
and exact core/script/card-ID comparison. A bot-side packet trace alone cannot
label the human's legal choices; server-side logging or validated legacy replay
reconstruction is required for that.

An official [41.0.2 Linux game folder](https://github.com/ProjectIgnis/edopro-assets/releases/tag/41.0.2)
was unpacked in ignored local cache after its published MD5
`4d05c408a4732cfe8dd0d16ad97342bf` matched. The read-only
`scripts/check_edopro_install.py` preflight found the EDOPro executable,
WindBot, GOAT scripts, and a main card database in `expansions/`, but no
GOAT banlist. Its bundled core SHA-256 is
`dcb3bb77230d2cc57bb5440c3ee0c2abee870a727a939c63529837ffb103b043`,
versus the project's pinned native core
`48763d36b1beba3ce37782d7d41cbee58fefe8f65573ab53090e319674bc5358`.
The main database bytes differ as well. Byte differences alone do not prove
wrong GOAT behavior; they mean exact parity and replay reconstruction cannot
be assumed. Local EDOPro room probes are described below; none has been
admitted for training.
Run the preflight with `python scripts/check_edopro_install.py /path/to/ProjectIgnis
--native-root .cache/goat-ai`; its report is an inventory, not a GOAT
correctness verdict.

An external [ygo-agent headless host](https://github.com/mostwanted7/ygo-agent)
at commit `c017f3c20d78b01e6398a41d33e023cf20236ae1` provides an EDOPro
LAN room and direct-core seats. It is AGPL-3.0-or-later and remains in ignored
local cache, not in this MIT repository. Its `selfplay-direct --rules goat`
completed a one-game smoke test on the official 41.0.2 package with two
historical tournament Decks: **51 turns, 1,109 responses, zero retries, zero
reported Lua errors, 0.50 s duel time**. The random seats ended by deck-out;
this says nothing about playing strength. The host rejected the first Deck's
16-card Fusion Deck under its default 0–15 Extra Deck validator, despite
[GOAT's unlimited Fusion Deck rule](https://www.goatformat.com/basics.html).
The smoke test used its explicit `--no-check-deck` option and independently
screened the generated replay against this project's GOAT whitelist and native
Deck validator; both screens passed. Do not use the bypass without that
separate check.

The produced `.yrpX` has SHA-256
`2c00d714ff149431ae4c760d4acd7b255992815d2ba83b6271de806abf61ae60`.
The host re-simulated all **8,480** replay messages identically on its bundled
core, demonstrating deterministic replay there. Our pinned native core failed
to reconstruct at response 92 (`illegal_saved_response`), consistent with the
different core and asset revisions reported by the preflight. This is a real
EDOPro-compatible replay container generated by a local bot duel, not an
authorized human demonstration. This particular duel had no desktop client,
and GOAT AI's PyTorch policy was not connected.

A second local probe exercised the host's actual TCP room protocol at
`127.0.0.1` with its own EDOPro-compatible Python client in the human seat
and a local random policy in the other seat. The room advertised GOAT flags,
used the pinned GOAT banlist copied into the ignored package, and allowed a
16-card Fusion Deck via GOAT-specific deck-size bounds while retaining content
checking. It completed **34 turns and 715 responses**, with zero retries and
zero reported Lua errors; the network client received **6,131** game packets
and a `.yrpX`. That replay's SHA-256 is
`6343f1ef23f56b2d9ca213c0d2b4f90a3689cf34836d4acc880833cd71b80be9`.
The host re-simulated all **5,338** saved replay messages identically. Our
GOAT setup and native Deck screens passed, but pinned-core response
reconstruction failed at response 289 (`illegal_saved_response`). This proves
the external room path can carry a GOAT duel, not that the GOAT AI policy works
over it. The Python client and external host source
remain in ignored cache and are not part of the project's MIT code.

A third probe connected the **actual EDOPro 41.0.2 desktop client** to a
private localhost GOAT room hosted by the same external process. The desktop
client selected a 42-card historical Gravekeeper Deck, won rock-paper-scissors,
chose to go first, set Gravekeeper's Spy in its center monster zone, and ended
the turn. The random AI then took its turn. The human surrendered on turn 3;
the host recorded **23 responses, zero retries, zero reported Lua errors** and
saved `.yrpX` plus a readable event log. The host log records the human's
`SELECT_IDLECMD` monster set, `SELECT_PLACE` center-zone choice, and the
resulting set card. This verifies a real desktop client can join and exchange
decisions with the GOAT room. It does **not** verify a complete played match,
a GOAT AI policy seat, historical accuracy, or a training-ready trajectory.
The test used a Deck without Scapegoat: an earlier desktop trial using it
stopped on a missing Sheep Token script (`c73915052.lua`) in the downloaded
package. That asset gap needs to be fixed or checked before broader Deck use.
The host replay SHA-256 was
`e9cb4f2c5c57adb5b503e205bebe82fb35179a70f66c039dbabd6b7bafdded07`;
our structural reader accepted it but marked it `training_ready: false`.
The EDOPro client's separately saved `.yrpX` appends two bytes after the raw
LZMA end marker. The bounded structural reader now accepts that trailer; it
read **235 packets and 23 embedded responses** from each file, with the
packets and responses exactly equal. The two files have different hashes, and
this structural result does not validate legal-choice or visibility recovery.
The event log and replay remain in ignored local cache; no third-party assets
or demonstrations were added to the repository.

For an exact-install comparison, a separate ignored root linked the 41.0.2
`libocgcore.so`, `expansions/` card databases, `script/`, and GOAT list into
the adapter's expected directory layout. The strict historical reconstruction
correctly refused this root because its `utility.lua` differs from the pinned
script required by our historical patches. An explicit
`--compare-external-unpatched` option now loads those external scripts unchanged
and is barred from strict GOAT intake. On a **complete 33-turn, 627-response**
random duel made by that install without Scapegoat, it reconstructed **all 627
responses** and passed the player-visible decision audit. This demonstrates
that the adapter can map a same-install EDOPro response stream; it does not
establish that the external scripts implement historical GOAT rulings. On the
desktop human trial, the same comparison reached the end of the saved response
stream and reported `incomplete_saved_responses`, as expected for the human's
surrender before a native duel terminal. The host log, rather than the legacy
response stream, records that surrender. Neither comparison is admitted to
training. The next data gate is a complete desktop-client duel with a
version-matched historical core, then a visibility audit of every decision.

An explicit `--allow-partial-reconstruction` mode now audits saved decisions
without requiring a native terminal state. On both the host and desktop
copies of the three-turn surrendered duel, paired with the same external
install and `--compare-external-unpatched`, it mapped **all 23 responses** to
23 legal, player-visible decisions and passed their visibility checks. The
report marks `conditional_native_reconstruction: partial`,
`native_terminal: false`, and `training_ready: false`; strict GOAT intake
rejects the partial option. This can help review human choices from an
interrupted match, but it supplies no verified terminal reward or historical
GOAT certification. A follow-up desktop trial with a 40-card normal-monster
Deck ended on turn 3 when the client disconnected during a required hand
discard; the host logged 22 responses and zero Lua errors. It did not
establish the complete desktop-duel gate. The next desktop run needs a
reliable way to answer all interactive prompts, including hand-size discard.

[Project Ignis FAQ](https://github.com/ProjectIgnis/projectignis.github.io/blob/main/faq.html) says old `.yrp` replays re-enact decisions against a matching core and scripts, whereas `.yrpX` stores resulting actions and remains viewable across engine updates. Neither statement guarantees the complete legal action set or each player's knowledge at every choice. The [EDOPro replay header and flags](https://github.com/edo9300/edopro/blob/d0f111d6f3e0d4ee529b88a869ae0a971954bae3/gframe/replay.h) and [container reader](https://github.com/edo9300/edopro/blob/d0f111d6f3e0d4ee529b88a869ae0a971954bae3/gframe/replay.cpp) define `yrp1` as saved Decks plus engine responses and `yrpX` as a packet stream, with optional LZMA compression and an extended four-word seed. GOAT AI has a bounded structural reader for these two EDOPro containers and conditional native response reconstruction tested on synthetic GOAT duels. The reader prints a privacy-preserving summary by default. A public YGOPro `yrp2` sample from [ygopro-yrp-encode](https://github.com/purerosefallen/ygopro-yrp-encode) is a distinct format and is rejected explicitly. Real EDOPro replay compatibility and player-knowledge validation are **not established**. No EDOPro replay is yet admitted as a training trajectory. DuelingBook data and video-derived trajectories require rights and a separate extraction pipeline.

Another MIT-licensed [YGOPro/YGOPro2 replay parser](https://github.com/RemarkWang/yrp-parser)
documents `.yrp2`, embedded `.yrp1`, and `.yrp3d` spectator streams. Its
engine driver may synthesize responses when the recording and current engine
disagree or the saved responses run out. That is useful for a human-readable
log, but synthetic continuation cannot supply exact player decisions for
imitation. Its target formats and YGOPro2 engine differ from the EDOPro
`.yrp`/`.yrpX` path tested here; no parser code has been copied or adopted.

[Goat World's match archive](https://goatworld.community/matches) describes
downloadable GOAT replays, but the pages checked here did not expose a direct
file fixture, and I found no express grant of external model-training rights
in its [terms](https://goatworld.community/legal/terms). Similarly,
[Goat Format's terms](https://beta.goatformat.com/terms) let the site publish
submitted replays as tournament records; I infer that this does not authorize
an unrelated project to train on them. We will seek a replay provided by its
recorder with an explicit scope of permission, keep it out of Git, and
separately test native compatibility.
See [replay contributions](replay_contributions.md) for the intake steps.

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
player decisions. A permitted real GOAT replay remains unvalidated.

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

A separate, actual standalone `.yrp` file from the public
[BOSS-3000 replay repository at commit `7b56a7b`](https://github.com/BOSS-3000/ygopro-replays-by-BOSS/blob/7b56a7b9c344b5ae020ca8d714ff863f30443c6c/FROGZ%20OTK%20ROCK%20STUN.yrp)
was checked read-only in ignored local cache. Its SHA-256 is
`3f3c2ffcdbe836387739355b4aecd76f28a8117cff5b119c59145d3dc79dfaae`.
The structural reader found two 40-card Main Decks, two 15-card Extra Decks,
and 248 saved responses. Its duel flags differ from the supported GOAT
profile; 65 Main and all 30 Extra Deck entries fall outside the pinned GOAT
whitelist, and both Decks fail the native GOAT validator. This confirms that
the reader can parse one real standalone legacy container, **not** that the
saved responses reconstruct on the pinned core or that the game is GOAT.
Its old header also records no four-word RNG state for the current native
reconstruction path. That is a separate compatibility limit after the GOAT
setup failure.
The source repository does not identify a redistribution or training license,
so this file is not committed or admitted as a demonstration. Reproduce the
read-only screen with the pinned source revision:

```bash
curl -L --fail \
  'https://raw.githubusercontent.com/BOSS-3000/ygopro-replays-by-BOSS/7b56a7b9c344b5ae020ca8d714ff863f30443c6c/FROGZ%20OTK%20ROCK%20STUN.yrp' \
  -o .cache/goat-ai/replay_samples/boss_frogz_rock_stun.yrp
PYTHONPATH=src:. .venv/bin/python scripts/inspect_edopro_replay.py \
  .cache/goat-ai/replay_samples/boss_frogz_rock_stun.yrp \
  --native-deck-screen .cache/goat-ai
```

The reader now retains the three `yrp1` duel settings that the pinned upstream
`Replay::ParseParams` reads: starting LP, opening hand size, and cards drawn
per turn. The inspection CLI screens those settings, two-player count, the
exact native `DUEL_MODE_GOAT` flag value, recorded RNG words, unsupported
replay modes, custom rule cards, and agreement between a `yrpX` wrapper and
its embedded legacy startup. It uses the embedded `yrp1` settings for `yrpX`
when available. All five real modern samples fail this setup screen: all five
differ in duel flags; four lack the four-word RNG state, three also use an
unsupported legacy replay mode, and the 2023 sample differs in starting LP
and opening hand size. The standalone 2012 sample also lacks RNG words. A passing
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
scripts may differ. Synthetic GOAT Thunder Dragon searches for zero, one,
and two copies and a Puppet Magic sum choice now replay under forced staged
action enumeration: one saved native response can become several public
decision records before its exact response is committed. Ambiguous or
invalid responses still fail explicitly. No human demonstration import is
claimed. The reconstructor now accepts either a standalone legacy replay
or one embedded in `.yrpX`; it rejects disagreement in player count, rules
flags, or recorded RNG words between the wrapper and embedded replay, and
retains both file hashes. The optional `--reconstruct-native` inspection
mode reports only a match/fail status, decision and response counts, and a
hash of the loaded-asset manifest. It never exports card IDs or marks a
replay as training ready. Legacy headers without four recorded RNG words
also need a separately validated RNG path.

Conditional reconstruction now checks that every recovered choice is in its
player-visible legal set and runs the existing decision visibility audit before
reporting a match. An injected visibility failure makes both reconstruction and
the privacy-preserving CLI fail closed. This audits the reconstructed adapter
output; it cannot establish what a real player knew in an original EDOPro
recording made with different core or script versions.

An optional `--goat-whitelist .cache/goat-ai/banlist/GOAT.lflist.conf` screen
reads the embedded Decks and reports only the number of Main/Extra cards
absent from or forbidden by the pinned GOAT list, plus whether both Main
Decks have at least 40 cards. All five real samples fail this screen: their
Main Deck out-of-pool counts are 40, 53, 81, 112, and 12 respectively by
file date. This independently rules them out as GOAT training fixtures.
The screen also counts exact card-ID copies across each player's Main and
Extra Deck and rejects counts above the pinned whitelist limit. It reports
only the total excess count. The optional `--native-deck-screen
.cache/goat-ai` uses the pinned card databases and the same GOAT deck
validator as native duels. It additionally rejects alias-equivalent cards
that exceed a shared copy limit and non-Fusion cards in the Extra Deck,
without printing card IDs or rejection details. A native test checks both
cases. The parsed legacy Deck record does not contain Side Decks, so this
still cannot validate a complete tournament Deck submission.
Passing either screen would only make a replay a candidate: it does not check
historical scripts, rules flags, response reconstruction, player visibility,
Side Deck legality, or permission to train on that gameplay.

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

