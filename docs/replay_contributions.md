# Contributing GOAT replay data

## Record your own local GOAT duel

The local browser server also offers `/games/play` for a game against Random,
Tactical, or the selected neural policy. Start it with
`./start_review_viewer.sh --game-creator`, then follow **Play against an AI in
your browser**. Completed games save a verified `human_web` trajectory in
`.cache/goat-ai/user_games/`, with `authorization=self_recorded` and only your
seat admitted as raw imitation data. AI opponent decisions remain in the
replay for verification but are not treated as human labels. The live choice
API binds every submitted action to a decision number, rejecting delayed or
duplicate actions after the game has advanced. Unfinished games are not saved
across server restarts.

`examples/play_goat.py` accepts two GOAT YDK Decks and records one CLI human
seat against a RandomAgent, TacticalHeuristicAgent, or saved policy. It shows
only the acting player's observation and numbered legal actions; long lists
can be paged with `n`/`p` or searched with `/text`. A completed
duel is written to an ignored local trajectory only after exact native replay
verification and the player-visibility audit; a failed check removes the
temporary file. The trajectory records `source=human_cli`,
`authorization=self_recorded`, the human seat, and opponent provenance. This
is an authorized self-recording path, separate from imported EDOPro or
DuelingBook material. See [README](../README.md#play-and-record-a-goat-duel)
for the command.

A complete local EDOPro desktop room duel has been reconstructed against the
matching pinned native assets. The local game page can launch that room and
save explicitly confirmed human-seat choices. The experimental clone command
can use only those confirmed choices from a complete pinned-room recording
with GOAT-legal Main and Extra Decks;
raw or arbitrary external EDOPro replays are still excluded. See the
[EDOPro room instructions](../README.md#experimental-edopro-room).

## Useful first sample

If you recorded a duel yourself in EDOPro, save its original `.yrp` or
`.yrpX` file. A complete two-player duel using the client's GOAT rules mode,
April 2005 card pool, 8000 starting LP, five-card opening hand, and one draw
per turn is most useful. Include the EDOPro version or approximate recording
date and any known card-script update version. Do not edit the binary replay
or publish either player's private Deck without their permission.

Please state one of these permission scopes when sharing the file:

- **Parser testing only:** we may inspect the replay locally to test format,
  rules flags, and reconstruction, but may not use its decisions for training.
- **Training and parser testing:** both players authorize local research
  training on this replay's decisions and publication of aggregate findings.
  We will still keep the raw replay and derived trajectories out of Git.

If a replay came from another player, tournament, or website, obtain the
recording rights holder's permission for the intended scope. Public access to
a replay does not establish permission to train on it.

## Local inspection

After [native setup](native_setup.md), run the following from the repository
root, replacing the path with your own replay:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/inspect_edopro_replay.py \
  /path/to/your/replay.yrpX --native-deck-screen .cache/goat-ai
```

The command reports format, response and packet counts, GOAT startup and
Deck-screen status, and file hashes without printing player names, card IDs,
or response bytes. A passing screen is only a candidate. To try conditional
native response reconstruction, add `--reconstruct-native .cache/goat-ai`.
That path checks every recovered action against the visible legal set and runs
the decision visibility audit. It still reports `training_ready: false` even
when the pinned assets match, because original engine/script provenance and
recording permission must be established separately.

For automated local intake, the strict mode requires the same pinned native
root for Deck screening and reconstruction and returns success only when the
GOAT setup, native Deck checks, and all saved responses match. It saves a
privacy-preserving report alongside the replay, without admitting decisions
to training:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/inspect_edopro_replay.py \
  /path/to/your/replay.yrpX \
  --native-deck-screen .cache/goat-ai \
  --reconstruct-native .cache/goat-ai \
  --require-goat-candidate \
  --report .cache/goat-ai/replay_samples/intake_report.json
```

The report's `native_goat_compatibility_candidate` is true only when all three
checks pass; `training_ready` remains false. Exit status 1 means reconstruction
failed, and status 2 means the strict candidate screen failed after successful
reconstruction. A saved report contains the input path and hashes, so keep it
in ignored local storage with the replay.

If reconstruction fails, the command exits with status 1 and reports a fixed
`reconstruction_failure_code`. For a divergent saved response, it also reports
the zero-based `reconstruction_response_index`. These fields help locate a
compatibility problem without printing card identities or response bytes.
For example, `wrapper_mismatch` means the `.yrpX` wrapper disagrees with its
embedded replay; `unsupported_startup` means its setup is outside the native
GOAT profile; `illegal_saved_response` means the indexed response cannot map
to a legal action on the pinned assets. The codes diagnose local compatibility,
not whether the original replay was a valid historical GOAT duel.

Keep raw replays and generated trajectories in an ignored local directory.
Share the replay file and permission statement directly with a maintainer;
do not open a public issue attaching a replay that contains another player's
private Deck or identifying information.

## Admission gates

Before using a real replay as imitation data, we need all of the following:

1. Explicit permission covering the intended use and both players' private
   information.
2. Successful bounded container parsing and a supported GOAT startup profile.
3. Matching engine and card-script behavior for every saved response, or a
   documented exact compatibility path for the original recording assets.
4. A complete player-visible observation and legal-action set at every
   recovered decision, with hidden-information and exact-replay audits.
5. Reproducible replay and asset hashes, plus a training/evaluation split that
   keeps that game and its Deck composition out of held-out evaluation.

Until these gates pass, an arbitrary external file remains a compatibility
fixture and its decisions are excluded from policy training and strength
claims. The behavioral-clone command rejects raw EDOPro-derived trajectories.
The separate `--experimental-edopro-confirmed` path requires a complete pinned
local room, an exact asset manifest and replay verification, and explicit
human-seat confirmations;
it marks resulting checkpoints historically uncertified and does not establish
the general admission or policy-strength gates.
