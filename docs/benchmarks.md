# Native benchmark log

## Preallocated PPO feature padding (27 October 2026)

The policy's batched forward pass used to call `torch.nn.functional.pad` for
every feature tensor in every decision, then stack the padded tensors. It now
allocates one zero-filled tensor per feature field and copies each decision
into its slice. Padding values and the legal-action mask are unchanged.

An AB/BA complete-training comparison used the feature-v23 reference
checkpoint, Jesse Goat Control versus Warrior, seeds 28000–28015, four
rollout workers, two PPO epochs, minibatch 32, and one Torch CPU thread per
process on an Intel Core i7-10700K. The unmodified arm ran from detached
commit `9a3e21d`; the changed arm ran from this patch. Each arm finished 16
terminal duels with 1,119 learner decisions. The 16 replay files were
byte-for-byte equal and all saved model tensors were exactly equal in every arm.

| Run order | Original trainer | Preallocated padding |
| :--- | ---: | ---: |
| Original, changed | 6.861 s | 6.643 s |
| Changed, original | 6.668 s | 6.496 s |

This was a **2.6–3.2% complete-training saving** on this one schedule. One
changed replay independently verified all 356 native decisions; the focused
policy suite passed 104 tests. The small gain does not establish a speedup on
other models, hardware, or deck pairings. Ignored reports and replays use
`.cache/goat-ai/pad_bench_{control,new,control_b,new_b}_28000` prefixes.

## Empty-chain GRU skip pilot (27 October 2026)

An experimental CPU inference branch skipped the chain GRU when the encoded
chain was the single all-zero sentinel row. It kept the ordinary GRU path
during gradient-enabled fitting and TorchScript tracing. In eight recorded
Jesse Goat Control versus Warrior duels, 167 of 1,644 multi-option decisions
had a nonempty chain, so this looked like a frequent opportunity. A focused
test found equal logits between the skipped inference path and the ordinary
gradient-enabled GRU path, including a later nonempty chain through the
traced scorer.

On seeds 26000–26007, the unchanged feature-v23 parent, one Torch CPU thread,
two four-duel PPO rollouts, two update epochs, and batch size 16, the ordinary
trainer reported **7.202 seconds** in its last measured arm. Two experimental
arms reported **7.229 and 7.284 seconds**. All three wrote byte-identical
replays across **4,848 decisions** and equal final policy tensors. Those same
replay bytes in a matched ordinary-GRU arm passed native verification and the
player-visibility audit. The experiment did not show a complete-training
speed gain, so the branch was reverted. Its ignored reports and outputs have the
`reuse_bench_off_b_26000` and `empty_chain_fast_{a,b}_26000` prefixes under
`.cache/goat-ai/`. These measurements do not support changing the policy
inference path.

## Cached viewer-specific card projections (27 October 2026)

Observation construction previously rebuilt every immutable `CardView` from
the same decoded native card record at every decision. The engine now caches
this pure projection by **viewer, controller, location, sequence, and complete
queried card**. The cache is bounded to 8,192 entries, includes the viewer in
its key, and does not change the player-visible observation contract. It does
not skip native queries or hide new card, position, stat, or counter changes.

A complete-training AB/BA comparison used the feature-v23 parent checkpoint
`fv23_tactical_v14_unseen_fourdeck_continuation.pt` (SHA-256
`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`),
Jesse Goat Control versus Warrior, seeds 23500–23503, one Torch CPU thread,
four-game PPO rollouts, two epochs, and batch size 16. Both modes played the
same **2,060 decisions** in every arm. All four replay files were byte-identical
between modes in each order, and all **38 model tensors** were exactly equal.
The cached arm's four replays passed exact native verification and the
player-visibility audit. The cache had 73,998 hits and 688 misses per arm.

| Run order | Uncached complete training | Cached complete training | Ratio |
| :--- | ---: | ---: | ---: |
| Uncached, cached | 3.781 s | 2.756 s | 1.37× |
| Cached, uncached | 2.967 s | 2.728 s | 1.09× |

The arms ran in one process, so startup and warm-cache effects can differ by
order. The reversed order supports a smaller local gain; these timings do not
establish performance across other decks, hardware, or long training runs.
Memory overhead was not isolated because both modes shared one process. The
ignored comparison and replay audit are under `.cache/goat-ai/` with
`card_view_*_23500` prefixes. The reference arm assigns
`ocgcore_probe._view_card = ocgcore_probe._view_card.__wrapped__` before running
the same trainer arguments; the cached arm uses the decorated function.

