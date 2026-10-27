# Contributing GOAT replay data

A real, authorized GOAT EDOPro replay is the next data-pipeline fixture. The
project currently parses `.yrp` and `.yrpX` containers and reconstructs
synthetic GOAT response traces against pinned native assets. It has **not**
validated a real GOAT recording end to end, and no EDOPro replay is accepted
as a training demonstration yet.

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

Until these gates pass, the file remains a compatibility fixture and its
decisions are excluded from policy training and strength claims.
The behavioral-clone command rejects EDOPro-derived sources even when native
response reconstruction succeeds; a future admission path must verify the
recording's original engine and script provenance and its permissions first.
