# Native benchmark log

The benchmark runs the real pinned ocgcore through `RestrictedOcgcoreEngine` with two normal-monster fixture decks and two seeded `RandomAgent` seats. It measures wall time around reset, action selection, steps, and teardown. It is a narrow protocol baseline, not a measure of general GOAT gameplay or training throughput. Run it with `python scripts/benchmark_native.py --games 3 --seed 42` after [native setup](native_setup.md).

| Date | Platform | Games | Decisions | Elapsed | Duels/s | Decisions/s | Peak process RSS |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-10-24 | Linux 6.8.0-146-generic x86_64 | 3 | 3876 | 2.403 s | 1.248 | 1612.72 | 54,340 KiB |
| 2026-10-24 (GOAT database attached) | Linux 6.8.0-146-generic x86_64 | 3 | 3876 | 2.315 s | 1.296 | 1674.56 | 54,972 KiB |
| 2026-10-24 (observation schema v2) | Linux 6.8.0-146-generic x86_64 | 3 | 3876 | 2.393 s | 1.253 | 1619.47 | 55,772 KiB |

This run used core commit `baa3881d0bae48e9994f915f5c931be53c1ba8ef`, seed start 42, and produced winners `[1, 1, 1]`. Total reset time was 0.135 s; average decisions per duel was 1,292. The bridge shuffled both decks deterministically from the seed before insertion. The process had an 18,156 KiB high-water mark before the timed loop. Memory is read from Linux `/proc/self/status` `VmHWM`; `resource.ru_maxrss` returned an implausible 5,950,868 KiB for an empty interpreter in this environment, so it is not used. These are measurements from one run, without uncertainty estimates. The earlier unshuffled run is excluded because all seeds saw the same opening deck order.

The second row uses the same core and fixture after attaching pinned `goat-entries.cdb` and loading selected GOAT scripts. Its reset time was 0.135 s, initial peak RSS 16,964 KiB, and winners `[1, 1, 1]`. These one-run differences do not establish a speed change.

The third row used project commit `37390528635ffdfa3d2348ba6affa966cc2d21f3`, after adding structured chain links and monster battle position to observations. Total reset time was 0.144 s, initial peak RSS 17,512 KiB, and winners `[1, 1, 1]`. This is one run; the difference from prior rows is not a measured performance regression.

## Parallel tournament measurement

An eight-game random-agent tournament on the same vanilla fixture pairing,
seeds 42–45 with both seat orders, produced the following one-run results on
Linux 6.8.0-146-generic x86_64 with the pinned native core. The timer covers
the tournament call, including worker startup and teardown, but excludes
report hashing and JSON writing.

| Workers | Games | Decisions | Wall time | Duels/s | Decisions/s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 8 | 10,728 | 7.495 s | 1.067 | 1,431.33 |
| 2 | 8 | 10,728 | 3.806 s | 2.102 | 2,818.99 |

Reproduce with the `--workers 1` and `--workers 2` commands in
[the evaluation log](evaluation.md). Game results and summaries matched
exactly. This is one short run, not a scaling estimate; peak memory across
worker processes was not measured. The earlier single-process RSS benchmark
above is not a parallel memory measurement.

## Sourced-deck single-process measurement (2026-10-25)

Commit `90bf1e042e308789243d9c609c4af7c19efa0764` extends `scripts/benchmark_native.py` to accept two decklists and select the experimental native adapter. It reports total reset time, average reset time, and the process's Linux `VmHWM` as well as full-duel throughput. The default restricted vanilla fixture still completed a seed-42 smoke run after this change.

On an Intel Core i7-10700K under Linux 6.8.0-146-generic, one process played ten seeded RandomAgent duels with the sourced Goat Control deck in seat 0 and Chaos Turbo in seat 1, seeds 9700–9709. All ten reached terminal under the 3,000-decision cap. The run took **11.298 seconds** for **10,313 decisions**, or **0.885 duels/s** and **912.9 decisions/s**. Native reset calls took **0.625 seconds total**, **0.0625 seconds per duel** on average. Process peak RSS rose from an initial **21,676 KiB** high-water mark to **64,180 KiB**. The JSON report records deck SHA-256 hashes and winners; it is an ignored local artifact. These are single-run measurements, so the observed rates are not a performance guarantee. RSS is for this one process, not the four-worker tournament.