Two further eight-duel comparisons used separate Python processes and the
same parent, decks, PPO settings, and one Torch thread. Both arms in the
second row used the same launcher and differed only in whether it assigned
the undecorated reference function before loading the trainer. All **16
cached trajectories** replay-verified and passed the visibility audit. Within
each seed group, cached and reference trajectories were byte-identical and
all 38 checkpoint tensors were exactly equal.

| Seeds; run order | Decisions | Reference trainer time | Cached trainer time | Reference peak RSS | Cached peak RSS |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 23600–23607; cached, reference | 4,910 | 8.132 s | 7.540 s | 352,952 KiB | 338,640 KiB |
| 23610–23617; reference, cached | 4,062 | 7.008 s | 6.584 s | 347,972 KiB | 337,924 KiB |

The 6–7% trainer-time saving is observed for these two schedules, not a
general throughput estimate. `/usr/bin/time` measured separate whole-process
wall times of 9.54/8.88 seconds and 8.39/7.92 seconds
(reference/cached). Peak RSS was lower for the cached process in both runs,
but two samples cannot isolate cache memory cost from allocator and process
variation. Raw reports, time files, and the 16-replay audit are ignored under
`.cache/goat-ai/` with `card_view_*_23600` and `card_view_*_23610` prefixes.

The pure projection has a unit regression that changes viewer, zone sequence,
position, and attack while checking both redaction and cache separation. The
native observation, environment, and visibility test group passed **23 tests**.

## Four-duel PPO training profile (27 October 2026)

One complete feature-v23 PPO rollout was profiled to choose a measured next
speed experiment. The parent checkpoint was
`fv23_tactical_v14_unseen_fourdeck_continuation.pt` (SHA-256
`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`).
On an Intel Core i7-10700K, one Torch CPU thread, Jesse Goat Control versus
Warrior, seeds 23400–23403, four terminal duels produced **2,126 total
decisions** and **417 learner decisions**. Two PPO epochs used minibatches of
16. Every recorded duel replay-verified on the pinned native assets and passed
the player-visibility audit.

The `cProfile` run reported 5.570 seconds inside the trainer, while one
unprofiled run on identical seeds and settings reported 3.946 seconds. Each
duel had the same decision count in both runs; all four trajectory files were
byte-identical and all 38 model tensors were exactly equal. The 1.624-second
timing difference is profiling overhead plus ordinary run variation, **not**
an optimization gain. The profile's cumulative Python times overlap callers:

| Repeated function | Calls | Profile cumulative time |
| :--- | ---: | ---: |
| Native observation construction | 2,130 | 1.040 s |
| Policy forward (internal) | 605 | 0.848 s |
| Visible decision encoding | 941 | 0.658 s |
| Native response processing | 2,126 | 0.450 s |
| Replay JSON writing | 4 | 0.055 s |

Observation construction is the next candidate for a matched optimization
experiment because it runs at nearly every native decision. The profile does
not justify removing observations, weakening hidden-information redaction, or
assuming these cumulative times translate directly into whole-run savings.
PyTorch imports also appeared prominently in this short-process profile, so
future comparisons should use longer runs and report complete wall time.
The ignored profile, checkpoints, reports, trajectories, and replay audit use
the `ppo_profile_23400` and `ppo_reference_23400` prefixes under
`.cache/goat-ai/`. Reproduce the profiled arm with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python -m cProfile \
  -o .cache/goat-ai/ppo_profile_23400.prof scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/ppo_profile_23400.pt --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --seed 23400 --games 4 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 \
  --ppo-epochs 2 --ppo-batch-size 16 --snapshot-every 4
```

### Longer single-process PPO profile

A follow-up used the same feature-v23 parent, sourced Goat Control/Warrior
matchup, one Torch CPU thread, four-game PPO rollouts, two epochs, and
batch size 16 on an Intel Core i7-10700K. Seeds 23700–23715 produced 16
terminal duels, **8,151 total decisions**, and **1,740 learner decisions**.
The profiled run reported 18.557 seconds of trainer time; the otherwise
identical unprofiled run reported 13.026 seconds. Profiling overhead and
ordinary timing variation are included in that difference.

All 16 replay JSON files were byte-identical between runs, and all 38 policy
tensors were exactly equal. Native replay verification checked all 8,151
decisions in the profiled arm, and the player-visibility audit passed.

| Repeated function | Calls | Profile cumulative time |
| :--- | ---: | ---: |
| Policy forward (internal) | 3,204 | 4.320 s |
| Native observation construction | 8,167 | 3.221 s |
| Visible decision encoding | 4,611 | 2.634 s |
| Native response processing | 8,151 | 1.623 s |
| Native location query, included in observation time | 57,080 | 1.092 s |

The cumulative times overlap callers and cannot be added to estimate a total.
This longer sample changes the next experiment's priority: reduce the many
small PyTorch operations in policy inference or avoid redundant inference
work, then measure **complete training time** against the unchanged rollout
and model tensors. The existing four-worker rollout measurement remains a
better tested CPU setting than single-process batched inference. This profile
alone establishes no speedup and no playing-strength change. It covers one
deck pairing and the single-process rollout path.

The ignored artifacts are `.cache/goat-ai/ppo_profile_23700_16.prof`,
`ppo_profile_23700_16.pt`, `ppo_reference_23700_16.pt`, their replay folders,
and `ppo_reference_23700_16_report.json`. To reproduce the profiled arm, use
the command above with seed 23700, 16 games, and fresh output and profile
paths; run the same command without `-m cProfile -o <profile>` for the
reference arm.

### Four versus eight PPO rollout workers

A separate scaling check used 16 games per schedule, eight-game PPO rollouts,
two epochs, batch size 16, and the same sourced Goat Control/Warrior pairing.
Both worker counts used independent native processes and one Torch CPU thread
per process on the same i7-10700K. Run order was reversed between seed groups.

| Seeds; order | Decisions | Four workers | Eight workers |
| :--- | ---: | ---: | ---: |
| 23800–23815; four then eight | 7,557 | 7.706 s | 7.396 s |
| 23820–23835; eight then four | 7,327 | 7.774 s | 7.695 s |

Within each seed group, all 16 replay files and all 38 policy tensors were
exactly equal between worker counts. The first eight-worker group's 7,557
decisions replay-verified against the pinned native engine and passed the
visibility audit. Eight workers saved about 1–4% of the reported trainer time
in these two short runs; worker memory and larger schedules were not measured.
This is too small a local gain to establish eight workers as the default.
The ignored reports, checkpoints, and replay folders have `worker4_23800_16`,
`worker8_23800_16`, `worker4_23820_16`, and `worker8_23820_16` prefixes.

### Reused TorchScript trace for frozen PPO rollout inference

An opt-in `--trace-rollout-inference` path traces the feature-v23 learner
scorer on its first visible decision and reuses that trace for every duel in
the same frozen, single-process multi-duel PPO rollout. The policy update
still uses the ordinary eager model and original feature tensors. A fresh
trace is made after the next policy update. It is currently restricted to
feature version 23, clipped PPO with at least two games per rollout, and no
process workers or batched rollout inference.

On 400 varied multi-option decisions from recorded sourced-deck duels, traced
and eager scorers returned exactly equal logits. Two warm CPU passes took
0.349/0.349 seconds eager and 0.151/0.150 seconds traced; this excludes
feature encoding, trace construction, simulator work, and updates. Tracing
once **per duel** made complete 16-duel training slower (13.815 versus
13.115 seconds eager), so the retained path reuses one trace per frozen PPO
rollout.

The complete-training comparisons below used the feature-v23 parent, sourced
Goat Control/Warrior decks, one Torch CPU thread, four-game PPO rollouts, two
epochs, batch size 16, and an Intel Core i7-10700K. Run order was reversed
between seed groups.

| Seeds; order | Total / learner decisions | Eager trainer time | Reused trace trainer time |
| :--- | ---: | ---: | ---: |
| 23900–23915; eager then trace | 9,080 / 1,633 | 13.115 s | 12.566 s |
| 23920–23935; trace then eager | 7,179 / 1,351 | 11.018 s | 10.392 s |

Within each group, all 16 replay files were byte-identical and all 38 model
tensors were exactly equal. The traced second group's 7,179 decisions passed
native replay verification and the player-visibility audit. The observed
complete-training saving was about 4–6% on these two schedules. This does not
establish a gain for other policy versions, worker counts, hardware, or
playing strength; the faster four-worker CPU rollout setting remains a
separate option. PyTorch's GRU emits shape-check tracer warnings, so this
path remains opt-in and has an additional two-duel native equality test.

The ignored reports, checkpoints, and replay folders have `trace_ref_23900_16`,
`trace_reuse_23900_16`, `trace_ref_23920_16`, and `trace_reuse_23920_16`
prefixes. Reproduce one arm with the documented 16-game PPO profile command,
seed 23900 or 23920, a fresh output path, and `--trace-rollout-inference`
for the traced arm; omit that flag for the eager arm.

## Reusing visible PPO features from rollout (27 October 2026)

The opt-in `--reuse-rollout-features` path retains the learner's already
encoded, player-visible decision tensors until its single-process PPO update.
It skips a second encoding pass over the same decisions. It is unavailable
with process rollout workers, which would have to send these tensors between
processes. The default training path remains unchanged.

An AB/BA complete-training comparison used the feature-v23 checkpoint
`fv23_tactical_v14_unseen_fourdeck_continuation.pt`, Jesse Goat Control versus
Warrior, seeds 23000–23003, four terminal games per PPO rollout, two epochs,
batch size 16, and one Torch CPU thread. Every arm played **2,650 decisions**,
including **487 multi-option learner decisions**. The four corresponding replay
files were byte-identical across arms; all **38 policy tensors** were exactly
equal. The cached arm's four trajectories replay-verified against the pinned
native engine and passed the player-visibility audit.

| Run order | Re-encode update | Reuse rollout features |
| :--- | ---: | ---: |
| Reference, reuse | 4.704 s | 4.610 s |
| Reuse, reference | 4.720 s | 4.606 s |

One additional matched `/usr/bin/time` run reported peak process RSS of
**341,844 KiB** for the reference and **345,448 KiB** for reuse, an observed
3,604 KiB increase. The comparison is short and on one CPU/deck schedule;
the roughly 2% wall-time gain is not a large-scale throughput or strength
claim. Raw outputs are ignored under `.cache/goat-ai/reuse_features_23000/`.
A separate four-game smoke with `--rollout-batch-inference` completed 3,857
decisions in both modes, kept replay bytes and all policy tensors equal, and
reported 5.940 versus 5.773 seconds (reference versus reuse). This checks
compatibility with that opt-in rollout mode, not its overall value against
process workers.
Reproduce an arm after [native setup](native_setup.md), using a fresh output
name and adding `--reuse-rollout-features` for the cached arm:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --seed 23000 --games 4 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 \
  --ppo-epochs 2 --ppo-batch-size 16 --snapshot-every 4 \
  --output .cache/goat-ai/reuse_features_example.pt
```