Reproduce after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/benchmark_native.py --engine experimental --deck-a examples/decks/goat_control_lolmarcus_2020.ydk --deck-b examples/decks/chaos_turbo_riclar_2020.ydk --games 10 --seed 9700 --max-decisions 3000 > artifacts/sourced_goat_chaos_single_process_benchmark_9700_9709.json
```

The benchmark measures Python decisions, native simulation, setup, and teardown together. Historical card correctness remains governed by the separate source-backed regressions.

## Sourced-deck spawned-worker measurement (2026-10-25)

Commit `8f4701adaf8129889f8c751a695ad3443f79f503` adds `scripts/benchmark_parallel_native.py`. On an Intel Core i7-10700K under Linux 6.8.0-146-generic, it ran eight RandomAgent duels between the sourced Goat Control and Chaos Turbo decks, seeds 9700–9703 with both deck seat orders. All eight reached terminal below the 3,000-decision cap. The one-worker and two-worker runs produced the same winner and decision count for every seed and seat, totaling 8,069 decisions. The report contains deck, core, database, whitelist, and global-script hashes; the generated JSON stays in `.cache`.

| Spawned workers | Wall time including spawn | Duels/s | Decisions/s | Mean native reset | Worker peak RSS |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 7.971 s | 1.004 | 1,012.3 | 0.0640 s/duel | 66,016 KiB |
| 2 | 4.422 s | 1.809 | 1,824.9 | 0.0700 s/duel | 66,104 and 63,140 KiB |

For the two-worker run, the **sum of worker high-water marks** was 129,244 KiB; the parent process's high-water mark was 26,048 KiB. These high-water marks may have occurred at different times, so their sum is not a measured instantaneous total memory peak. The corresponding one-worker sum was 66,016 KiB, with a 25,940 KiB parent peak. Native reset time totaled 0.512 s for one worker and 0.560 s for two workers. This is one short sample, not a scaling curve or a guarantee for other deck families.

Reproduce after [native setup](native_setup.md):

```bash
PYTHONPATH=. .venv/bin/python scripts/benchmark_parallel_native.py --games 8 --workers 1 --seed 9700 --output .cache/goat-ai/sourced-single-9700-9703.json > .cache/goat-ai/sourced-single-9700-9703.stdout
PYTHONPATH=. .venv/bin/python scripts/benchmark_parallel_native.py --games 8 --workers 2 --seed 9700 --output .cache/goat-ai/sourced-parallel-9700-9703.json > .cache/goat-ai/sourced-parallel-9700-9703.stdout
```

## Sourced-deck worker scaling pilot (2026-10-26)

At project commit `05260a875a3bf52a92e0dce3a2a541d0032eb014`, the same
Goat Control/Chaos Turbo pairing ran 16 seeded RandomAgent duels, seeds
9800–9807 in both deck seat orders, on an Intel Core i7-10700K under Linux
6.8.0-146-generic. `OMP_NUM_THREADS=1` was set. All four worker counts
produced the same ordered winners and decision counts: 16 terminal duels and
16,860 decisions, each under the 3,000-decision limit. Wall time includes
spawn and teardown. Each row is one run, so the rates are pilot measurements
rather than a scaling guarantee.

| Workers | Wall time | Duels/s | Decisions/s | Mean reset | Sum of worker peak RSS |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 17.547 s | 0.912 | 960.9 | 0.0722 s | 67,716 KiB |
| 2 | 9.301 s | 1.720 | 1,812.6 | 0.0767 s | 134,120 KiB |
| 4 | 5.203 s | 3.075 | 3,240.7 | 0.0814 s | 264,520 KiB |
| 8 | 3.648 s | 4.386 | 4,621.3 | 0.1079 s | 525,504 KiB |

The 8-worker row used all eight workers. The parent process peak was
25,940–26,284 KiB across runs. The worker total sums separate `VmHWM` high
water marks; these peaks need not have occurred at the same time. The runs do
not measure instantaneous machine-wide memory, neural inference, or longer
training workloads. Raw ignored report SHA-256 values for 1/2/4/8 workers are
`8381bce79d6141f331b1dc3396fe95ae2ce5e535704019ec454bc0ee2bba163c`,
`4efe4b3d5d91cd6c4b9aceaf924ad5f5e70b169c5190181bd3b03c9ff8471108`,
`05d1b12cb9c64d8a521b086234603fa2b7ff5be5fd9cd55f1a8364aef3400290`,
and `2e21354ecb7762328bb5177ec1bbada9e1d7d69b40af758809f0cd32132905b4`.

Reproduce with the pinned assets described in [native setup](native_setup.md):

```bash
for workers in 1 2 4 8; do
  PYTHONPATH=. OMP_NUM_THREADS=1 .venv/bin/python scripts/benchmark_parallel_native.py \
    --games 16 --workers "$workers" --seed 9800 \
    --output ".cache/goat-ai/scaling-${workers}-9800-9807.json" \
    > ".cache/goat-ai/scaling-${workers}-9800-9807.stdout"