## Reused opponent statistics in policy encoding (27 October 2026)

Feature-v23 encoding now computes visible opposing monster statistics once per
decision, rather than once for every legal action, and looks up action-kind
indices through a local map. It does not alter the observation or action
contract. On 615 multi-action decisions from the seed-18200 recorded replay,
the baseline and candidate produced the same combined feature SHA-256
`b6dfed5b4f8da6dab29d0f26ccd5bfd50d6c580caf9476f0b03d9a63c228b83e`.
Eight encoding passes per arm, excluding the first warm-up pass, measured
median times of **166.984/164.990 ms** and **168.316/162.489 ms** in
baseline/candidate and candidate/baseline order respectively.

A complete one-duel REINFORCE comparison used the same feature-v23 checkpoint,
control/Chaos probe decks, seed 18240, one Torch CPU thread, and update batch
size 16. The candidate/baseline and baseline/candidate training times reported
by the CLI were **2.251/2.286 s** and **2.232/2.273 s**. Every run completed
1,178 decisions, wrote byte-identical trajectory JSON (SHA-256
`d2073f4c5e955cfb9379b124f7cb9a42dd1687f1f34872a2f033306b307ef4c7`),
and produced identical model tensors. The candidate replay passed full native
verification and the visibility audit. This is a small measured improvement on
one seed and CPU, with no evidence of improved playing strength. Ignored logs,
checkpoints, and replays have the `encode_{baseline,candidate}_{a,b}_18240`
prefix under `.cache/goat-ai/`. Reproduce a training arm against the matching
source revision with a fresh output path:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v6_current_assets.pt \
  --output .cache/goat-ai/encode_example_18240.pt --engine experimental \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk \
  --seed 18240 --games 1 --max-decisions 3000 --reinforce-batch-size 16
```

## Fixed zone and position lookup in policy encoding (27 October 2026)

Policy feature encoding now looks up the seven fixed zones and three fixed
positions through prebuilt integer maps. A recorded feature-v23 replay from
seed 18200 supplied 615 multi-action decisions. Six passes over those
decisions gave a median warm encoding time of **171.3 ms** with tuple searches
and **166.8 ms** with maps. The combined feature-tensor SHA-256 was identical
in both modes:
`b6dfed5b4f8da6dab29d0f26ccd5bfd50d6c580caf9476f0b03d9a63c228b83e`.

A complete native AB/BA comparison used the same feature-v23 checkpoint,
control/Chaos probe decks, seeds 18210–18213, a frozen random opponent,
one Torch CPU thread, and a 3,000-decision cap. Each mode completed
**4,956 decisions** and produced exactly equal trajectories and learner
records. Linear/mapped wall times were **5.119/5.032 s** and
**4.913/4.871 s** in reversed order. This is a small gain on one CPU and
deck pair; it does not establish a broader training speedup or any strength
change. The ignored measurements are
`.cache/goat-ai/zone_lookup_baseline_18200.json`,
`.cache/goat-ai/zone_lookup_candidate_18200.json`, and
`.cache/goat-ai/zone_lookup_full_18210.json`.

## Torch CPU thread count in a complete self-play game (27 October 2026)

The trainer does not override PyTorch's CPU thread count. On this host its
default was eight. A matched AB/BA test compared `OMP_NUM_THREADS=8` and
`OMP_NUM_THREADS=1` using the feature-v23
`fv23_tactical_v6_current_assets.pt` checkpoint, the control/Chaos probe
decks, seed 18200, experimental native engine, one REINFORCE game, and update
batch size 16. Each arm completed 1,527 decisions, recorded the same replay
bytes (SHA-256 `f040020863571a0b54a0989cdbd55e8d7091da77bdbb2e0c7f6c7152213d93fe`),
and reported the same policy loss. The one-thread replay verified against all
1,527 native decisions. Whole-process times in run order were **4.454 s**
(eight), **4.452 s** (one), **4.400 s** (one), and **4.363 s** (eight).
The trainer's own reported times were 3.111, 3.104, 3.065, and 3.022 s.
These tiny differences do not support changing the thread default.

Saved weights were bit-identical between runs with the same thread count.
Across thread counts, seven tensors differed by at most `3.24e-6`, despite
identical sampled decisions. Pin the thread count when exact checkpoint
reproduction matters. The ignored raw report and outputs are under
`.cache/goat-ai/thread_benchmark_18200/`. To reproduce an arm, use a fresh
output path and change `OMP_NUM_THREADS` between one and eight:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v6_current_assets.pt \
  --output .cache/goat-ai/thread_example_18200.pt --engine experimental \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk \
  --seed 18200 --games 1 --max-decisions 3000 --reinforce-batch-size 16
```

A separate `cProfile` sample with the automatic fast replay writer used
seed 18201 and 1,215 native decisions. It attributed cumulative Python time
of 0.742 s to observation construction, 0.553 s to 714 policy feature
encodings, and 0.505 s to 380 policy forward calls. These cumulative times
overlap their callers and include profiling overhead. They identify the next
places to test with complete matched duels: reduce redundant observation
work, then consider reuse of already encoded learner decisions during policy
updates. Preserve player-visible observations and byte-identical trajectories
as correctness gates. The ignored profile is
`.cache/goat-ai/train_profile_fast_18201.prof`.

## Cached frozen-parent scores for PPO (27 October 2026)

With `--parent-kl-weight`, clipped PPO previously re-ran the unchanged
parent model for every shuffled minibatch in every epoch. It now scores each
record once, before the update, and reuses those player-visible probabilities.
The cache stores two float vectors per recorded legal-action set; its memory
use grows with the total number of legal actions in the update. A focused test
confirms that five records in three epochs cause three parent batch calls at
batch size two, rather than nine.

A single matched native training game used the feature-v23 checkpoint SHA-256
`93ca70795e2c5316ab349a4e5c61ebd553915e49abdbe469d0976d3bebe3d9b2`,
control/Chaos probe decks, seed 18101, three PPO epochs, batch size 16,
parent KL weight 0.1, and one Torch CPU thread. Complete reported training
time was **8.203 s before** and **7.586 s after** (1.081× in this one pair).
Both arms recorded 2,384 decisions, including 965 learner decisions, in
byte-identical trajectories (SHA-256
`818e97d173fa41ffcc527ffd6b2772f7e7f05780ee4a779a43a5def717d6883a`).
The updated trajectory replay-verified all 2,384 decisions and passed the
visibility audit. The reported PPO loss was identical. Changed minibatch
grouping for frozen-parent inference gives slightly different floating-point
weights: all 965 recorded learner decisions retained the same top action,
and the maximum logit difference was 0.000727. This is a one-game CPU timing,
not evidence of a strength gain or a reliable scaling factor.

Reproduce each arm at its corresponding source revision with a fresh output
name:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v6_current_assets.pt \
  --output .cache/goat-ai/ppo_parent_kl_MODE_18101.pt \
  --engine experimental \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk \
  --seed 18101 --games 1 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-epochs 3 --ppo-batch-size 16 \
  --parent-kl-weight 0.1