done
```

## On-policy clone training stages

On 26 October 2026, one epoch over 32 replay-verified policy recordings
(seeds 10400–10407; 2,474 multi-option policy decisions) used PyTorch feature
version 23, width 32, minibatch size 16, one CPU thread, and the same pinned
native assets. The trainer made one backward call per minibatch in all runs.
The third run also enabled padded `--batched-forward`:

| Verification workers | Batched forward | Native verification | Model fitting | Total wall |
| ---: | :---: | ---: | ---: | ---: |
| 1 | No | 22.73 s | 9.41 s | 37.68 s |
| 4 | No | 9.73 s | 9.72 s | 25.57 s |
| 4 | Yes | 9.02 s | 3.33 s | 18.34 s |

Four verification workers alone measured a **1.47× end-to-end speedup**;
adding batched forward measured **2.05×** versus the serial unbatched run.
Fitting itself was **2.92×** faster than four-worker unbatched fitting. The saved
serial and parallel checkpoints had identical metadata and bit-identical
model tensors. A two-replay smoke run was slower with two workers (5.90 s
versus 4.81 s total), so extra workers are useful only when enough replays
amortize process startup. These runs do not measure peak memory or GPU
training. Batched forward uses a different floating-point operation order;
its one-epoch checkpoint had the same greedy choice as the unbatched
checkpoint on **1,292** multi-option player-visible holdout decisions
(seeds 11100–11103), but no duel-strength equivalence is claimed.

Reproduce after [native setup](native_setup.md), using the ignored recordings
from the on-policy teacher experiment described in [evaluation](evaluation.md):

```bash
for workers in 1 4; do
  OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
    scripts/train_behavioral_clone.py \
    .cache/goat-ai/on_policy_teacher_10400_10407/*.json \
    --engine experimental --on-policy-teacher tactical_v14 \
    --feature-version 23 --width 32 --epochs 1 --batch-size 16 \
    --verification-workers "$workers" --learning-rate 0.0001 --seed 48 \
    --init-checkpoint \
      .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
    --output ".cache/goat-ai/profile_on_policy_workers_${workers}.pt"
done
```

For the batched row, repeat the four-worker command with `--batched-forward`
and a distinct output path. The held-out decision comparison used the ignored
`resource_holdout_11100_11103` trajectories; it compared raw model argmax
scores on their recorded visible states, without replaying alternative duels.

## Native location-query cache

On 27 October 2026, a bounded cache keyed by the entire native location-query
response was measured on four random-agent control/Chaos probe duels (seeds
12000–12003, **3,781 decisions**). The pinned native engine returned 37,850
location buffers; only 1,164 distinct buffers were decoded in the cached
schedule. The cache holds at most 4,096 immutable decoded tuples. Its key is
the complete response bytes, so equal-size responses containing different
private cards remain separate.

The matched ablation ran twice in one process, reversing mode order. The
cached and uncached schedules produced **identical complete trajectories** for
all four seeds in both rounds. Four serialized cached trajectories also
replay-verified all 3,781 decisions and passed the legal-choice visibility
audit. Measured CPU times were:

| Order | Uncached | Cached | Speedup |
| :--- | ---: | ---: | ---: |
| Uncached, cached | 4.426 s | 3.709 s | 1.19× |
| Cached, uncached | 4.725 s | 3.477 s | 1.36× |

These results used an Intel Core i7-10700K, Linux 6.8.0 x86_64, and the
experimental native adapter. The mixed-process peak RSS was 956,160 KB;
because both modes ran in the same process, that value does **not** isolate
cache memory overhead. The comparison covers these decks, seeds, and random
choices; it is not a policy-training benchmark or a historical-rules audit.
Deck SHA-256 values were `04352ceadbf53684fe7d6bc4dc18b7e5bed756e01c5914649dda93073dcefc8b`
and `51ca430a9ec9dc3e8b9ce400bcec469d3de39d2152add2a8feb5db814c38a48e`.

A matched policy-rollout check used the v23 checkpoint with SHA-256
`93ca70795e2c5316ab349a4e5c61ebd553915e49abdbe469d0976d3bebe3d9b2`
as the learner against `RandomAgent` on the same deck pair and seeds. Each
four-duel schedule made **4,322 decisions**; complete trajectories matched
between cached and uncached runs. With one Torch thread, uncached versus
cached CPU time was **7.085 vs 6.148 seconds** (1.15×), then **7.036 vs 6.028
seconds** (1.17×) in reverse order. This measures rollout time only; it does
not include optimizer updates or imply a playing-strength gain.

Reproduce after [native setup](native_setup.md):

```bash
PYTHONPATH=src:. .venv/bin/python scripts/benchmark_native_query_cache.py \
  --games 4 --rounds 2
```

After the cache change, the full native-enabled pytest suite passed **985
tests in 958.33 seconds**. The ignored log is
`.cache/goat-ai/native_full_20261027_query_cache.log` (SHA-256
`92cfffddae0a03bdc836f7ed33e50f8ab62835a55540c06a91802d96aacbfdf3`).
The preceding uncached full suite passed 984 tests in 1,139.55 seconds (log
SHA-256 `3b7e8d045628a02ae9ae9896d8410d7e81dc7825c913cb683701553d1266a044`).
The extra test and uncontrolled machine load make those suite times unsuitable
as a cache-speed comparison; the matched duel ablation above isolates that
effect.

## Native field-summary observation queries

The pinned API-11 `OCG_DuelQueryField` response already carries both players'
public field occupancy and zone counts. The adapter now parses that response
first, skips full native location queries for empty zones, and uses its counts
instead of five separate `OCG_DuelQueryCount` calls per observation. The
reference path remains selectable in the benchmark. Both modes produced
**identical complete trajectories** in two order-reversed rounds per deck
pair; all optimized trajectories replay-verified and passed the legal-choice
visibility audit. Timing excludes those verification passes.

On an Intel Core i7-10700K, Linux x86_64, four control/Chaos probe duels
(seeds 12000–12003, 3,781 decisions per schedule) made **37,850** native
location queries on the reference path versus **30,038** on the optimized
path. CPU times were **2.998 vs 2.840 seconds** (1.055×) and **2.854 vs
2.756 seconds** (1.036×). Four sourced Goat Control/Chaos Turbo duels (seeds
12100–12103, 4,487 decisions per schedule) made **44,910** versus **34,256**
location queries. CPU times were **3.191 vs 3.109 seconds** (1.027×) and
**3.104 vs 3.034 seconds** (1.023×). The two reports together contain
**16,536 replay-verified decisions** across their optimized schedules.

The ignored reports are
`.cache/goat-ai/benchmark_native_field_summary_12000_12003.json` (SHA-256
`f7ff85b519bae2306011f7e41668622828e3885d7dcadf64bfe9f416124d4fc6`)
and `.cache/goat-ai/benchmark_native_field_summary_sourced_12100_12103.json`
(SHA-256 `5f9012a867eeb9e70ef25a863107134036db0c5aea0c21eab7cdbbd3ac3b172c`).
Both reports record the benchmark's dirty pre-commit worktree and SHA-256
hashes of the two changed engine files and benchmark script. Those file
hashes identify the tested code independently of the parent commit field.
Reproduce after [native setup](native_setup.md):

```bash
PYTHONPATH=src:. .venv/bin/python scripts/benchmark_native_field_summary.py \
  --games 4 --rounds 2
PYTHONPATH=src:. .venv/bin/python scripts/benchmark_native_field_summary.py \
  --deck-a examples/decks/goat_control_lolmarcus_2020.ydk \
  --deck-b examples/decks/chaos_turbo_riclar_2020.ydk \
  --seed 12100 --games 4 --rounds 2
```

This is a small whole-duel CPU gain under random play. It does not measure
neural inference, optimizer updates, GPU utilization, or competitive strength.

## Batched REINFORCE update

The self-play trainer now accepts opt-in `--reinforce-batch-size 16` for
supported feature versions (v10+, excluding the chain-target v14/v15
variants). Its default of one keeps earlier scalar-update experiments
reproducible. The batched path pads variable-length legal-action sets, masks
padding, and accumulates the same per-decision REINFORCE objective before one
optimizer step. It supports entropy regularization, state baselines, and the
frozen-parent KL term. It does not alter policy sampling or the PPO path.

On 27 October 2026, one replay-verified recording supplied **211**
multi-option, player-visible decisions for one seat. A feature-v23 width-32
checkpoint, Adam at `1e-4`, mean gradient reduction, and one CPU thread gave:

| Order | Scalar update | Batch of 16 | Update speedup |
| :--- | ---: | ---: | ---: |
| Scalar, batched | 0.692 s | 0.183 s | 3.78× |
| Batched, scalar | 0.699 s | 0.188 s | 3.72× |

The loss differed by `1.30e-8`; the largest absolute parameter difference
after the Adam step was `7.98e-6`. These are small numerical differences from
batched floating-point operations, not bit-identical updates. One exploratory
single-duel training comparison produced identical 1,196-decision native
trajectories and measured 1.18×–1.70× CPU speedup across reversed run orders;
that range is too small and variable to generalize to other training schedules.
No playing-strength gain is claimed. The checkpoint SHA-256 was
`93ca70795e2c5316ab349a4e5c61ebd553915e49abdbe469d0976d3bebe3d9b2`;
the recording SHA-256 was
`e5ce07fa2e62f2dcfe6b7613260207a416dc636e291baec26b0a2e0748863fe9`.
A CLI smoke trained one batch-of-16 native duel at seed 14000 on the
control/Chaos probe decks. It reached terminal after 721 decisions, recorded
140 learner choices, saved the batch setting in checkpoint provenance, and
replay-verified and visibility-audited all 721 decisions.

Reproduce the update-only comparison with the ignored recording from the
on-policy teacher collection:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/benchmark_reinforce_update.py \
  .cache/goat-ai/fv23_tactical_v6_current_assets.pt \
  .cache/goat-ai/on_policy_teacher_10400_10407/jesse_warrior_10400_seat0.json \
  --seat 0 --batch-size 16 --rounds 2
```

The native CLI smoke used:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v6_current_assets.pt \
  --output .cache/goat-ai/batched_reinforce_smoke_child.pt \
  --native-root .cache/goat-ai --engine experimental \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk \
  --games 1 --seed 14000 --historical-probability 0 \
  --learning-rate 0.00001 --policy-gradient-reduction mean \
  --reinforce-batch-size 16 \
  --record-dir .cache/goat-ai/batched_reinforce_smoke_records
```

After merging the opt-in trainer path, the Python suite passed 294 tests
(694 native-gated skips), and the focused policy/native-query suite passed 95
tests with native assets. The 985-test full native run above preceded this
trainer commit; the native CLI smoke and focused tests exercise its new path.

## Native replay-manifest hash cache

On 27 October 2026, profiling one 846-decision feature-v23 policy duel showed
about 0.20 seconds in `replay_manifest()` hashing the same native library and
databases at duel completion. The library alone is about 90 MiB. The adapter
now reuses each required asset's SHA-256 while its resolved path, device,
inode, size, modification time, and change time match. Loaded scripts retain
their per-duel hashes. Deck files and trajectories still use direct content
hashing. Replacing a file invalidates the cache through its inode even when
the replacement has the same size and modification time. An in-place edit
usually changes modification or change time, but a same-inode rewrite that
restores all observed timestamps cannot be detected from metadata. Pinned
native assets must therefore stay immutable during one Python process; use a
fresh process after regenerating them.

Four complete policy-versus-random native duels (seeds 13000–13003,
control/Chaos probe decks, 3,816 total decisions) were run with direct and
cached hashing on an Intel Core i7-10700K, one PyTorch CPU thread. Two rounds
reversed run order. All corresponding complete trajectories, including asset
hashes, were equal.

| Order | Direct hashes | Cached hashes | Whole-duel speedup |
| :--- | ---: | ---: | ---: |
| Direct, cached | 4.161 s | 3.650 s | 1.14× |
| Cached, direct | 4.214 s | 3.470 s | 1.21× |

This measures short, single-process policy rollouts with repeated pinned
assets; it does not measure a parallel training run or competitive strength.
The checkpoint SHA-256 was
`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`.
The deck SHA-256 values were
`04352ceadbf53684fe7d6bc4dc18b7e5bed756e01c5914649dda93073dcefc8b`
and `51ca430a9ec9dc3e8b9ce400bcec469d3de39d2152add2a8feb5db814c38a48e`.
The comparison used Linux 6.8, PyTorch 2.5.1+cpu, and commit `c0980cf` plus
this cache change. Reproduce it with:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/benchmark_native_manifest_cache.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --games 4 --rounds 2
```

The targeted fingerprint/native environment test run passed 5 tests. The
Python suite passed 295 tests with 694 native-gated skips. The full native
suite has not been rerun after this change.

## Native script-path dispatch

On 27 October 2026, a 30-reset profile of the experimental adapter found
repeated `Path.relative_to()` calls in every native script load. The loader
now computes that relative name once per script and uses it for the historical
patch checks and loaded-script manifest. The SHA-guarded patch contents are
unchanged.

An AB/BA comparison used four complete RandomAgent duels per run, seeds
15000–15003, control/Chaos probe decks, and one CPU thread on an Intel
Core i7-10700K. The prior adapter source was commit `a4c12e9` (probe SHA-256
`b834c4abbf496bc0c158f9d42e91f212a51262749162fc2295b2cfe0d75ab3bc`);
the changed probe SHA-256 was
`5b4c80de9b4d1e834bab263537dfa20f631db7bb8e4f36bbfdf50f5016cce1c6`.
Every run completed the same **4,230 decisions** with identical per-game
counts and winners.

| Order | Prior total / reset | Changed total / reset |
| :--- | ---: | ---: |
| Prior, changed | 2.879 / 0.334 s | 2.820 / 0.219 s |
| Changed, prior | 2.871 / 0.317 s | 2.769 / 0.217 s |

The four-game reset subtotal improved **1.45–1.53×**; total duel wall time
improved **1.02–1.04×** in these two runs. A complete 985-decision replay
recorded under each source was byte-identical (9,678,584 bytes), and the
changed-source replay passed native verification and the visibility audit.
These are measured startup and complete-duel results for one deck pairing,
not a measured self-play training gain. The ignored AB/BA report is
`.cache/goat-ai/script_path_abba_15000.json` (SHA-256
`e50260cc379cc56e1146d54387bda5211bbbc8a50a3bf98cf4d66c03724f5948`).
The changed replay is `.cache/goat-ai/script_path_new_15000.json` (SHA-256
`6b8b7d681f1a72db14fc8fa5d9ad4be802691965f4b44838b5f7488e07e69e84`).
The related native script regressions passed **16 tests**.

For a source-level comparison, check out `a4c12e9` in a separate worktree
and run `scripts/benchmark_native.py` under each source tree with the same
`--engine experimental --deck-a examples/decks/control_probe.ydk`
`--deck-b examples/decks/chaos_probe.ydk --seed 15000 --games 4` arguments.
The benchmark now reports per-game decision counts and the loaded probe
source hash as well as total timing.

## Pending prompt decoding and policy evaluation mode

On 27 October 2026, a one-duel CPU profile of the experimental native adapter
showed 3,333 pending-prompt decodes across 1,111 decisions. The adapter now
reuses a decoded prompt while the same native response window is pending.
PolicyAgent also skips its recursive PyTorch `eval()` call when the model is
already in evaluation mode. Both changes preserve the decoded choices and
model outputs; a new native prompt gets a new decode.

The reproducible prompt-cache AB/BA command is:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/benchmark_pending_decode.py \
  --native-root .cache/goat-ai --seed 15000 --games 4
```

The command forces a fresh decode for the reference arm. On an Intel Core
i7-10700K, the four control/Chaos probe duels completed 4,230 decisions in
each arm. Complete trajectories matched. The fresh/cached wall times were
2.997/2.872 seconds in the first round and 2.908/2.938 seconds in the
reversed round, giving **1.043× and 0.990×** ratios. The measured effect is
small relative to run variation; this is a CPU overhead reduction, not a
demonstrated self-play throughput or playing-strength gain. The ignored raw
report is `.cache/goat-ai/pending_decode_benchmark_15000.json`.

A separate four-game greedy-policy comparison forced the former recursive
`eval()` behavior at every decision. Changed and reference trajectories
matched; old/new wall-time ratios were 1.087× and 1.011× in reversed-order
rounds. The comparison did not include a training update. A four-game sampled
self-play comparison of 1 versus 8 PyTorch CPU threads produced 3.259 versus
3.323 seconds in one order and 3.354 versus 3.206 seconds in the other;
trajectories matched and neither thread count won consistently. The training
CLI keeps its current thread setting.

## Staged-selection observation reuse

On 27 October 2026, the native adapter began reusing the same player-visible
observation while a multi-card selection is only staged in Python. It rebuilds
the observation after the selected cards are submitted to ocgcore. The focused
Graceful Charity and Thunder Dragon native regressions passed, including exact
replay and visibility verification.

The comparison forces staged Graceful Charity selection and runs one complete
1,197-decision duel per arm in six AB/BA rounds:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/benchmark_staged_observation.py --rounds 6
```

Both arms produced identical complete trajectories. The reused arm made
1,197 observation builds versus 1,198 in the reference arm in every round.
The wall-time reference/reused ratios were 1.349, 1.030, 0.981, 1.030, 0.955,
and 0.970; the median was **1.006×**. The first round includes warm-up effects.
This saves an exact redundant query but shows no reliable whole-duel speedup
for this fixture. It is not a training-throughput result. The ignored raw
report is `.cache/goat-ai/staged_observation_benchmark_18.json`. This run used
an Intel Core i7-10700K on Linux 6.8.0 with native core SHA-256
`b2ce880275e07ae2cd5e6f8735e61e651dedaa6b752de471e6c0cf9d66db00eb`.