```

The pre-cache arm used commit `b8acffb`; the cached arm uses the current
revision. Both ignored output logs and checkpoints are under `.cache/goat-ai/`
with `ppo_parent_kl_before_18101` and `ppo_parent_kl_after_18101` prefixes.

## Single-process batched PPO inference (27 October 2026)

The optional `--rollout-batch-inference` path advances independent native
duels in one process and batches only learner policy calls at decision
boundaries. Each duel retains its own engine, player-visible observation, and
sampling generator. It requires multi-duel clipped PPO and the policy versions
supported by `forward_batch`; process workers, censored games, and a learned
critic are excluded from this experimental path.

An end-to-end eight-duel run used the feature-v23 parent checkpoint SHA-256
`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`,
control/Chaos probe decks, seeds 16630–16637, a frozen random opponent,
one PPO epoch, rollout size eight, batch size 16, and one Torch CPU thread.
It ran on an Intel Core i7-10700K under Linux 6.8.0-146-generic. Each mode
completed the same 5,865 decisions and 1,092 learner decisions. All eight
replays had byte-identical counterparts across modes, and the resulting
policy tensors were equal. The batched replays passed complete native
verification and the player-visibility audit.

| Rollout mode | Complete training wall time |
| :--- | ---: |
| One independent worker | 8.710 s |
| Batched inference in one process | 8.322 s |
| Four independent process workers | 6.897 s |

The four-duel smoke on seeds 16620–16623 took 4.318 s with one worker and
4.265 s with batched inference; its replays and trained tensors also matched.
These small measurements show a modest CPU gain over a single worker and a
slower run than four process workers. Batch inference remains opt-in. No
competitive strength gain follows from byte-identical training data.

To reproduce one arm from the repository root, run the command below with a
fresh output name and append either `--rollout-workers 1`,
`--rollout-workers 4`, or `--rollout-batch-inference`:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/rollout_MODE_16630.pt \
  --engine experimental \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk \
  --seed 16630 --games 8 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 8 \
  --ppo-epochs 1 --ppo-batch-size 16 \
  --historical-probability 0 --snapshot-every 8
```

The ignored stdout reports and checkpoints have matching names under
`.cache/goat-ai/`: `batch_inference_16630`, `worker1_16630`, and
`workers4_16630`.

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

## Complete one-duel REINFORCE training: scalar versus batch 16

On 27 October 2026, the existing opt-in batch update was measured through the
complete `train_self_play.py` command, including native rollout, replay writing,
update, and checkpoint save. The fv23 checkpoint
`93ca70795e2c5316ab349a4e5c61ebd553915e49abdbe469d0976d3bebe3d9b2`
played the control/Chaos probe decks, seed 16000, with one Torch CPU thread on
an Intel Core i7-10700K. Run each command from the repository root, changing
`MODE` and `BATCH` to `scalar`/`1` or `batch16`/`16`:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v6_current_assets.pt \
  --output .cache/goat-ai/speed_MODE_16000.pt \
  --record-dir .cache/goat-ai/speed_MODE_16000_replays \
  --engine experimental \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk \
  --seed 16000 --games 1 --max-decisions 3000 --reinforce-batch-size BATCH
```

AB/BA training wall times were **2.520/2.111 s** and **2.466/2.076 s** for
scalar/batch 16, respectively: **1.19× and 1.19×** speedups. All four runs
played the same 924 decisions (158 learner decisions), winner seat 0, and
wrote byte-identical trajectories (SHA-256
`b8e09b8272b77d8be913c28eb4037df0b1419468c7be2041eae47780192f7dc7`).
The batched trajectory passed exact native verification and the visibility
audit. Policy losses differed only at floating-point precision (0.5590956630
versus 0.5590956422). These are one-duel training measurements, not a
multi-game throughput or competitive-strength result. Keep batch size 1 as
the reproducibility default; use `--reinforce-batch-size 16` for opt-in CPU
experiments and evaluate resulting checkpoints separately.

## Cached race-mask encoding

On 27 October 2026, the opt-in policy feature versions 20–25 repeatedly
expanded the same public announced race mask into 64 float bits for every
legal action. A bounded 256-entry cache now reuses the exact tuple for each
race value. The cache stores only the integer action parameter and its pure
encoding; it contains no duel state or hidden card information.

On 182 multi-action decisions (799 legal actions) from a recorded v25
Dimension Fusion/Phoenix duel, eight encoder passes took a median **59.3 ms**
without the cache and **49.4 ms** with it, excluding the first pass. Every
encoded tensor matched byte for byte (combined SHA-256
`894436ae77c3cd5115e6e71af081a28f4f0fda7ff75ec38aa8e221292f575610`).
These measurements isolate feature encoding; they are not full training times.
Ignored measurement reports are `.cache/goat-ai/encode_race_baseline_17008.json`
and `.cache/goat-ai/encode_race_cached_17008.json`.

The matched complete-duel check is reproducible from the repository root:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/benchmark_race_feature_cache.py \
  .cache/goat-ai/fv25_resource_trade_head_10400_10407.pt \
  --output .cache/goat-ai/race_cache_complete_script_17100_17103.json
```

Four seeded control/Chaos probe duels completed **2,723 decisions** in each
arm. Both AB/BA rounds had identical full trajectories and learner records.
Uncached/cached wall times were **2.539/2.390 s** and **2.366/2.320 s**,
respectively. The second round's difference is small relative to timing
variation; this confirms correctness and a modest local CPU saving, not a
reliable estimate of large-scale self-play speedup. The ignored raw report is
`.cache/goat-ai/race_cache_complete_script_17100_17103.json`.

## Optional fast trajectory JSON in self-play

On 27 October 2026, `cProfile` of one seeded native training game identified
replay JSON writing as a material CPU cost. The 11.4 MB recorded trajectory
serialized in a mean 0.232 s with the standard writer versus 0.0178 s with
`orjson` over eight passes on this host. The outputs were byte-identical for
that trajectory. The profile and sample are ignored local artifacts at
`.cache/goat-ai/train_profile_18000.prof` and
`.cache/goat-ai/train_profile_18000_replays/`.

The `--fast-trajectory-json` path uses `orjson`'s native dataclass writer.
Install the optional dependency with `pip install '.[speed]'`; the trainer now
uses it automatically when installed and otherwise uses standard JSON.
`--standard-trajectory-json` forces the standard writer. The initial complete
one-game training comparison
used the same fv23 checkpoint, seed 18100, experimental native engine,
control/Chaos probe decks, batch size 16, and one Torch CPU thread. Each arm
recorded 1,115 decisions in a byte-identical 13,218,971-byte trajectory
(SHA-256 `1fbd10a54ac9d0c8674753357dcdbe46a2f9ea58564552e8e7144f5cb8cb9081`).
Model tensors were exactly equal. Standard/fast reported training wall times
were **2.497/2.260 s** and **2.458/2.219 s** in AB/BA order, or **1.105×**
and **1.108×** speedups. The fast trajectory passed native verification of
all 1,115 decisions and the player-visibility audit. Full process wall times,
which include Python/Torch startup, were 3.841/3.619 s and 3.800/3.582 s.
These are one-game CPU measurements, not multi-game scaling or a strength gain.
The ignored comparison is `.cache/goat-ai/fast_json_benchmark_18100/report.json`.

Reproduce one arm from the repository root, changing `MODE` and adding
`--standard-trajectory-json` for the standard arm, or
`--fast-trajectory-json` for the fast arm:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v6_current_assets.pt \
  --output .cache/goat-ai/json_MODE_18100.pt --engine experimental \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk \
  --seed 18100 --games 1 --max-decisions 3000 --reinforce-batch-size 16
```

After making the fast writer automatic, a second AB/BA comparison used the
same feature-v23 checkpoint and decks with seed 18102. Each arm finished
1,556 decisions and produced a byte-identical 21,399,927-byte replay (SHA-256
`0a497d54fe680104bc68dda0d6db517bf8f536e0a63f470bf65f5cd16b4ac091`).
The saved model's 38 tensors were exactly equal across writers. The automatic
writer's replay passed native verification of all 1,556 decisions and the
player-visibility audit. Standard/automatic reported training wall times were
3.948/3.458 s and 3.879/3.472 s in reversed orders, or **1.142×** and
**1.117×** ratios. These are two runs of one CPU duel, not a multi-game
throughput estimate or evidence of improved playing strength. The ignored
checkpoints and replays are under `.cache/goat-ai/` with
`standard_json_18102` and `auto_json_18102` prefixes.

## Sixteen-game PPO rollout workers

On 27 October 2026, four consecutive matched self-play runs compared one
versus four persistent rollout workers on an Intel Core i7-10700K. Each arm
started from the same feature-v23 checkpoint (SHA-256
`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`),
played Jesse Goat Control against Warrior on seeds 28000–28015, and used
four-game frozen PPO rollouts, two update epochs, minibatch 16, a 3,000-decision
cap, and `OMP_NUM_THREADS=1`. The execution order was one, four, four, one.

| Run | Workers | CLI-reported training wall | Complete decisions |
| --- | ---: | ---: | ---: |
| 1a | 1 | 10.332 s | 7,046 |
| 4a | 4 | 7.474 s | 7,046 |
| 4b | 4 | 7.631 s | 7,046 |
| 1b | 1 | 10.529 s | 7,046 |

Four workers were **1.38× faster** in both adjacent comparisons. Every arm
finished all 16 duels with no decision-cap censoring and 1,196 learner
decisions. The 16 trajectory SHA-256 values and all saved model tensors matched
exactly across the four arms. One complete arm independently replay-verified
all 7,046 decisions against the pinned native core and passed the
player-visibility audit. The reports, checkpoints, and trajectories are ignored
local artifacts named `.cache/goat-ai/worker_bench_{1a,4a,4b,1b}_28000*`;
the report SHA-256 values in that order are
`a73b503c3205b7b2f8e948661846b90cf6c98467f283df4cfad282d9e9298cbf`,
`5643c2864718b74cdf2ea645bd1b51951e3c18bad5122bf089f4c7ec1232c247`,
`fbf1cddd8fcb3c2fa00edcf4d08a31bbe07c80202aac6e79e4e8dc14c0a98fe9`,
and `66be601c67ba20733431a437eee43a991a3f935ba64aa0a1fd885ece15ac3585`.

Reproduce one arm after native setup, changing the worker count and output
name for each run:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --seed 28000 --games 16 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 \
  --ppo-epochs 2 --ppo-batch-size 16 --snapshot-every 4 \
  --rollout-workers 4 --output .cache/goat-ai/worker_bench_4a_28000.pt
```

This supports using `--rollout-workers 4` for comparable CPU PPO jobs on this
host. It does not establish speedup on other machines, deck families, or
larger policies, nor any increase in playing strength. The measured wall time
includes CLI training, replay writing, and checkpoint saving after Python
startup; it is not a separate process-launch measurement.

## Four-worker PPO parent-process profile (2026-10-27)

The same 16-game, four-worker schedule above was rerun under `cProfile` with
output `.cache/goat-ai/ppo_parent_profile_28000.prof`. The trainer reported
8.623 seconds and completed the same 7,046 decisions. All 16 trajectory files
were byte-identical to the earlier four-worker arm, and all 38 saved model
tensors were exactly equal. Profiling raised wall time, so its timings should
be used to locate work, not as an unprofiled throughput measurement.

In the parent profile, `ppo_clipped_update` accounted for 4.918 seconds of
cumulative time across four updates. Its 228 batched policy forwards accounted
for 3.605 seconds of cumulative time; 1,196 decision encodes accounted for
0.629 seconds. The process-pool wait and shutdown entries include time spent
waiting for child processes and overlap with other activity; their cumulative
times cannot be added to the PPO times to make a wall-time budget. The profile
does **not** include a per-function breakdown inside the rollout workers.

To check whether worker result transfer was a likely bottleneck, one direct
seed-28000 native episode produced 356 decisions and 52 learner decisions.
Its `EpisodeResult` occupied 250,062 bytes when pickled with the highest
protocol; serialization and deserialization took 0.0034 and 0.0036 seconds
on this host. Omitting its trajectory reduced the pickle to 46,737 bytes but
saved only about 0.0027 seconds of serialization time. Constructing a v23
policy took about 0.00146 seconds per model over 100 constructions, and
loading its state took about 0.00035 seconds per load. These are narrow
single-process timings, not worker IPC or end-to-end speedups. They make
model-instance caching and trajectory-free worker returns lower priorities
than improving the parent PPO batched forward path. Any change there must
preserve replay bytes and be evaluated on held-out strength as well as speed.

## PPO minibatch 16 versus 32 (2026-10-27)

With the same v23 parent, Jesse Goat Control/Warrior pairing, seeds
28000–28015, four rollout workers, two PPO epochs, and one CPU Torch thread,
the existing `--ppo-batch-size 16` setting took 7.474, 7.631, and 7.609
seconds in three complete runs. `--ppo-batch-size 32` took 6.727 and 6.517
seconds in two complete runs. Each repeat of a given setting saved identical
model tensors. Batch 32 changed the policy updates and subsequent duels: it
produced 1,119 learner decisions versus 1,196 for batch 16. Thus the full-run
times are evidence for this schedule, but do not isolate computation saved
per PPO update.

For a fixed-update comparison, the first four batch-16 replay files supplied
304 player-visible learner decisions. Two CPU-time rounds in reversed order
ran the same two-epoch clipped PPO update from a fresh copy of the same parent
with batch 16 and batch 32. Batch 16 took 0.5454 and 0.5289 seconds; batch 32
took 0.3947 and 0.3895 seconds. The different losses reflect different
minibatch updates, not an equivalence claim. Batch 32 is a useful opt-in speed
setting, pending stronger held-out playing-strength evidence. The generated
checkpoints, replays, and JSON reports use `ppo_batch{16,32}_28000_*` names
under ignored `.cache/goat-ai/`.
