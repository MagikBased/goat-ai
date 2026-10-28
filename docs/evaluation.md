# Baseline evaluation log

## Current-core policy on independent 2005 decks (27 October 2026)

The selected feature-v23 checkpoint
`.cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt` (SHA-256
`975d06284b3035bc8bf8dbafa041a8a25a80195574d1ff695f2fbd25d1c7ff45`)
played Tactical-v14 on Phoenix Control versus Charlotte Zombie and Rhymus
Goat Control versus Charlotte Zombie. These are three published 2005 Main
Decks absent by composition hash from the checkpoint's training provenance.
Seeds 49500–49507 covered both deck assignments and both policy seats: **64
terminal duels**, **25 wins and 39 losses** for the policy (39.1%, paired-seed
95% score interval 29.7%–50.0%). By assigned policy deck it went 7–9 with
Phoenix, 9–7 with Rhymus, and 9–23 with Zombie. This does not show strength
over Tactical or close M4.

A Tactical-v14 mirror on the same seeds and deck assignments went 16–16 in
each pairing. Its assigned Zombie deck went 11–21 across the pairings, showing
substantial deck asymmetry even with the same agent on both sides. The policy
scored **10.9 percentage points lower** than the matched mirror baseline;
the paired matchup-seed bootstrap interval was **−20.3 to 0.0 points**.
Thus the raw Zombie split should not be read as a 23-game policy deficit.
The policy and rerun mirror reports match on the native core commit, every
recorded native asset hash, card-script hash, local YDK hashes, and Main Deck
composition hashes. `evaluate_native.py` now records the unofficial card
database and Main Deck compositions as `evaluate_policy.py` already did; the
initial mirror reports omitted those fingerprints and were replaced.

The ignored policy report SHA-256 is
`34e53735526350504a84c268559220a9c22d0f749c611cb15cf62be3af3aa94f`.
The Phoenix/Zombie and Rhymus/Zombie mirror report hashes are respectively
`d20f2a95c90ff801cf1a46f756fa8890544b1bd736441e84152412ae42723f5a`
and `ee07eb7272af4f7c6928b2dc701e10ae5dabc37df85fbf487ea88ad9f41a3a2a`.
Reproduce with `scripts/evaluate_policy.py --engine experimental --opponent
tactical --both-deck-assignments --require-unseen-main-decks --seed 49500
--seeds 8 --workers 4 --max-decisions 3000` and the two pairings above;
use `scripts/evaluate_native.py --agent-a tactical --agent-b tactical` on
each pairing with the same schedule. The comparison used
`paired_score_difference` from `goat_ai.evaluation.tournament` on the three
reports' saved `GameResult` fields.

`scripts/compare_policy_baseline_mirror.py` now reproduces that comparison
with gates for the exact role schedule, local deck bytes and compositions,
native assets, core revision, card scripts, baseline version, and saved
outcomes. It rejects a changed report or deck before reporting a difference.
The ignored comparison report SHA-256 is
`40608d142d26ff2350d0795bbc4fc480c87f78673b8fb48085755b843dd43bf6`.
Run it as:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/compare_policy_baseline_mirror.py \
  .cache/goat-ai/fv23_current_vs_tactical_2005_holdout_49500_49507.json \
  .cache/goat-ai/tactical_mirror_phoenix_zombie_49500_49507_v2.json \
  .cache/goat-ai/tactical_mirror_rhymus_zombie_49500_49507_v2.json
```

Separate development seeds 49600–49601 then yielded eight policy-versus-
Tactical duels and **3,565 replay-verified, visibility-audited decisions**.
The local review shortlister selected 24 of 122 candidates, balanced 12 per
policy seat across eight duels. Two selected frames have conservative visible
flags (own-only Nobleman and negative Heavy Storm); one flagged play was also
chosen by Tactical. These are prompts for human judgment, not training labels.
An independent full-replay audit reproduced the greedy policy choices and
found exactly those two conservative flags among all 3,565 decisions; its
ignored report SHA-256 is
`64abb298113b7ea94e7216f95d0adfb52d29756e37d8bf7846aebb5db8946a21`.
The [development review queue](../.cache/goat-ai/current_2005_development_review_49600_49601/queue.html)
uses the local save server documented in [the replay audit](replay_audit.md).
If its labels are used for training, these three deck compositions must be
excluded from later held-out strength evaluations.

## Fixed-policy visible-margin outcome diagnostic (27 October 2026)

The same 64 frozen-checkpoint, native-verified policy-versus-Tactical duels
used for the [critic check](#fixed-policy-visible-state-critic-check-27-october-2026)
also test the user's card-advantage hypothesis without a policy-change
confound. At the first policy-seat Main Phase 1 of turn 4 in each duel, one
player-visible snapshot counted hand and field cards, excluding Sheep Tokens,
and compared that margin with the eventual binary outcome. It also recorded
the visible Life Point margin. Each duel contributes one sample, including
both deck pairings and policy seats; the policy won 18/64 games. The saved
summary checks all snapshot hashes against the collector manifest. The
separate critic comparison had already independently replay-verified the
same 31,729 decisions and reproduced the checkpoint's 15,704 choices.

Overall win-versus-loss ranking AUC was **0.561** for visible card count and
**0.671** for Life Point margin. Resampling whole four-game seeds 10,000
times gave 95% intervals **0.370–0.759** for card count and **0.505–0.830**
for Life Points. The paired LP-minus-card AUC interval was **−0.203 to
+0.402**; this small corpus does not establish that either margin is better.
By pairing, card-count AUC was **0.514** for Jesse Goat Control/Warrior and
**0.628** for Phoenix/Dimension Fusion; LP AUC was **0.668** and **0.742**.
Card count alone is a weak and uncertain early predictor here. Later-turn
snapshots are conditional on duels lasting that long and can reflect the
consequence of winning, so this retrospective audit does not identify an
action's causal value or justify a shaped reward. It also omits card quality,
hidden holdings, and future draws.

The ignored raw audit SHA-256 is
`cdc560e583c1cfb6fcd5ad210bd220c591a4554677ca033d624104854866b92b`;
the ignored summary SHA-256 is
`5af727ea547662c7a2af809361d0052ea8ea7409bb10e7999aac6127cf6e068d`.
Reproduce after the fixed-policy collection above with:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/audit_visible_value_signals.py \
  .cache/goat-ai/fixed_policy_value_44000_44015 --turn 4 \
  --output .cache/goat-ai/fixed_policy_value_signals_44000_44015.json
PYTHONPATH=src:. .venv/bin/python scripts/summarize_fixed_policy_value_signals.py \
  .cache/goat-ai/fixed_policy_value_signals_44000_44015.json \
  .cache/goat-ai/fixed_policy_value_44000_44015/manifest.json \
  --seed 171 --replicates 10000 \
  --output .cache/goat-ai/fixed_policy_value_signals_summary_44000_44015.json
```

## Fixed-policy visible-state critic check (27 October 2026)

To remove the policy-change confound in the earlier v1/v2 critic comparison,
the unchanged current-core feature-v23 checkpoint
`.cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt` (SHA-256
`975d06284b3035bc8bf8dbafa041a8a25a80195574d1ff695f2fbd25d1c7ff45`)
played Tactical-v14 on two deck pairings: Jesse Goat Control versus Warrior,
and 2005 Phoenix Control versus WikiFormat Dimension Fusion. Seeds
44000–44015 covered both policy seats for each pairing, producing **64
complete duels and 31,729 native replay-verified, visibility-audited
decisions**. The critic comparison independently verified every trajectory
and reproduced **15,704 recorded policy choices** against the unchanged
checkpoint. The collector manifest SHA-256 is
`93c2f2f5f768b912b76d9033408f833a1eef972a6d1371021f6a3287b72fffa6`.

The first 12 whole seeds supplied 48 training duels with 768 evenly spaced
multi-option policy-seat decisions; the final four whole seeds supplied 16
holdout duels with 256 such decisions. Each split has both pairings and seats.
The critics each used width 32, two epochs, learning rate 0.001, and the same
initial seed 171. Targets were the learner's terminal win/loss outcome; a
constant predictor used the training games' mean return. On the holdout,
per-game mean squared error was **0.866** for the constant, **1.151** for v1,
and **1.169** for v2. The v2-minus-v1 paired bootstrap 95% interval was
**−0.005 to +0.055**, so this sample does not distinguish their errors. The
first pairing had 2/8 policy wins on holdout; the second had 3/8. This is a
value-prediction diagnostic, not a policy-strength result. These critics do
not justify changing the default PPO baseline on this fixed-policy evidence.
Training on more diverse fixed-policy games or a different value objective
remains open; repeated tuning against these 16 holdout games would invalidate
their use as an untouched check.

The ignored report is
`.cache/goat-ai/fixed_policy_value_comparison_44000_44015.json` (SHA-256
`44ad61ed9ce5ecb3b97d3483ecbdf08a6d56fdccc91859c4e283dd602604c2d7`).
Reproduce from pinned native assets with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --matchup examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk \
            examples/decks/dimension_fusion_turbo_wikiformat_reference.ydk \
  --opponent tactical --seed 44000 --seeds 16 --workers 4 --max-decisions 3000 \
  --output-dir .cache/goat-ai/fixed_policy_value_44000_44015
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/compare_fixed_policy_values.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/fixed_policy_value_44000_44015/manifest.json \
  --holdout-seeds 4 --max-records-per-game 16 --epochs 2 --width 32 \
  --learning-rate 0.001 --seed 171 \
  --output .cache/goat-ai/fixed_policy_value_comparison_44000_44015.json
```

## Fixed-policy critic architecture transfer check (27 October 2026)

The v1/v2 critic comparison now accepts `policy_evaluation` trajectories and
selects only the frozen policy's `demonstrator_seat` decisions. On the 64-game
fixed-policy corpus above, seeds 44000–44011 supplied 48 training duels and
44012–44015 supplied 16 held-out duels, with both deck pairings and policy
seats in each split. An independently collected 16-game corpus used 2005
Rhymus Lizo Goat Control and Jae Kim Charlotte Zombie in both deck assignments
and policy seats, seeds 47400–47403. The frozen checkpoint is the same in all
80 duels. All **39,552 decisions** were native replay-verified and visibility
audited for this comparison; 768, 256, and 256 multi-option policy-seat
decisions were sampled from training, holdout, and independent games.

With width 32, two epochs, learning rate `0.001`, and seed 171, per-game
outcome MSE was:

| Predictor | Held-out seeds | Independent decks |
| --- | ---: | ---: |
| Constant training-return mean | 0.866 | 0.866 |
| v1 visible-state critic | 1.151 | 1.150 |
| v2 visible-state critic | 1.169 | 1.187 |

The v2-minus-v1 paired bootstrap 95% interval was **−0.005 to +0.055** on
held-out seeds and **+0.001 to +0.078** on independent decks. Both fitted
critics underperform the constant baseline on these data. The independent
deck result supports v1 over v2 for this specific fit, but neither critic
has earned use as a PPO baseline. This experiment used one training seed and
only 16 independent games; it is a prediction diagnostic, not a measured
policy-strength change.

The ignored independent collection manifest SHA-256 is
`716444777065171464b17a84c9a663c8f785151fa9570181ad173067e98cc0f4`;
the original two-critic comparison report SHA-256 is
`4d240379f2c9fb1a57465b4081071ed9f603edbc964d41e4aac449c0cded5320`.
An additional six-input visible-resource control used
acting-player-minus-opponent Life Points, hand size, monster count, backrow
count, Deck count, and turn. Under the same two-epoch Adam schedule it scored
**1.309** MSE on held-out seeds and **1.233** on independent decks, also worse
than the constant. This small model may be underfit at the shared learning
rate; the result only rules out this fit. Its updated ignored report SHA-256 is
`6103d38a9241a2fc180a27929e905b1af3e66762ebd54689f1ec55ac991a6424`
at `.cache/goat-ai/fixed_policy_resource_transfer_44000_47403.json`.
Reproduce after the 64-game collection above with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --matchup examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk \
            examples/decks/zombie_jae_kim_charlotte_2005.ydk \
  --matchup examples/decks/zombie_jae_kim_charlotte_2005.ydk \
            examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk \
  --seed 47400 --seeds 4 --workers 4 \
  --output-dir .cache/goat-ai/fixed_policy_value_rhymus_zombie_47400_47403
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/compare_value_architectures.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/fixed_policy_value_44000_44015 \
  --corpus-source policy_evaluation \
  --independent-replay-dir .cache/goat-ai/fixed_policy_value_rhymus_zombie_47400_47403 \
  --train-games 48 --max-records-per-game 16 --epochs 2 --width 32 \
  --learning-rate 0.001 --seed 171 \
  --output .cache/goat-ai/fixed_policy_resource_transfer_44000_47403.json
```

## Fixed-policy resource regression check (27 October 2026)

The earlier six-input resource network underfit on the shared two-epoch Adam
schedule. A separate closed-form ridge regression now uses the same six
player-visible differences: Life Points, hand count, monster count, backrow
count, Deck count, and turn. Each duel has equal total weight regardless of
its number of sampled decisions. The six inputs are standardized using only
training games, the intercept is unpenalized, and the fixed coefficient
penalty is `0.1` per training game. Predictions are clipped to the legal
terminal-return range of −1 to +1. No hidden identities, future outcome, or
opponent Deck order enter a prediction.

The frozen feature-v23 policy supplied 48 training duels (seeds 44000–44011)
and 16 held-out duels (44012–44015) from the prior corpus. A new
16-duel transfer check used the Guide Dimension Fusion Turbo and Rhymus Lizo
Goat Control decks in both assignments and policy seats, seeds 48100–48103.
Both Main Deck compositions are absent from the policy checkpoint's
training games. The new collection recorded **7,402 decisions**. The
comparison independently native replay-verified and visibility-audited all
**39,131 decisions** across 80 duels, and sampled 768 training, 256 held-out,
and 256 transfer decisions with multiple legal actions.

| Predictor | Held-out seed MSE | New pairing MSE |
| --- | ---: | ---: |
| Constant training-return mean | 0.866 | 0.637 |
| v1 embedding critic | 1.151 | 0.698 |
| v2 embedding critic | 1.169 | 0.705 |
| Two-epoch resource network | 1.309 | 1.412 |
| Closed-form resource ridge | **0.692** | **0.572** |

The ridge-minus-constant paired bootstrap 95% interval was **−0.424 to
+0.056** on held-out seeds and **−0.292 to +0.099** on the new pairing.
The point estimates favor the ridge baseline, but both intervals include
zero. This is a retrospective outcome-prediction diagnostic on only 16 games
per check, not evidence of a stronger playing policy or of causal value for
the six features. Keep the current self-play baseline unchanged; an opt-in
ridge-baseline ablation needs a larger independent schedule and held-out
competitive matches before promotion.

The ignored new collection manifest SHA-256 is
`4ab7476326cac52628822f80ecf0a43f6309d63256c25799304e6fd0fdb78c72`;
the ignored comparison report SHA-256 is
`e828e8aee472fa4dee656b06ac4b6c628384ee20758212d1f32191a5a6080b95`.
Reproduce after the 64-game fixed-policy collection above with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --matchup examples/decks/dimension_fusion_turbo_goatformat_guide.ydk \
            examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk \
  --matchup examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk \
            examples/decks/dimension_fusion_turbo_goatformat_guide.ydk \
  --seed 48100 --seeds 4 --workers 4 \
  --output-dir .cache/goat-ai/fixed_policy_value_dimension_rhymus_48100_48103
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/compare_value_architectures.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/fixed_policy_value_44000_44015 \
  --corpus-source policy_evaluation \
  --independent-replay-dir .cache/goat-ai/fixed_policy_value_dimension_rhymus_48100_48103 \
  --train-games 48 --max-records-per-game 16 --epochs 2 --width 32 \
  --learning-rate 0.001 --seed 171 \
  --output .cache/goat-ai/fixed_policy_resource_ridge_44000_48103.json
```

## Frozen mirror self-play value transfer (27 October 2026)

The policy recorder now supports `--opponent mirror_policy`: it loads the same
frozen checkpoint independently for each seat and records the opponent
checkpoint hash. This makes a deterministic self-play value diagnostic without
PPO changing the policy during data collection. With both `--policy-seat`
values on each seed/deck assignment, a physical duel is recorded twice, once
for each player's outcome perspective. These are **not independent duels**;
uncertainty below resamples whole seed blocks, keeping both assignments and
perspectives together. All replays were native verified and visibility audited.

First, the six-resource ridge fitted on policy-versus-Tactical games above
was tested on **16 mirror records** (eight distinct duels) from Phoenix
Control versus Guide Dimension Fusion Turbo, both assignments, seeds
48200–48203. It scored **1.071** per-game outcome MSE. The Tactical-trained
constant scored 1.210, but a zero-return mirror baseline scored **1.000**.
The ridge-minus-zero seed-clustered bootstrap 95% interval was **+0.003 to
+0.141**. This fit does not justify use in self-play PPO.

A separate ridge was then fitted on **96 mirror records** from 2005 Rhymus
Goat Control versus Charlotte Zombie, both assignments and perspectives,
seeds 48300–48323. The remaining **32 records**, seeds 48324–48331, were
held out; the Phoenix/Dimension 16 records supplied a different-deck check.
The 128 Rhymus/Zombie records contain 64 distinct frozen-policy duels and
**68,840** decisions. The final comparison independently replay-verified and
visibility-audited **77,124** decisions across all 144 records. The ridge
uses only six acting-player-visible resource differences, equal total weight
per recorded perspective, fixed L2 shrinkage, and no hidden card identities.

| Predictor | Held-out Rhymus/Zombie MSE | Phoenix/Dimension MSE |
| --- | ---: | ---: |
| Zero-return mirror baseline | 1.000 | 1.000 |
| v1 embedding critic, two epochs | 0.895 | 1.342 |
| v2 embedding critic, two epochs | 0.895 | 2.050 |
| Resource network, two epochs | 1.089 | 1.083 |
| Self-play-trained resource ridge | **0.727** | **0.790** |

Ridge-minus-zero 95% intervals from whole-seed bootstrap were **−0.394 to
−0.122** on eight held-out seeds and **−0.292 to −0.067** on four
different-deck seeds. The point estimate and interval favor this small
value model on these fixed-policy trajectories, but the different-deck check
has only four seed blocks. Outcome prediction is not a measured improvement
in decisions or competitive strength. The selected policy and PPO baseline
remain unchanged pending a controlled PPO ablation and held-out matches.

The ignored 128-record collection manifest SHA-256 is
`a25f84b405cc9859e281299b5c8cbfc3584008e6bc134b842ae22baef0341116`;
the independent 16-record manifest SHA-256 is
`04c4d2b0ec07acfcf067a2a2aafd29dccfb158582657d5c1c4450a0fc955e4b5`.
The mirror-trained report SHA-256 is
`6c720d808f6221fa8132d0b610b69ea4f603caa5eb78ad023b90ce124ebdb37c`.
Reproduce with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --opponent mirror_policy \
  --matchup examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk \
            examples/decks/zombie_jae_kim_charlotte_2005.ydk \
  --matchup examples/decks/zombie_jae_kim_charlotte_2005.ydk \
            examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk \
  --seed 48300 --seeds 32 --workers 4 \
  --output-dir .cache/goat-ai/fixed_policy_mirror_rhymus_zombie_48300_48331
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --opponent mirror_policy \
  --matchup examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk \
            examples/decks/dimension_fusion_turbo_goatformat_guide.ydk \
  --matchup examples/decks/dimension_fusion_turbo_goatformat_guide.ydk \
            examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk \
  --seed 48200 --seeds 4 --workers 4 \
  --output-dir .cache/goat-ai/fixed_policy_mirror_phoenix_dimension_48200_48203
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/compare_value_architectures.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/fixed_policy_mirror_rhymus_zombie_48300_48331 \
  --corpus-source policy_evaluation --primary-mirror-policy \
  --independent-replay-dir .cache/goat-ai/fixed_policy_mirror_phoenix_dimension_48200_48203 \
  --independent-mirror-policy --train-games 96 --max-records-per-game 16 \
  --epochs 2 --width 32 --learning-rate 0.001 --seed 171 \
  --output .cache/goat-ai/fixed_policy_mirror_ridge_48300_48331.json
```

## Frozen resource-ridge PPO ablation (27 October 2026)

An opt-in `resource_ridge` baseline now supplies a separate predicted return
for every learner decision in multi-duel PPO. It is fitted only on the 96
frozen mirror training records above, then held constant during PPO. The
exporter independently native replay-verifies and visibility-audits those
source records, reproduces the reported regression coefficients, and writes
normalization, coefficients, checkpoint/report hashes, and all 96 replay
hashes. The trainer checks those bytes before using the artifact. Neither
the resource model nor its training replays enter the agent's observations.

A four-game native smoke run completed. The controlled training run then used
the same selected feature-v23 parent, two 2022 training pairings, 128 four-role
seeds 47000–47127, four workers, four-duel PPO rollouts, per-episode weighting,
three epochs, batch size 16, learning rate 0.0001, parent KL 0.1, and snapshot
pool as the [longer lower-KL control](#longer-lower-kl-ppo-continuation-27-october-2026).
Only the advantage baseline changed from learner-deck moving return to the
frozen visible-resource prediction. All 128 games reached terminal: 76 learner
wins, 52 losses, 16,304 learner decisions. Measured training wall time was
**107.09 s** with `OMP_NUM_THREADS=1`. These training wins do not estimate
playing strength. All **91,218** recorded decisions independently replay-
verified and passed the visibility audit; 218 heuristic review flags are
prompts, not proven mistakes.

Held-out competitive tests used both deck assignments and policy seats, 16
new seeds per pairing, `--require-unseen-main-decks`, and the same native
assets. Phoenix Control versus the GoatFormat Guide Dimension Fusion list
used seeds 47300–47315; Phoenix versus the separate WikiFormat Dimension
Fusion reference used seeds 49200–49215. The exact Main Deck compositions are
absent from both policy checkpoints' training histories. The ridge value fit
used neither evaluation composition in its 96 fitting records; Phoenix/Guide
was an earlier value-validation pairing, so it is not untouched for model
selection.

| Held-out pairing | Ridge child vs PPO control | Ridge child vs original parent | Ridge vs Tactical | PPO control vs Tactical |
| --- | ---: | ---: | ---: | ---: |
| Phoenix / Guide Dimension Fusion | 33–31 | 31–33 | 23–41 | 20–42–2 |
| Phoenix / Wiki Dimension Fusion | 28–36 | Not run | 17–45–2 | 15–49 |

The direct ridge-versus-control paired bootstrap score intervals were
**40.6–62.5%** and **34.4–51.6%**. The paired ridge-minus-control Tactical
score differences were **+3.1 points** (95% interval −8.6 to +14.1) and
**+4.7 points** (−6.3 to +16.4). The Phoenix/Guide direct result against the
original parent was 31–33 (95% score interval 37.5–59.4%). No interval
establishes a gain. The selected parent remains unchanged; better
terminal-outcome prediction did not translate into demonstrated stronger play
under this PPO schedule.

Ignored artifacts are the ridge model
`.cache/goat-ai/frozen_resource_ridge_48300_48323.json` (SHA-256
`7115d29f4a6bedd2de870d26f43c570a902ab342a50593d185e4aa55dbb092dc`),
child checkpoint `.cache/goat-ai/fv23_ppo_ridge_128_47000_47127.pt`
(`7d2f1fa807f87f169fcedcc4a1bc48705bce9c1138e31768d16a5e5ed399bc42`),
and audit `.cache/goat-ai/fv23_ppo_ridge_128_47000_47127_audit.json`
(`5a9e8fa375e2520fd45899b5f07ca5583ca175784f00971ccd6735703c31b18d`).
The seven ignored held-out reports are bound by their SHA-256 hashes:
Phoenix/Guide direct control `52fa817b7c506173354c994bae5ffbf9482e90a0efdf7c9edec61eba97391c9c`,
direct parent `f924b5660c229016271ab3bca7fdded206514dd22d51e7e900c2aec5b98ac1ea`,
ridge Tactical `e74551a7bb092229480b4f30a119bff863e79c45a019affb37199b5ffe256a84`,
control Tactical `288c99773dc24c65c358bf0d8031c9eef9aa995803335ffc1cbf05c11f2f9f66`;
Phoenix/Wiki direct control `d82fd31fbbd5040fa43e98d780886d828e530f7779fa9e237bc978a875b2ae68`,
ridge Tactical `960316709c1ad6d0ad08d46a2aa45bc6d6dfcfc777c1b2ed8b49380c83326944`,
control Tactical `ebe420af454369347869ec162603ca19da17ea853dd6bb5bd00de0d9a7d19757`.
The current-source comparator verified both matched Tactical pairs against
local deck files and unseen Main Deck provenance.

Reproduce the fitted baseline and training after the mirror collections:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/export_resource_ridge.py \
  .cache/goat-ai/fixed_policy_mirror_ridge_48300_48331.json \
  .cache/goat-ai/fixed_policy_mirror_rhymus_zombie_48300_48331 \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --output .cache/goat-ai/frozen_resource_ridge_48300_48323.json
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --engine experimental \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
            examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --schedule-mode four_roles --seed 47000 --games 128 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 --rollout-workers 4 \
  --ppo-rollout-weighting per_episode --ppo-baseline-timing online \
  --ppo-epochs 3 --ppo-batch-size 16 --ppo-clip-epsilon 0.2 \
  --learning-rate 0.0001 --parent-kl-weight 0.1 --baseline-scope resource_ridge \
  --resource-ridge-artifact .cache/goat-ai/frozen_resource_ridge_48300_48323.json \
  --snapshot-every 4 --max-snapshots 8 \
  --output .cache/goat-ai/fv23_ppo_ridge_128_47000_47127.pt
```

## Visible-state critic architecture transfer check (27 October 2026)

The original opt-in Monte Carlo critic (v1) averages all visible card
embeddings. A versioned v2 experiment separately pools each player's visible
cards, adds current public ATK/DEF and counters, counts cards in each visible
zone, and embeds the player's own initial Main Deck. It receives only
`DecisionFeatures` made from the acting player's observation; action order
does not affect its score. The prior v1 architecture and existing critic
checkpoints remain compatible, and v1 remains the default.

Both critics were fitted to terminal outcomes from the same 48 replay-verified
self-play games (seeds 17000–17047), with 16 evenly spaced learner decisions
per game, two epochs, width 32, learning rate `0.001`, and seed 171. The next
16 games from that run (17048–17063) were held out. Another 32 complete
replays (11820–11851), generated from the same parent but a different PPO
continuation, formed an independent validation corpus. All **96 replays and
49,851 decisions** passed fresh native replay verification and the visibility
audit; no opponent-seat decisions became training examples.

Per-game mean squared error on the first holdout was **0.739** for v1 and
**0.702** for v2, against **0.813** for a constant training-return predictor.
On the independent corpus, v1 scored **0.894**, v2 **1.094**, and the constant
predictor **0.969**. The paired bootstrap interval for v2 minus v1 MSE was
−0.364 to +0.269 on the 16-game holdout and −0.096 to +0.509 on the
32-game independent set. The v2 result does not establish a better value
signal and does not justify changing the training default or claiming a
playing-strength gain. These are outcomes from changing policies' recorded
games; a future critic test should also use fixed-policy data and a larger
independent holdout.

An opt-in `--baseline-scope state_value --value-architecture v2` one-game
native training smoke at seed 17200 reached terminal, saved versioned critic
weights, and replay-verified all 587 decisions with the visibility audit. It
checks that the architecture can be trained and resumed as a separate critic;
it is not a strength or calibration result.

The ignored report is
`.cache/goat-ai/value_v1_v2_independent_17000_17063.json` (SHA-256
`f5d3a630c2ec188f134d85fc9205805174e80de26fb6e135b85bf4b3ad45a5a7`).
Reproduce with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/compare_value_architectures.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  .cache/goat-ai/ppo_balanced_64_17000_17063_replays \
  --independent-replay-dir .cache/goat-ai/ppo_rollout4_equal_11820_11851_replays \
  --train-games 48 --max-records-per-game 16 --epochs 2 --width 32 \
  --learning-rate 0.001 --seed 171 \
  --output .cache/goat-ai/value_v1_v2_independent_17000_17063.json
```

## Balanced parallel PPO continuation across four roles (27 October 2026)

The feature-v23 four-deck parent
(`.cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt`, SHA-256
`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`)
was continued through **64 native self-play duels** on two established deck
pairings: Jesse Twohig Goat Control versus Montague Warrior, and DingoSig
Chaos Return versus GoatFormat Guide Flip Control. The four-role schedule
assigned the learner each deck in both seats. Seeds were 17000–17063, with
four duels per frozen-policy PPO rollout, four CPU rollout workers, per-episode
weighting, three PPO epochs, minibatch 16, learning rate `1e-4`, learner-deck
moving baselines, historical-snapshot probability 0.75, and frozen-parent KL
weight 0.5. All **64/64** games reached terminal (30 wins, 31 losses, three
draws), producing 5,440 multi-option learner decisions in **43.48 seconds**
of reported wall time. Every saved replay passed full native verification and
the player-visible audit, totaling **33,341 decisions**. The checkpoint is
`.cache/goat-ai/ppo_balanced_64_17000_17063.pt` (SHA-256
`3abbabf0508dae326d1666e6e64e0b8cbd9d2c647d256507978576899a7a4c4b`).

Both parent and child passed the exact unseen-Main-Deck composition gate for
the 2005 Phoenix Control versus WikiFormat Dimension Fusion matchup. On fresh
seeds 17100–17123, both deck assignments and both agent seats, the child
scored **44–50–2** directly against its parent over 96 duels (paired-bootstrap
score interval **39.6–54.2%**). By child deck it scored **30–17–1** with
Phoenix and **14–33–1** with Dimension Fusion. On another fresh 64-game
schedule against Tactical v14 (seeds 17130–17145), both child and parent
scored **16–48** overall. Child deck splits were 13–19 Phoenix and 3–29
Dimension Fusion; parent splits were 11–21 and 5–27. These separate baseline
matches do not establish a paired improvement; the direct match also fails
the strength gate. Keep this child experimental and the parent as the neural
reference. More terminal-reward PPO updates of this form are lower priority
than stronger decision feedback or a validated value signal.

The ignored training JSON is
`.cache/goat-ai/ppo_balanced_64_17000_17063.json` (SHA-256
`5903bbccb9a4a463217dcfea88ee34a7080db99b4e93b5ce0cd4518460c4cd59`);
the 64-replay audit is
`.cache/goat-ai/ppo_balanced_64_17000_17063_audit.json`
(`23c0dcae2f685af445d940f8933b47b802d699ad82dc75ce2a55b1f08aff0628`).
The direct report is
`.cache/goat-ai/ppo_balanced_64_vs_parent_17100_17123.json`
(`33b063eef88f1eb443a5cdedfced1bc301dd4f575d7665014e34a0672bc3c19e`);
child/parent Tactical reports are
`.cache/goat-ai/ppo_balanced_64_vs_tactical_17130_17145.json`
(`46eafbf797da61997ce25cfd3f71728e8dcc5d98615f4945268b7438622400c9`)
and `.cache/goat-ai/ppo_parent_vs_tactical_17130_17145.json`
(`33af91ca7e0dc71454f6b21a7fd2332b4fae0631c7718003fc887380cf52a77f`).
Reproduce with `scripts/train_self_play.py` using the two `--matchup` pairs,
`--schedule-mode four_roles --seed 17000 --games 64 --max-decisions 3000
--learning-rate 0.0001 --historical-probability 0.75 --snapshot-every 8
--baseline-scope learner_deck --parent-kl-weight 0.5 --policy-update
clipped_ppo --ppo-rollout-games 4 --rollout-workers 4
--ppo-rollout-weighting per_episode --ppo-epochs 3 --ppo-batch-size 16`.
Use `scripts/evaluate_policy.py --engine experimental
--both-deck-assignments --require-unseen-main-decks --workers 4` with the
two held-out decks and the recorded evaluation seed ranges.

## Phoenix Control historical effect line (27 October 2026)

The pinned GOAT scripts completed a sourced Hand of Nephthys / Scapegoat /
Sacred Phoenix of Nephthys line. Hand Tributed itself and a Sheep Token as a
cost to Summon Phoenix from the Deck. Torrential Tribute destroyed Phoenix,
which returned during its controller's next Standby Phase and then destroyed
an opposing Set Book of Moon. The native duel continued to a terminal result;
its trajectory replay-verified and passed the player-visible audit. Historical
sources and explicit remaining edge cases are in [GOAT rules](goat_rules.md).
This is a card-interaction correctness fixture, not a playing-strength result.

For M4 triage, the unchanged feature-v23 parent played a 391-decision
Dimension Fusion mirror against Tactical v14 at seed 16295 and lost. The
trajectory replay-verified. The existing teacher-disagreement queue selected
11 frames, including an early Card Destruction-versus-Thunder Dragon choice
and two Book of Moon response disagreements. These are review candidates,
not human correctness labels, and no policy was trained from them. Ignored
artifacts: `.cache/goat-ai/dimension_v23_vs_tactical_16295.json` (SHA-256
`8fc3ccd3489c989c1a1821f92cdc7b37c3e50c6600f0406195330077ca8a1a3e`)
and `.cache/goat-ai/dimension_v23_review_16295.json`
(`4b42f850767269fb4eb812a166928179897131c16b5395d9f5c0d485ac938a99`).

## Parallel frozen-policy PPO rollouts (27 October 2026)

The multi-duel PPO path now has an opt-in `--rollout-workers` setting. A frozen
learner and frozen snapshot opponent are copied at the start of each rollout
group; independent native duels run in CPU worker processes, and their results
are returned in schedule order before the PPO update. Worker processes stay
alive across groups. Each duel uses a seed-scoped Torch sampling generator,
so changing the worker count within this opt-in mode preserves sampled play.
The default `0` retains the earlier sequential sampling stream. One worker is
useful as a deterministic reference; more than one enables concurrency. This
path requires multi-duel PPO with terminal games and a moving baseline; it
does not parallelize REINFORCE or an individual duel.

On the Phoenix Control versus WikiFormat Dimension Fusion matchup, seeds
14860–14867, eight games in two frozen four-game PPO groups, the one-worker
run took **14.07 s** end to end and the persistent four-worker run **11.46 s**
(`time` wall clock, **1.23×** speedup). Training-reported wall time was
12.73 versus 10.12 s. Both runs had 5 wins, 3 losses, 1,290 learner
decisions, identical per-game reports and trajectory content hashes, and
bit-identical model tensors after both updates. The four-worker run's eight
replays passed full native verification and visibility audit across **5,592
decisions**. These timings include Python launch, rollout, PPO updates,
trajectory writing, hashing, and checkpoint writing. They are one measured
schedule on this machine, not a general scaling claim; process startup and
trajectory transfer limit the gain for short runs.

The ignored one-worker and four-worker JSON reports are
`.cache/goat-ai/ppo_parallel_long_serial_14860.json` (SHA-256
`977bfdf9f6c6f6192ecc3ff7b5c5596b2f6d10d19f8b3ed4eb88606b970a4e94`)
and `.cache/goat-ai/ppo_parallel_persistent_workers4_14860.json`
(`33830b74bd0e7e5ea9a11be34fc31eae773260e363db3fed4797d30148f214d1`).
The replay audit is `.cache/goat-ai/ppo_parallel_persistent_14860_audit.json`
(`04edbe48ff5e0749a0cfd7df67307fafe9d162915f56b733bed90d057b68844c`).
Reproduce with `scripts/train_self_play.py`, the feature-v23 four-deck parent,
`--engine experimental`, the two listed deck paths, `--seed 14860 --games 8
--max-decisions 3000 --policy-update clipped_ppo --ppo-rollout-games 4
--ppo-epochs 2 --ppo-batch-size 16 --snapshot-every 4`, and
`--rollout-workers 1` or `4`. Use distinct `--output` paths. This is a
throughput optimization; no policy-strength improvement is claimed.

## New Jersey 2005 Phoenix Control holdout (27 October 2026)

[Roberto Martinez's SJC New Jersey 2005 Top 8 list](https://www.goatformat.com/home/top-8-decklists)
is transcribed as [Phoenix Control](../examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk)
(YDK SHA-256 `b0356d0177bc864b81c41f1b1a31d1fde87b967cbdaa92b59717a3e950efd71a`).
Its published 40-card Main and 18-card Fusion Deck use pinned GOAT/pre-errata
IDs. The published Side Deck is omitted for single-duel fixtures. The
name-by-name source transcription and whitelist validation passed on pinned
native assets; Phoenix played complete duels in both seats against Matt
Peddle's Indianapolis 2005 list. Both trajectories replay-verified and passed
the player-visible audit. This checks protocol coverage, not every Phoenix
ruling.

The four-deck feature-v23 parent (`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`)
and six-deck continuation (`5941c66ec1ee68babf2f359c9e6dab807b3e50021761fe0ce8214aac873abab0`)
were compared on Phoenix Control and the independently sourced WikiFormat
Dimension Fusion Turbo list. Both Main Deck compositions passed the unseen
training-composition gate for both checkpoints. Seeds 16250–16273, both deck
assignments and both agent seats, produced 96 direct games. The child won
**56–40**; paired-bootstrap score interval **51.0–65.6%**. The split was
**35–13** with Phoenix and **21–27** with Dimension Fusion. This direct match
favors the child on the aggregate schedule, but its gain is concentrated in one
deck assignment.

On a separate same-seed 64-game schedule (16274–16289, both deck assignments
and seats) against Tactical v14, the parent scored **23–41** (paired-bootstrap
score interval **25.0–46.9%**) and the child **15–49** (**14.1–34.4%**). The
parent's Phoenix/Dimension Fusion splits were 16–16/7–25; the child's were
12–20/3–29. These are separate games against a deterministic baseline, not a
direct paired estimate of the difference in score. They show no absolute
playing-strength improvement over the parent. Keep the child experimental;
next training work needs deck-balanced held-out promotion criteria and a better
Dimension Fusion policy before adopting it as the reference.

The ignored JSON reports are
`.cache/goat-ai/phoenix_sixdeck_vs_fourdeck_16250_16273.json` (SHA-256
`a1e4b3dd42fbe6512bc35de8964104ba4bfa32fb55e9ee808aec4e4e9ac152be`),
`.cache/goat-ai/phoenix_fourdeck_vs_tactical_16274_16289.json`
(`833d12e40acbbc0da2d2ac737a7e924c6a345209bc187fe76c009dcb1b2f2542`),
and `.cache/goat-ai/phoenix_sixdeck_vs_tactical_16274_16289.json`
(`a28bd4a5073951fd5a59d37d8bf2ef1075fde0ce6be67a663ce8200a2bbcefd3`).
Reproduce with `scripts/evaluate_policy.py`, `--engine experimental`,
`--both-deck-assignments`, `--require-unseen-main-decks`, `--workers 4`,
the two `--matchup` paths above, and the indicated seed ranges. Set
`--opponent-checkpoint` to the parent for the direct comparison or
`--opponent tactical` for the two baseline checks. The direct 96-game run took
23.83 s on this machine (4.03 duels/s, 2,471 decisions/s); these timings
include Python policy inference and tournament overhead and are not native
simulator-only throughput.

## Independent Dimension Fusion reference list (27 October 2026)

[WikiFormat's published Dimension Fusion Turbo reference list](https://www.wikiformat.com/en/mazzi/dimension-fusion-turbo/)
provides a complete 40 Main / 15 Extra / 15 Side composition. Its [saved
source YDKE](../configs/decks/dimension_fusion_turbo_wikiformat_reference.ydke)
is transcribed into [a playable YDK](../examples/decks/dimension_fusion_turbo_wikiformat_reference.ydk)
with ten printed-card IDs replaced by the pinned GOAT or pre-errata variants.
The source snapshot SHA-256 is
`14573914215bc34b5d23d7c505675d4c61d60489facbe817c6abcc8b2d6ea192`;
the YDK SHA-256 is
`aaa971829ce795a90cafbafb8a84ee540ee141c10431e7c1c5d5f0871e5529d1`.
A test decodes every source card ID, checks the exact three-section
transcription and whitelist legality, then runs both deck seats against the
sourced Chaos Turbo list. Both native duels reached terminal, serialized,
replay-verified, and passed the player-visible trajectory audit. This is a
modern published reference list, not evidence of play in 2005 or a ruling
certification for every included card.

The feature-v23 checkpoint with SHA-256
`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`
was evaluated against Tactical v14, using seeds 13040–13047 and both deck
assignments and seats. Both this list and Michael Fukuyama's 2005 Goat
Control Main Deck passed the checkpoint's unseen-composition gate. The policy
scored **12–20 overall**: **2–14** piloting Dimension Fusion and **10–6**
piloting Goat Control. The paired bootstrap score interval was 28.1–46.9%.
On the same 32-game schedule, Tactical versus Tactical scored 5–11 with
Dimension Fusion and 11–5 with Goat Control, showing that the deck matchup
itself is uneven under this baseline. These are separate games; the score
differences are descriptive, not a paired policy-effect estimate.

A separate same-deck Dimension Fusion mirror on seeds 13060–13075 put the
policy against Tactical v14 in both seats. It scored **5–27** (paired bootstrap
score interval 6.25–28.13%), including 1–15 in first seat and 4–12 in
second seat. This is a direct new-composition weakness for the current policy,
although 32 games cannot identify its cause or establish general archetype
strength. A seed-13060 loss replayed and passed the visibility audit; the
greedy policy's 161 choices were reproduced. The existing review auditor
flagged a Thunder Dragon zero-copy search while two copies remained and a
Heavy Storm with three own backrow cards and no opposing backrow. These are
concrete follow-up decisions for supervised review, not proof that correcting
them alone would change match outcomes.

The three detailed JSON reports are ignored local artifacts under
`.cache/goat-ai/` named `eval_v23_wikiformat_df_vs_fukuyama_tactical_13040_13047.json`,
`eval_tactical_mirror_wikiformat_df_vs_fukuyama_13040_13047.json`, and
`eval_v23_wikiformat_df_mirror_tactical_13060_13075.json`; their SHA-256 values
are respectively `1a5b37374fb2fa338796f206085cab1adff0876aea69a3cdacaa90e7e1c35bd3`,
`5fdaaebb4a43bd451451a3cde512d1ecd89c5dfa08d9d892fad7e3aa74f6ba7f`,
and `bc10df1b857c46aaa6aff8464bb7fad8b0866031cb876b8162aba9e2b6efea95`.
Reproduce the policy mirror with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --engine experimental --opponent tactical \
  --matchup examples/decks/dimension_fusion_turbo_wikiformat_reference.ydk \
    examples/decks/dimension_fusion_turbo_wikiformat_reference.ydk \
  --seed 13060 --seeds 16 --max-decisions 3000 \
  --require-unseen-main-decks --workers 2 \
  --output .cache/goat-ai/eval_v23_wikiformat_df_mirror_tactical_13060_13075.json
```

To test whether targeted imitation transfers across Dimension Fusion lists,
eight policy-versus-Tactical duels on the WikiFormat composition (seeds
13100–13103, both policy seats) were recorded, fully replay-verified, and
visibility-audited. They contained 3,057 decisions. Tactical v14 labeled
501 multi-option policy decisions, and a warm-start feature-v23 clone fit
those labels for one epoch with batch size 16, batched forward, learning rate
`3e-5`, and seed 42. The batch manifest SHA-256 is
`f2d9569c6314589fa7db9123fcaddfe0c5eff4140327796b40315593ba8216a8`;
the experimental child checkpoint SHA-256 is
`0664997efc1e4f859ec84de587984fd108f83df4bf4cd22fbc99498920c1082f`.

The separate GoatFormat guide Dimension Fusion Main Deck was excluded from
both parent and child training compositions. In a 32-game mirror against
Tactical on seeds 13140–13155, the unchanged parent scored **5–26–1** and
the child **7–25–0**. A direct 64-game child-versus-parent mirror on fresh
seeds 13160–13191 scored **30–34** for the child, with a paired bootstrap
score interval of **35.9–57.8%**. The small Tactical-score change and direct
match do not establish a strength gain. The child remains an ignored research
checkpoint; the reference is unchanged. The three evaluation report SHA-256
values are `fd31524acd505dc69d9ce716776b12c0bb4062f22b9780cd225c770b81877e9e`,
`7e4b83f195bd5a5b0ab4d3cf25f7b564f973bfa99ef4e2cbce51f21f0d9fd5cf`,
and `64b3353990a0d5d546240b6acffe1b184d9a0d24bb6398c1f80238f7b3259817`.
This is one small single-archetype training run, and says nothing yet about
performance on other deck families. It indicates that simply labeling a few
hundred policy-visited choices with the existing Tactical teacher is
insufficient evidence to promote a new policy.

The deck fixture and prior hash-cache correction passed the Python suite:
296 tests passed, with 696 native-gated skips. Six focused native-enabled
deck/fingerprint tests passed. The full native suite was not rerun.

## On-policy teacher diversity pilot (27 October 2026)

The previous 64-duel, four-deck Tactical-v14 labeling collection contained
4,679 multi-option labels but regressed on a held-out Dimension Fusion family.
I combined those 64 verified trajectories with eight already recorded
policy-versus-Tactical duels on the independently sourced WikiFormat Dimension
Fusion list. The same unchanged feature-v23 parent, disagreement weight 4,
two epochs, minibatch size 16, learning rate `1e-4`, and seed 37 produced a
5,180-label clone (1,196 policy/teacher disagreements). All 72 source duels
were replay-verified and visibility-audited during training; these are
**synthetic teacher labels**, not human demonstrations. The experimental
checkpoint SHA-256 is
`2227a1f708784ad4df3e2f2ab895955c888377548920e11e4d3311211de893d4`.
Training took 30.36 seconds, including 10.36 seconds of verification and
8.25 seconds of fitting.

Fresh seeds 13200–13207 evaluated three matchups with both deck assignments
and both policy seats: GoatFormat guide Dimension Fusion/Bazoo Return,
Insids Chaos Control/Bazoo Return, and Lolmarcus/Michael Goat Control. Every
evaluation Main Deck composition and seed was excluded from the clone's
training set. The mixed clone split **46–45–5** directly against its unchanged
parent over 96 games (paired score interval **43.8%–57.3%**). Against Tactical
on that same schedule it scored **26–70**, versus **19–77** for the parent and
**18–76–2** for the prior four-deck clone. The mixed-minus-parent paired
score difference was **+7.3 points** (95% interval **−1.0 to +15.6**); the
mixed-minus-prior-clone difference was **+7.3 points** (95% interval **+0.5
to +13.5**). On fresh seeds 13208–13215, the mixed clone scored **53–40–3**
directly against that prior clone over 96 games, with a paired score interval
of **47.9%–65.1%**. These exploratory comparisons suggested some transfer from
the added Dimension Fusion labels, but neither a direct parent gain nor a
strong result against Tactical was established.

To test broader deck diversity, eight more policy-versus-Tactical duels on
Riclar Chaos Turbo/Matt Peddle Goat Control, seeds 13300–13303 in both policy
seats, completed with **3,734 replay-verified and visibility-audited
decisions**. The collection manifest SHA-256 is
`8015354185f482d9ff90321620dd91b6106250c8bd17a153ac1b9f6fe441fc6f`.
Adding these to the same training schedule produced a 5,749-label clone
(1,359 disagreements) in 33.69 seconds; checkpoint SHA-256
`bbdcef649c1f01212fdf52bf49d08654c20b068a70acb9c018df0585b65b270c`.
The held-out Insids, GoatFormat Dimension Fusion, Lolmarcus, Michael, and
Bazoo Return Main Decks remained outside this training set.

On fresh seeds 13340–13347, this three-family clone split **46–48–2**
directly against the mixed clone in 96 games (paired score interval
**41.7%–55.2%**). Against Tactical it scored **28–67–1** versus the mixed
clone's **21–75** on that schedule. On the earlier seeds 13200–13207,
however, it scored **24–72** versus the mixed clone's **26–70**. Combined
across 192 paired Tactical games, the three-family clone scored **52–139–1**
versus **47–145** for the mixed clone: a **+2.9-point** paired score difference
with a 95% interval of **−2.1 to +8.1 points**. More synthetic labels did not
demonstrate a reproducible competitive gain. Neither child is promoted, and
no self-play gain is claimed. The unchanged v23 parent remains the reference.

The ignored training summaries and key evaluation reports are below. All
report SHA-256 values bind these numbers to the local artifacts:

| Artifact under `.cache/goat-ai/` | SHA-256 |
| --- | --- |
| `fv23_on_policy_teacher_plus_wikiformat_df_disagreement4.train.json` | `d3a8117adfea639dd3b7d52a3b5269e72213f97bf138fc187936c19ab0431e57` |
| `fv23_on_policy_teacher_diverse_threefamily_disagreement4.train.json` | `8c0008b0c8019080742b7f8f9255f2dde9e933cf449af6bc512276d48ca98c0f` |
| `fv23_mixed_on_policy_vs_parent_13200_13207.json` | `0e3c0bd4fa225a04936c0fd6d5f9bf963de573befb1f5dbb3c6c0943c0c552d4` |
| `fv23_mixed_vs_old_on_policy_13208_13215.json` | `3d5aca5ab6cefdac9ac76bba7e867ab3a29be9b6bb85985bb5dc5cef323637b4` |
| `fv23_diverse_vs_mixed_on_policy_13340_13347.json` | `ebac68af1e8a97744449e6a91f6f896dbb01819c42bd71e33d37d4776b80f77d` |
| `fv23_mixed_on_policy_vs_tactical_13200_13207.json` | `ce99c9636a611c37b647677a812c708c95663939e8d49236639a3c484818407e` |
| `fv23_old_on_policy_vs_tactical_mixed_eval_13200_13207.json` | `6fbd76c464bfea8ab1caf70d6ea04f3664f4770b68ec9ace7eeb6844420960d3` |
| `fv23_parent_vs_tactical_mixed_eval_13200_13207.json` | `5eec2b2beba051533644cc9bc13555d631a77aac1795f43f1abb373f2c81d4a6` |
| `fv23_diverse_vs_tactical_13200_13207.json` | `75639604f269319a1ea2db35ad9f0e1f3f319e7816a994c80a012ce130366c65` |
| `fv23_diverse_vs_tactical_13340_13347.json` | `75139f9fed0afea9bd1b19d0990e0b75402a6cfa6b23730bb0699f783ca14f56` |
| `fv23_mixed_vs_tactical_13340_13347.json` | `2f1e46fb3fe4379f0289a1aa5e47c7c16569dc61f532571d6d85f2f44cda48df` |

The Chaos Turbo/Matt Peddle addition can be collected from the pinned parent
checkpoint after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --matchup examples/decks/chaos_turbo_riclar_2020.ydk \
            examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
  --opponent tactical --seed 13300 --seeds 4 --workers 4 \
  --max-decisions 3000 \
  --output-dir .cache/goat-ai/on_policy_chaos_turbo_matt_13300_13303
```

The current code reproduces the two-family training with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/train_behavioral_clone.py \
  .cache/goat-ai/policy_vs_tactical_12100_12115/matchup*.json \
  .cache/goat-ai/on_policy_wikiformat_df_13100_13103/matchup*.json \
  --engine experimental --on-policy-teacher tactical_v14 \
  --on-policy-disagreement-weight 4 --feature-version 23 --width 32 \
  --epochs 2 --batch-size 16 --batched-forward --verification-workers 4 \
  --learning-rate 0.0001 --seed 37 \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/fv23_on_policy_teacher_plus_wikiformat_df_disagreement4.pt
```

For the three-family child, add
`.cache/goat-ai/on_policy_chaos_turbo_matt_13300_13303/matchup*.json` to the
trajectory arguments and change the output path to its checkpoint name above.
The saved reports record the full held-out deck schedules, seeds, hashes, and
seat results. For example, rerun the first mixed-versus-parent schedule with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/evaluate_policy.py \
  .cache/goat-ai/fv23_on_policy_teacher_plus_wikiformat_df_disagreement4.pt \
  --engine experimental \
  --opponent-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --matchup examples/decks/dimension_fusion_turbo_goatformat_guide.ydk \
            examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
            examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 13200 --seeds 8 --workers 4 \
  --output .cache/goat-ai/fv23_mixed_on_policy_vs_parent_13200_13207.json
```

This experiment supports a data-diversity hypothesis for future
work, while showing that another small dose of the same Tactical teacher is
insufficient to close M4. A different learning signal, stronger authorized
human decisions, or value learning needs separate testing.

## Chaos Return versus Warrior protocol sweep

Simon “Dingosig” Guinhut's [first-place 2022 Worlds Chaos Return list](https://formatlibrary.com/decks/6540) was downloaded as a public YDK and converted to pinned GOAT/pre-errata IDs in [`chaos_return_dingosig_worlds_2022.ydk`](../examples/decks/chaos_return_dingosig_worlds_2022.ydk). The source has 40 Main, 15 Extra, and 15 Side cards; all three sections pass the pinned GOAT legality gate. Two seat-swapped full duels against the sourced Warrior list serialize and replay-verify exact trajectories.

A random-agent schedule on seeds 1–10, with each deck in both seats, completed **20/20 terminal duels** under the 3,000-decision cap. It recorded 14,331 decisions, or 716.55 per duel; the longest took 1,281 decisions. Chaos Return's assigned RandomAgent won 5, lost 13, and drew 2. These outcomes measure protocol coverage, not relative deck strength. On the pinned Linux x86_64 assets with one worker, the tournament took 12.453 seconds, measuring 1.606 duels and 1,151 decisions per second. Generated results remain outside Git.

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai python scripts/evaluate_native.py \
  --engine experimental \
  --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk \
    examples/decks/warrior_montague_clash.ydk \
  --agent-a random --agent-b random --seed 1 --seeds 10 \
  --max-decisions 3000 --output artifacts/chaos_return_warrior_random_1_10.json
```

This protocol run alone does not establish that Return from the Different Dimension activated. Separate [source-backed native fixtures](goat_rules.md) now cover a basic Chaos-cost revival, End Phase rebanish, and the historical Book of Moon exception; other Return interactions remain unaudited.

## Chaos Control versus Chaos Turbo protocol sweep

Dmitry “InsiDS” Summovsky’s [third-place 2022 Worlds Chaos Control list](https://www.formatlibrary.com/decks/6548) was downloaded as a public YDK and converted to the pinned GOAT/pre-errata IDs in [`chaos_control_insids_worlds_2022.ydk`](../examples/decks/chaos_control_insids_worlds_2022.ydk). The source has 40 Main, 15 Extra, and 15 Side cards; all three sections pass the pinned GOAT legality gate. Two seat-swapped full duels against the sourced Chaos Turbo list serialize and replay-verify exact trajectories.

A random-agent schedule on seeds 1–2, with each deck in both seats, completed **4/4 terminal duels** under the 3,000-decision cap. It recorded 4,224 decisions, or 1,056 per duel. Chaos Control’s assigned RandomAgent won 2/4, both in seat 0; this small result measures protocol coverage and does not estimate relative deck strength. On the pinned Linux x86_64 assets with one worker, the tournament took 4.293 seconds, measuring 0.932 duels and 984 decisions per second. Generated results remain outside Git.

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai python scripts/evaluate_native.py \
  --engine experimental \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
    examples/decks/chaos_turbo_riclar_2020.ydk \
  --agent-a random --agent-b random --seed 1 --seeds 2 \
  --max-decisions 3000 --output artifacts/chaos_control_chaos_turbo_random_1_2.json
```

## Warrior versus Chaos protocol sweep

Sean Montague's [fourth-place Warrior list](https://www.goatformat.com/warrior.html) was transcribed into [`warrior_montague_clash.ydk`](../examples/decks/warrior_montague_clash.ydk), using GOAT and pre-errata IDs from the pinned whitelist. The source omits an Extra Deck, so this fixture leaves it empty. The 40-card Main Deck passes the pinned legality gate. Two seat-swapped Warrior versus sourced Chaos Turbo duels serialize and replay-verify complete trajectories.

With both agents selecting uniformly at random, seeds 1–10 in both seats completed **20/20 terminal duels** within 3,000 decisions. The schedule recorded 18,938 decisions, averaging 946.9 per duel. Warrior's assigned RandomAgent won 8/20; this is an engine protocol check, not an archetype-strength estimate. On the pinned Linux x86_64 assets, the sequential tournament took 16.42 seconds, or 1.22 duels and 1,153 decisions per second. The generated report is ignored at `artifacts/warrior_chaos_random_1_10.json`.

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai python scripts/evaluate_native.py \
  --engine experimental \
  --matchup examples/decks/warrior_montague_clash.ydk \
    examples/decks/chaos_turbo_riclar_2020.ydk \
  --agent-a random --agent-b random --seed 1 --seeds 10 \
  --max-decisions 3000 --output artifacts/warrior_chaos_random_1_10.json
```

Reinforcement searches and other Warrior-specific card interactions still need source-backed ruling fixtures. The random games do not establish that every possible legal choice or hidden-information boundary was exercised.

`scripts/evaluate_native.py` runs paired seeds: candidate A plays each matchup once in each seat, always with its assigned deck. It creates fresh agents and native environments for each game. A draw counts as half a point in `score_rate` and is excluded from `decisive_win_rate`. The report gives a deterministic 95% percentile bootstrap interval for the score rate, resampling whole matchup/seed pairs, plus a descriptive Wilson interval for decisive games. The Wilson interval treats games as independent and should not be used alone for this paired schedule. Results include deck and asset SHA-256 fingerprints, individual game outcomes, decisions, and seat/matchup summaries.

Reproduce the first report after [native setup](native_setup.md):

```bash
python scripts/evaluate_native.py --agent-a heuristic --agent-b random \
  --seed 42 --seeds 10 --output artifacts/heuristic_vs_random_10seeds.json
```

| Date | Core | Matchup | Seeds | Heuristic wins | Losses | Draws | Score rate, paired 95% bootstrap |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 2026-10-24 | `baa3881d0bae48e9994f915f5c931be53c1ba8ef` | vanilla_probe vs vanilla_reverse | 42–51, both seats | 17 | 3 | 0 | 85.0%, 70.0–100.0% |

The heuristic won 9/10 games in seat 0 and 8/10 in seat 1. Mean game length was 568.15 decisions. The run used Linux 6.8.0-146-generic x86_64 and the pinned assets from `setup_native.py`. The bootstrap interval describes variation among these ten seeds; with few seeds or uniform outcomes it can be too narrow. This is a baseline comparison on one normal-monster fixture pairing, with no held-out decks or human opponents. It does not establish general GOAT playing strength. The native integration test reruns a separate four-game random-versus-random schedule and compares individual outcomes for reproducibility.

## Spawned-process reproducibility

The following two commands run the same eight-game random-agent schedule:

```bash
python scripts/evaluate_native.py --agent-a random --agent-b random --seed 42 --seeds 4 --workers 1 --output artifacts/parallel_eval_workers1.json
python scripts/evaluate_native.py --agent-a random --agent-b random --seed 42 --seeds 4 --workers 2 --output artifacts/parallel_eval_workers2.json
```

On 2026-10-24, the pinned native assets on Linux
6.8.0-146-generic x86_64 produced identical ordered game results and summary
with either worker count: 10,728 total decisions, four wins and four losses
for candidate A. A native test separately compares a four-game sequential
schedule with two spawned workers. This proves reproducibility for these
fixtures and seeds, not for all cards or platforms.

## First policy checkpoint: held-out seed baseline

An initial 16-wide policy was fit for one epoch to 1,368 decisions from a single random-versus-random vanilla-fixture trajectory (training seed 42; replay verified against the pinned native core). The mean training cross-entropy was 0.5308. This source is random self-play, so the checkpoint is a software and evaluation baseline, not a skilled-human imitation model. Its SHA-256 is `738629ed63d9c6782200c5c18c8dae0594bcd690515204036d3edf4b5829fb21`; the generated checkpoint and trajectory are ignored artifacts.

With held-out seeds 43–46 and the same two fixture decks, the checkpoint lost all eight paired, seat-swapped duels against `RandomAgent`: 0 wins, 8 losses, 0 draws. It lost 4/4 in each seat. Mean game length was 411.875 decisions. The descriptive Wilson interval for its decisive win rate was 0–32.4%; the paired bootstrap score interval collapsed to 0–0 on this four-seed sample, which should not be interpreted as a population bound. All eight games reached terminal states within the 5,000-decision cap. On Linux 6.8.0-146-generic x86_64 with the pinned core, the sequential tournament portion took 3.440 seconds for 8 games and 3,295 decisions. Two spawned workers produced the same ordered outcomes and summary in 4.062 seconds. This small run provides no evidence of playing strength or speedup from extra workers.

Reproduce after [native setup](native_setup.md) with:

```bash
python examples/play_vanilla.py --seed 42 --trajectory replays/policy_smoke_42.json
python scripts/train_behavioral_clone.py replays/policy_smoke_42.json \
  --output checkpoints/policy_smoke_eval_42.pt --epochs 1 --width 16 --seed 42
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/policy_smoke_eval_42.pt \
  --seed 43 --seeds 4 --opponent random \
  --output artifacts/policy_smoke_vs_random_43_46.json
```

The evaluator records the checkpoint hash, training-game seeds and deck hashes, evaluation seeds, current core/database/list hashes, deck hashes, individual games, and intervals. It refuses a training/evaluation seed overlap. Future reports need authorized human demonstrations, held-out deck families and opponents, and a policy improvement algorithm before any competitive claim.

## First terminal-reward self-play experiment

Starting from the random-imitation checkpoint above, an initial score-function learner played 16 native duels with training seeds 100–115. It alternated seats, sampled its actions, and faced 11 frozen historical policy snapshots and 5 RandomAgent opponents. It won 8 games and lost 8; 3,023 learner decisions contributed to updates. Two recorded trajectories were independently replayed against the pinned native assets, verifying 1,147 and 1,260 decisions. The child checkpoint SHA-256 is `7c3a17fe24bfcfb90285188de09f5561ed712b1e4e8315e1c79426893d9de42b`; its training-game entries include deck, rules-profile, and loaded-asset fingerprints.

On fresh seeds 200–207, the parent and child were each evaluated in both seats against RandomAgent on the same vanilla fixture decks. **Both lost all 16 games.** The parent's mean game length was 369.0625 decisions and the child's was 369.3125. Both decisive-win Wilson intervals were 0–19.4%; the eight-pair bootstrap interval is not a meaningful strength bound when all scores are zero. A direct action audit on seed 200 showed both greedy policies repeatedly chose `end_phase` in Main Phase 1 while Normal Summons were legal. The sparse self-play update did not overcome that behavior in this 16-game budget. Increasing the game count without changing the data or learning setup is not yet justified.

Reproduce the training and paired evaluation after generating the parent checkpoint with the commands above:

```bash
OMP_NUM_THREADS=1 python scripts/train_self_play.py checkpoints/policy_smoke_eval_42.pt \
  --output checkpoints/policy_selfplay_100_115.pt --seed 100 --games 16 \
  --snapshot-every 4 --historical-probability 0.75 \
  --record-dir replays/selfplay_100_115
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/policy_smoke_eval_42.pt \
  --seed 200 --seeds 8 --output artifacts/parent_vs_random_200_207.json
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/policy_selfplay_100_115.pt \
  --seed 200 --seeds 8 --output artifacts/selfplay_vs_random_200_207.json
```

The model and data remain a software baseline, not a strength result. The next experiment should supply stronger authorized or heuristic demonstrations before RL, then compare updates on unseen decks and opponents.

## Seat-labeled heuristic imitation baseline

Eight native vanilla-fixture duels were recorded with HeuristicAgent against RandomAgent at seeds 1000–1003, once per seat. The teacher won 7/8. Full replay verification covered 4,429 decisions; `demonstrator_seat` filtering kept 2,407 teacher decisions for behavioral cloning. A width-32 policy trained for three epochs at learning rate 0.001, with mean training cross-entropies 0.0958, 0.00208, and 0.000324. The checkpoint SHA-256 is `be2567d206e2a53ab41ad1733595bc1904ac82bd0cf00aaf72980a67f081a993`. On an Intel Core i7-10700K CPU with PyTorch 2.5.1+cpu and `OMP_NUM_THREADS=1`, a repeat of the full replay-verification plus training command took 26.72 seconds, with 26.26 user CPU seconds and 332,060 KB peak RSS. The repeated checkpoint had the same hash.

On held-out seeds 2000–2007 and the vanilla fixture pair, policy inference version 2 won **15/16 against RandomAgent** (paired 95% bootstrap score interval 81.25–100%) and **9/16 against HeuristicAgent** (31.25–81.25%). Both schedules swapped the candidate between seats. The latter interval includes 50%, so this sample does not establish superiority over its heuristic teacher.

The policy had never trained on the separate synthetic control and Chaos probe decks. With the experimental adapter, it completed both candidate deck roles against RandomAgent on held-out seeds 3000–3003: **7/8** using the control probe, **5/8** using the Chaos probe, and **12/16** combined (paired bootstrap score interval 50–93.75%). Before the generic inference version 2 liveness guard, these runs hit the 5,000-decision cap by repeatedly selecting and unselecting a target or cancelling and restarting a Special Summon. The guard uses only visible legal actions and the agent's previous choice; it is part of the measured agent. The experimental adapter's historical card behavior and complete hidden-information boundary remain unaudited, so these cross-deck results are protocol and baseline evidence, not a GOAT-correct competitive evaluation.

Reproduce the versioned measurements after collecting and training as in [the ML notes](ml.md):

```bash
python scripts/evaluate_policy.py checkpoints/heuristic_bc_1000_1003.pt \
  --seed 2000 --seeds 8 --opponent random
python scripts/evaluate_policy.py checkpoints/heuristic_bc_1000_1003.pt \
  --seed 2000 --seeds 8 --opponent heuristic
python scripts/evaluate_policy.py checkpoints/heuristic_bc_1000_1003.pt \
  --engine experimental \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk \
  --matchup examples/decks/chaos_probe.ydk examples/decks/control_probe.ydk \
  --seed 3000 --seeds 4 --opponent random
```

The next strength gate needs authorized skilled-human data and larger held-out samples across multiple audited deck families and opponents. The current policy is a useful baseline, not evidence of superhuman play.

## Self-play from the heuristic imitation parent

The heuristic-imitation checkpoint above was used as the parent for two separate native snapshot-pool policy-gradient runs on the vanilla fixture decks. Both used the same pinned assets and `OMP_NUM_THREADS=1`; generated checkpoints and trajectories remain ignored. A default 16-game run on seeds 4000–4015 won 11/16 training games, recorded 1,419 learner decisions, and took 25.27 seconds wall time (24.61 user CPU seconds, 339,204 KB peak RSS). Its child SHA-256 is `f848804cd5afeb45c3e2ec96903b80bdf5d02c389ecb4f93c8cdba3bf120e687`. On held-out seeds 5000–5015, that child won 21/32 against its parent and 21/32 against HeuristicAgent. The parent also won 21/32 against HeuristicAgent on the same schedule; all three game-outcome sequences were identical. On 581 decision points from four recorded training duels with more than one legal action, parent, child, and heuristic selected the same action. The apparent 21/32 head-to-head result therefore does **not** demonstrate a learned improvement; seat and deck effects can explain it.

An exploratory 32-game run from the same parent used seeds 4200–4231, learning rate 0.001, and entropy coefficient 0.01. It won 23/32 training games, recorded 2,581 learner decisions, and took 34.15 seconds wall time (33.17 user CPU seconds, 328,140 KB peak RSS). Its child SHA-256 is `b49bf53ea87c7a8ac1c894a261bce84204210cea61b4f1fd96c0d813a84c2dd8`. On separate held-out seeds 6000–6015, the child won 20/32 against its parent and 20/32 against HeuristicAgent, while the parent also won 20/32 against HeuristicAgent. All three game-outcome sequences again matched, and the exploratory child disagreed with the parent on none of the same 581 sampled decisions. The paired bootstrap score interval for each 20/32 schedule was 53.125–75%. These experiments do not support an RL strength gain.

The evaluator now accepts `--opponent-checkpoint` and records both checkpoint hashes, with training-seed overlap rejected for each checkpoint. Reproduce the direct comparison after training:

```bash
OMP_NUM_THREADS=1 python scripts/train_self_play.py checkpoints/heuristic_bc_1000_1003.pt \
  --output checkpoints/heuristic_rl_4000_4015.pt --seed 4000 --games 16 \
  --record-dir replays/heuristic_rl_4000_4015
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/heuristic_rl_4000_4015.pt \
  --opponent-checkpoint checkpoints/heuristic_bc_1000_1003.pt \
  --seed 5000 --seeds 16
```

The next RL experiment needs a mechanism that changes the greedy policy and a paired parent-versus-child comparison on held-out, audited decks. More episodes of this sparse terminal-reward update alone are not justified by these observations.

## Target-aware policy feature experiment

Feature version 2 keeps a separate target-presence mask and embeds the visible controller, zone, and slot of every card in a multi-card action. A contract test shows that two actions with the same number of hidden targets but different slot pairs receive different logits, while reversing the target order leaves the score unchanged. Version-1 checkpoints still load with their original encoder: rerunning the prior 16-game vanilla RandomAgent schedule produced identical game records and summary to its saved report.

The same eight verified heuristic demonstration duels were retrained for three epochs with width 32 and seed 17. The version-2 checkpoint SHA-256 is `b53fed2c70de0f5c57993388f4964c89b896401bfdc5ec753a82df48e100c4ec`; epoch losses were 0.09548, 0.001964, and 0.000288. Training, including full replay verification, took 29.03 seconds wall time, 28.61 user CPU seconds, and 335,972 KB peak RSS on the same Intel Core i7-10700K and PyTorch 2.5.1+cpu with `OMP_NUM_THREADS=1`.

On held-out vanilla seeds 2000–2007, it won **15/16 versus RandomAgent** and **9/16 versus HeuristicAgent**, exactly matching the version-1 outcome counts. On the experimental control/Chaos schedules at seeds 3000–3003, it won **14/16 versus RandomAgent** (paired score interval 68.75–100%), compared with 12/16 for version 1. A direct, seat-swapped version-2 versus version-1 comparison on a separate experimental seed range 3100–3107 won **17/32** (paired score interval 34.375–71.875%): 13/16 with the control probe and 4/16 with the Chaos probe. The interval includes 50%, and these decks lack a complete historical rules and visibility audit. The new features remove one representational ambiguity; these results do not establish stronger play.

## Own-Deck feature check on two experimental matchups

On 2026-10-24, a version-5 policy was trained for one epoch at width 16 and seed 17 on the 1,126 replay-verified decisions from the schema-v11 Ground Collapse fixture (`examples/record_ground_collapse.py`, training seed 3). Its teacher decisions are mostly random. The version-5 checkpoint SHA-256 is `8934273db109672bf9b77bc369a3de4635e9fe7979061409d9d02110500cdbd2`. A version-4 checkpoint trained from the earlier schema-v9 recording has SHA-256 `9e1a505d320190072ca2aec1fe60a3efecdf90bcebc30b5280b06691b93036fd`. Retraining version 4 from the current schema-v11 recording with the new `--feature-version 4` option produced **identical model tensors and loss** (0.5452325494), although the file hash changed to `3720c90e6f454b70333e19452357caf9083439459ae8a034507d53b22aae42ed` because the recorded trajectory metadata changed. Version 5's one-epoch mean decision loss was 0.5429644987.

The checkpoints were evaluated on held-out seeds 60–63, both seat assignments, with two matchups: Ground Collapse versus the vanilla fixture and control versus Chaos. All games used the experimental adapter and the pinned GOAT-mode core. The measured schedules used the earlier tensor-equivalent version-4 checkpoint.

| Candidate | Opponent | Wins | Losses | Paired score 95% bootstrap | Ground/vanilla | Control/Chaos |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Version 4 | RandomAgent | 14 | 2 | 68.75–100% | 6/8 | 8/8 |
| Version 5 | RandomAgent | 11 | 5 | 56.25–87.5% | 4/8 | 7/8 |
| Version 5 | Version 4 | 7 | 9 | 18.75–68.75% | 2/8 | 5/8 |

Version 4 won 6/8 in the first seat and 8/8 in the second against RandomAgent. Version 5 won 4/8 and 7/8 respectively; against version 4 it won 2/8 and 5/8. These four-seed samples are small, the experimental decks are not fully audited for historical rules or visibility, and the direct interval includes 50%. The model architectures and random initialization differ, so the comparison does not isolate a causal Deck-feature effect. The measurements provide **no evidence of a playing-strength gain** from version 5. On the Intel Core i7-10700K, Linux 6.8.0-146-generic x86_64, and `OMP_NUM_THREADS=1`, the three tournament calls took 20.52, 27.60, and 27.94 seconds respectively; those one-run times are not throughput estimates.

Reproduce the training and schedules locally after [native setup](native_setup.md):

```bash
python examples/record_ground_collapse.py
OMP_NUM_THREADS=1 python scripts/train_behavioral_clone.py \
  replays/ground_collapse_3.json --engine experimental --feature-version 4 \
  --output checkpoints/ground_v4.pt --epochs 1 --width 16 --seed 17
OMP_NUM_THREADS=1 python scripts/train_behavioral_clone.py \
  replays/ground_collapse_3.json --engine experimental --feature-version 5 \
  --output checkpoints/ground_v5.pt --epochs 1 --width 16 --seed 17
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/ground_v4.pt \
  --engine experimental --seed 60 --seeds 4 \
  --matchup examples/decks/ground_collapse_probe.ydk examples/decks/vanilla_probe.ydk \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/ground_v5.pt \
  --engine experimental --seed 60 --seeds 4 \
  --matchup examples/decks/ground_collapse_probe.ydk examples/decks/vanilla_probe.ydk \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/ground_v5.pt \
  --opponent-checkpoint checkpoints/ground_v4.pt --engine experimental \
  --seed 60 --seeds 4 \
  --matchup examples/decks/ground_collapse_probe.ydk examples/decks/vanilla_probe.ydk \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk
```

## Sourced Goat Control and Chaos Turbo baseline

On 2026-10-24, the experimental GOAT-mode adapter completed a paired baseline tournament using the sourced [Goat Control](../examples/decks/goat_control_lolmarcus_2020.ydk) and [Chaos Turbo](../examples/decks/chaos_turbo_riclar_2020.ydk) Main Decks. Each deck was assigned to HeuristicAgent once per matchup, and each seed was played with the agent in both seats. Seeds 7000–7007 were unused by the documented training runs. The opponent was RandomAgent. The pinned core was `baa3881d0bae48e9994f915f5c931be53c1ba8ef` on Linux 6.8.0-146-generic x86_64. Deck and native asset SHA-256 hashes, individual game outcomes, and timing are in the ignored report `artifacts/heuristic_vs_random_sourced_7000_7007.json`, recreated by:

```bash
python scripts/evaluate_native.py --engine experimental \
  --agent-a heuristic --agent-b random \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/goat_control_lolmarcus_2020.ydk \
  --seed 7000 --seeds 8 --max-decisions 3000 \
  --output artifacts/heuristic_vs_random_sourced_7000_7007.json
```

| Candidate deck | Heuristic wins | Losses | Paired score 95% bootstrap |
| --- | ---: | ---: | ---: |
| Goat Control | 11/16 | 5/16 | 43.75–93.75% |
| Chaos Turbo | 13/16 | 3/16 | 62.5–93.75% |
| Both | 24/32 | 8/32 | 59.375–87.5% |

The heuristic won 15/16 in seat 0 and 9/16 in seat 1. Mean duel length was 865.28 decisions. The sequential tournament took 22.287 seconds for 32 duels and 27,689 decisions, or 1.436 duels and 1,242 decisions per wall-clock second in this one run. The strong seat split, small sample, weak opponent, unaudited full-card scripts, and partially reconstructed Goat Control Extra Deck limit interpretation. This is a reproducible baseline for future policies on the two high-play decks, not a competitive-strength claim.

## Heuristic imitation on sourced GOAT decks

A controlled behavioral-cloning run used 16 real native duels at seeds 8000–8003: four seeds with each deck assignment, and the heuristic teacher in each seat. The teacher won 9/16 against RandomAgent. The 16 complete trajectories contain 13,428 decisions; replay verification passed before training, and `demonstrator_seat` filtering selected 6,999 heuristic decisions. Feature-version-8, width-32 training ran for three epochs with seed 17 and learning rate 0.001. Mean decision losses were 0.09133, 0.03901, and 0.02767. With PyTorch CPU and `OMP_NUM_THREADS=1`, the verification-plus-training command took 102.47 seconds wall time, 101.53 user CPU seconds, and 565,320 KB peak RSS. The ignored checkpoint `checkpoints/heuristic_bc_sourced_8000_8003.pt` has SHA-256 `b8c51e5e129175a35eb142c7dc48d81056a2f948ee4d3ffc3af893cc36185992`.

On fresh seeds 9000–9007, both sourced deck assignments and both seats were tested under the experimental adapter:

| Candidate versus opponent | Wins | Losses | Paired score 95% bootstrap |
| --- | ---: | ---: | ---: |
| Sourced imitation versus RandomAgent | 18/32 | 14/32 | 37.5–75% |
| Sourced imitation versus HeuristicAgent | 21/32 | 11/32 | 43.75–84.375% |
| Sourced imitation versus vanilla-trained version-2 checkpoint | 16/32 | 16/32 | 31.25–68.75% |
| HeuristicAgent versus RandomAgent | 23/32 | 9/32 | 56.25–87.5% |

The direct checkpoint comparison shows no gain. The sourced policy won 15/16 when assigned Goat Control but only 6/16 with Chaos Turbo against the heuristic, so the aggregate 21/32 masks substantial deck dependence. The parent and child also use different feature versions, so this is an operational comparison rather than a causal estimate of the added training data.

### Held-out Warrior deck check

The sourced imitation checkpoint above trained on Goat Control and Chaos Turbo, never the sourced Warrior list. On seeds 9200–9207, `ExperimentalOcgcoreEngine` completed 16 Warrior-versus-Chaos duels for each opponent, swapping the Warrior candidate between seats. The checkpoint won **15/16 versus RandomAgent** (paired 95% bootstrap score interval 81.25–100%) and **14/16 versus HeuristicAgent** (68.75–100%). The latter split was 6/8 in the first seat and 8/8 in the second. A same-seed, same-deck-assignment control with HeuristicAgent on both sides won **13/16** for Warrior (62.5–93.75%). That control shows a large deck-assignment effect; the checkpoint's 14/16 is insufficient evidence of improvement over its teacher or broad deck generalization. No games reached the 3,000-decision cap. Wall times for these separate sequential runs were 10.68, 10.98, and 4.24 seconds respectively; these are measurements of these runs, not general throughput estimates. Native GOAT rulings for these whole decks remain unaudited.

Reproduce with the pinned native assets and checkpoint described above:

```sh
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/heuristic_bc_sourced_8000_8003.pt --engine experimental --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_turbo_riclar_2020.ydk --seed 9200 --seeds 8 --max-decisions 3000 --opponent random --output artifacts/warrior_policy_vs_random_9200_9207.json
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/heuristic_bc_sourced_8000_8003.pt --engine experimental --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_turbo_riclar_2020.ydk --seed 9200 --seeds 8 --max-decisions 3000 --opponent heuristic --output artifacts/warrior_policy_vs_heuristic_9200_9207.json
OMP_NUM_THREADS=1 python scripts/evaluate_native.py --engine experimental --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_turbo_riclar_2020.ydk --seed 9200 --seeds 8 --max-decisions 3000 --agent-a heuristic --agent-b heuristic --output artifacts/warrior_heuristic_vs_heuristic_9200_9207.json
```

A separate off-policy audit used eight newly collected, replay-verified heuristic duels at seeds 9100–9101, totaling 5,500 full-duel decisions and 2,860 teacher decisions. Of those, 891 had more than one legal action. The vanilla-trained version-2 checkpoint agreed exactly with the teacher on 737/891; the sourced version-8 checkpoint agreed on 859/891. Across all 2,860 decisions, exact agreements were 2,706 and 2,828 respectively, but 1,969 decisions had only one legal action. This improvement in imitation did not translate into a measured competitive gain. The audit follows recorded teacher states, so its agreement rates cannot replace head-to-head duels.

Reproduce after native setup with generated outputs under ignored `replays/`, `checkpoints/`, and `artifacts/`:

```bash
python scripts/collect_heuristic_demos.py --engine experimental \
  --deck-a examples/decks/goat_control_lolmarcus_2020.ydk \
  --deck-b examples/decks/chaos_turbo_riclar_2020.ydk \
  --seed 8000 --seeds 4 --output-dir replays/sourced_heuristic_goat_chaos_8000_8003
python scripts/collect_heuristic_demos.py --engine experimental \
  --deck-a examples/decks/chaos_turbo_riclar_2020.ydk \
  --deck-b examples/decks/goat_control_lolmarcus_2020.ydk \
  --seed 8000 --seeds 4 --output-dir replays/sourced_heuristic_chaos_goat_8000_8003
OMP_NUM_THREADS=1 python scripts/train_behavioral_clone.py \
  replays/sourced_heuristic_goat_chaos_8000_8003/*.json \
  replays/sourced_heuristic_chaos_goat_8000_8003/*.json \
  --engine experimental --feature-version 8 \
  --output checkpoints/heuristic_bc_sourced_8000_8003.pt \
  --epochs 3 --width 32 --seed 17 --learning-rate 0.001
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/heuristic_bc_sourced_8000_8003.pt \
  --engine experimental --opponent-checkpoint checkpoints/heuristic_bc_v2_1000_1003.pt \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/goat_control_lolmarcus_2020.ydk \
  --seed 9000 --seeds 8 --max-decisions 3000
```

Use the same evaluator command with `--opponent random` or `--opponent heuristic` for the other two policy schedules. Generate audit trajectories with `collect_heuristic_demos.py` at seeds 9100–9101 in separate directories for each deck assignment, then run `scripts/audit_policy_agreement.py` with both `--checkpoint` paths and those trajectory files. The next training experiment needs stronger demonstrations or a learning update that improves decisions across both decks; a lower imitation loss alone is insufficient.

```bash
OMP_NUM_THREADS=1 python scripts/audit_policy_agreement.py --engine experimental \
  --checkpoint checkpoints/heuristic_bc_v2_1000_1003.pt \
  --checkpoint checkpoints/heuristic_bc_sourced_8000_8003.pt \
  replays/sourced_audit_goat_chaos_9100_9101/*.json \
  replays/sourced_audit_chaos_goat_9100_9101/*.json
```

## Balanced sourced-deck self-play experiment

The self-play scheduler previously advanced the matchup and learner seat in lockstep. With two reversed deck assignments, that would train the learner on Goat Control in every game. It now uses both learner seats for a matchup before moving to the next matchup. A contract test covers the four combinations of learner deck and seat.

Starting from the sourced feature-version-8 imitation checkpoint, the initial REINFORCE-style trainer played 16 native duels at seeds 8200–8215 with both sourced deck assignments and the corrected schedule. The learner received exactly four games for each deck/seat combination, won 7/16 training games, and recorded 1,644 decisions with legal alternatives for gradient updates. Opponents were frozen snapshots in 13 games and RandomAgent in 3. The 16 duels had 11,539 total decisions. Four saved trajectories covering every deck/seat combination replay-verified for 874, 925, 615, and 457 decisions. With `OMP_NUM_THREADS=1`, the run took 34.32 seconds wall time, 33.60 user CPU seconds, and 387,572 KB peak RSS. The ignored child checkpoint `checkpoints/heuristic_rl_sourced_8200_8215.pt` has SHA-256 `677deef5c1a3e1b9401d33750ad96f84f5a28028fc1d6d46f9466f1d25aa3806`.

On fresh seeds 8300–8307, both sourced deck assignments and both seats, the child won **17/32 directly against its parent** (paired score interval 34.375–71.875%). It won 10/16 with Goat Control and 7/16 with Chaos Turbo; the first-seat and second-seat splits were 7/16 and 10/16. On the separate replay-verified seed-9100–9101 action audit, both parent and child matched the heuristic on exactly 859/891 decisions with more than one legal action, and 2,828/2,860 total decisions. This 16-game update provides no evidence of a strength gain or a changed greedy policy on the audited states.

Reproduce with:

```bash
OMP_NUM_THREADS=1 python scripts/train_self_play.py checkpoints/heuristic_bc_sourced_8000_8003.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/goat_control_lolmarcus_2020.ydk \
  --seed 8200 --games 16 --max-decisions 3000 \
  --record-dir replays/sourced_selfplay_8200_8215 \
  --output checkpoints/heuristic_rl_sourced_8200_8215.pt
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/heuristic_rl_sourced_8200_8215.pt \
  --engine experimental --opponent-checkpoint checkpoints/heuristic_bc_sourced_8000_8003.pt \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/goat_control_lolmarcus_2020.ydk \
  --seed 8300 --seeds 8 --max-decisions 3000
```

The terminal-only return supplies little guidance about which decision helped. The next RL experiment needs a stronger policy-update signal or selection method, with a direct held-out comparison against the parent and coverage across decks and seats.

## Sourced-deck random protocol sweep (2026-10-25)

Using the pinned experimental GOAT-mode adapter, two spawned workers played RandomAgent against RandomAgent for seeds 21–30 in both seats for each of three sourced-deck pairings: Goat Control versus Chaos Turbo, Warrior versus Chaos Turbo, and Goat Control versus Warrior. All **60/60 duels** reached terminal within the 3,000-decision cap, with 60,374 decisions total and a maximum of 1,336 in one duel. Mean decisions were 1,099.4, 948.9, and 970.4 respectively in the order listed. The measured tournament wall time was **29.842 s**, or **2.011 duels/s** and **2,023.1 decisions/s** across two workers on Linux 6.8.0 x86_64. The pinned native library SHA-256 was `b2ce880275e07ae2cd5e6f8735e61e651dedaa6b752de471e6c0cf9d66db00eb`; the command records the remaining asset and deck hashes in its ignored JSON output. Goat Control versus Warrior now also has two complete, seat-swapped replay-verified test duels.

```bash
python scripts/evaluate_native.py --engine experimental \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/warrior_montague_clash.ydk \
  --agent-a random --agent-b random --seed 21 --seeds 10 \
  --max-decisions 3000 --workers 2 \
  --output .cache/goat-ai/sourced_random_21_30.json
```

This measures protocol coverage and throughput for these three deck pairings under random choices. It does not establish the historical correctness of every card interaction or either agent's competitive strength. Throughput includes duel startup and Python process scheduling, but not native setup/build time.

## Flip Control protocol sweep

On 2026-10-25, the experimental GOAT-mode adapter completed 40 paired, seat-swapped random-agent duels using the [GoatFormat guide Flip Control list](../examples/decks/flip_control_goatformat_guide.ydk) against the sourced Chaos Turbo and Goat Control fixtures. Seeds 31–40 all reached terminal within 3,000 decisions. The guide omits an Extra Deck, so the Flip Control fixture leaves it empty. Four representative full-duel trajectories additionally serialize and replay-verify in `tests/test_flip_control_duel.py`. The pinned core was `baa3881d0bae48e9994f915f5c931be53c1ba8ef` on Linux 6.8.0-146-generic x86_64.

```bash
python scripts/evaluate_native.py --engine experimental \
  --agent-a random --agent-b random \
  --matchup examples/decks/flip_control_goatformat_guide.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/flip_control_goatformat_guide.ydk examples/decks/goat_control_lolmarcus_2020.ydk \
  --seed 31 --seeds 10 --max-decisions 3000 --workers 2 \
  --output artifacts/random_flip_control_31_40.json
```

| Opponent deck | Flip Control random wins | Losses | Mean decisions |
| --- | ---: | ---: | ---: |
| Chaos Turbo | 4/20 | 16/20 | 895.6 |
| Goat Control | 0/20 | 20/20 | 1015.25 |

The 40 duels took 18.082 seconds in one two-worker run, with 38,217 decisions total, 2.212 duels/second, and 2,113.6 decisions/second. The longest duel used 1,420 decisions. The ignored JSON report includes deck and asset SHA-256 hashes and individual outcomes; the Flip Control deck hash was `faa799b4248d82bcdf05571907ce54849f64d485763f51bab24fd40d8150474c`. These are measured protocol and throughput results. Random choices, incomplete card-by-card historical validation, and the omitted Extra Deck prevent a competitive-strength interpretation.

## Public opponent-hand feature comparison (2026-10-25)

A controlled feature-version-8 versus version-9 comparison used newly recorded schema-v17 heuristic demonstrations on the sourced Goat Control and Chaos Turbo Main Decks. The training schedule covered both deck assignments and both demonstrator seats on seeds 8400–8401: eight complete duels, 9,100 recorded decisions, and 4,630 teacher decisions. Of those teacher decisions, 686 had at least one publicly known opponent hand card. Both training runs replay-verified every duel with the pinned experimental adapter before fitting. The teacher was the project's `HeuristicAgent`, not an expert human.

Both models used width 32, three epochs, learning rate 0.001, and seed 17 on the same data. Feature 8 losses were 0.11991, 0.04478, and 0.02946; its checkpoint SHA-256 is `d7c5a31a72e3cba374cea4d66f1a1d338b3c4c38e8afc303cb889deb8d313fdd`. Feature 9 losses were 0.11639, 0.04468, and 0.03137; its checkpoint SHA-256 is `ff23f06113bda694d0387db025de0a0720e04fd5c8886cf18a4dee52235e12b2`. With `OMP_NUM_THREADS=1` on x86_64 Linux, verification plus fitting took 70.28 and 77.01 seconds wall time, with peak RSS 509,352 and 510,148 KB respectively. The ignored checkpoints and recordings are under `checkpoints/` and `replays/`.

On held-out seeds 8500–8507, both deck assignments and both seats, feature 9 won **18/32** directly against feature 8 (14 losses, no draws). The paired-score 95% bootstrap interval was **40.625–71.875%**. It won 11/16 with Goat Control and 7/16 with Chaos Turbo; the seat split was 13/16 first and 5/16 second. All 32 games reached terminal under the 3,000-decision cap, with 23,840 total decisions. The one-worker tournament took 57.32 seconds, or 0.558 duels and 415.9 decisions per wall-clock second; its report is `artifacts/sourced_fv9_vs_fv8_8500_8507.json` (ignored). This small same-deck comparison does not demonstrate a strength gain, and the large seat split limits interpretation.

A separate off-policy teacher-action audit on seeds 8600–8601 replay-verified eight more complete duels (8,068 decisions, 4,139 teacher decisions). On the 1,302 teacher decisions with multiple legal options, feature 8 matched the teacher exactly 1,235 times and feature 9 matched 1,238 times. On the 229 such decisions with a publicly known opponent hand card, both matched exactly **212/229**. This diagnostic measures agreement on teacher states, not competitive play; the known-hand subset is dominated by Chaos Turbo (217/229 decisions). The audit report is `artifacts/sourced_fv8_fv9_agreement_8600_8601.json` (ignored). These results do not justify preferring feature 9 for playing strength yet.

Reproduce with the pinned [native setup](native_setup.md), then collect both deck assignments using `scripts/collect_heuristic_demos.py --engine experimental --seed 8400 --seeds 2` and `--output-dir replays/sourced_v17_goat_chaos_8400_8401` or `replays/sourced_v17_chaos_goat_8400_8401`, swapping `--deck-a` and `--deck-b` between the two commands. Train with `scripts/train_behavioral_clone.py` on both output glob patterns, `--engine experimental --epochs 3 --width 32 --seed 17 --learning-rate 0.001`, selecting `--feature-version 8` or `9` and the checkpoint paths above. Compare with `scripts/evaluate_policy.py checkpoints/sourced_v17_fv9_8400_8401.pt --engine experimental --opponent-checkpoint checkpoints/sourced_v17_fv8_8400_8401.pt --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk --matchup examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/goat_control_lolmarcus_2020.ydk --seed 8500 --seeds 8 --max-decisions 3000`. Repeat the collection at seeds 8600–8601, then run `scripts/audit_policy_agreement.py` with both checkpoints and the new trajectories for the off-policy audit. Use `OMP_NUM_THREADS=1` for these measurements.

## Unseen Chaos Return and Warrior policy comparison (2026-10-25)

The same feature-version-8 and version-9 checkpoints from the public opponent-hand experiment above were evaluated on two sourced tournament Main Decks absent from their Goat Control/Chaos Turbo demonstrations: [2022 Worlds Chaos Return](../examples/decks/chaos_return_dingosig_worlds_2022.ydk) and [Warrior](../examples/decks/warrior_montague_clash.ydk). The evaluator's exact YDK file-hash gate confirmed that neither checkpoint trained on the evaluation files. This proves file-byte separation; a deck with the same card list and changed comments could bypass the gate, so the archetype separation also relies on the documented source lists. Both deck assignments and both learner seats were played at fresh seeds 8700–8707 under the pinned experimental GOAT adapter. No game reached the 3,000-decision cap.

Feature version 9 won **16/32** directly against version 8, with 16 losses and no draws. The paired-score 95% bootstrap interval was **31.25–65.625%**. Version 9 won 4/16 with Chaos Return and 12/16 with Warrior; it won 8/16 in each seat. The strong deck split makes the aggregate 50% especially important to report alongside deck assignment. These lists contain audited Shining Angel, Zaborg, Return, Bazoo, and Warrior staples, but the complete decks still lack card-by-card historical validation. This is evidence against a demonstrated generalization gain from the hand feature, not evidence of competitive strength.

The 32 duels took 24.64 seconds tournament wall time on one x86_64 Linux worker, with 12,812 decisions total, or 1.299 duels and 520.0 decisions per wall-clock second in this run. The enclosing command took 26.75 seconds and peaked at 259,468 KB RSS. The full ignored report is `artifacts/sourced_fv9_vs_fv8_chaos_return_warrior_8700_8707.json`. Reproduce after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/sourced_v17_fv9_8400_8401.pt \
  --engine experimental \
  --opponent-checkpoint checkpoints/sourced_v17_fv8_8400_8401.pt \
  --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk \
  --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --seed 8700 --seeds 8 --max-decisions 3000 --reject-training-deck-hashes \
  --output artifacts/sourced_fv9_vs_fv8_chaos_return_warrior_8700_8707.json
```

The `--reject-training-deck-hashes` option was added after this tournament and run separately against both saved checkpoints and these two YDK files; both passed. It compares exact file bytes against the checkpoint's recorded training Deck hashes, including both seats, and fails closed if the checkpoint lacks that provenance. It does not establish that all card compositions or archetype families are unseen.

Future checkpoints now record `main_deck_composition_sha256` for each training Deck. The optional `--require-unseen-main-decks` evaluator gate rejects matching Main Deck card multisets regardless of card order, comments, or Side/Extra Deck changes; it fails closed for older checkpoints without those hashes. A replay-verified one-duel, 338-teacher-decision training smoke test saved the new metadata, and a two-duel random-opponent evaluation on the Chaos Return/Warrior pair completed with both unseen-Main and exact-file gates enabled. The smoke checkpoint and report are ignored local artifacts under `.cache/goat-ai/composition_gate_smoke.pt` and `artifacts/composition_gate_smoke_8800.json`. Those two games are only an integration check, not a strength estimate. A composition hash still cannot determine whether two different Main Deck lists belong to the same archetype.

## Ordered public-chain policy comparison (2026-10-25)

Feature version 10 was trained on the same eight replay-verified, sourced Goat Control versus Chaos Turbo demonstrations as the version-9 checkpoint: 4,630 selected heuristic decisions, seed 17, width 32, three epochs, and learning rate 0.001. Its epoch losses were 0.11162, 0.04105, and 0.02848; version 9's were 0.11639, 0.04468, and 0.03137. The version-10 checkpoint is the ignored local file `checkpoints/sourced_v17_fv10_8400_8401.pt` (SHA-256 `a30a977c3285cba1155bab6c9791624300f994d585aa466fab475b0bb6e4d61a`).

In 32 paired, seat-swapped duels on fresh seeds 8800–8807, version 10 beat version 9 **20–11 with one draw** (score rate 64.06%; paired bootstrap 95% interval 53.13–76.56%). It was 8–8 as first player and 12–3–1 as second player. Its Chaos Return and Warrior assignments scored 9–7 and 11–4–1 respectively. All 32 duels terminated, with at most 725 decisions each under the 3,000-decision cap. The measured tournament took 27.04 seconds for 11,983 decisions (1.18 duels/s; 443 decisions/s). The exact training YDK-file-hash gate passed for both checkpoints against these evaluation files. The two evaluation lists were sourced Chaos Return and Warrior lists, distinct from the training Goat Control and Chaos Turbo lists; the gate checks file bytes, not archetype independence.

On a separate set of eight verified teacher duels from seeds 8600–8601, version 10 matched **116/135** multi-option decisions with a nonempty public chain, versus **114/135** for version 9. Across all 4,139 selected teacher decisions, version 10 matched 4,073 and version 9 matched 4,075. Teacher agreement is a diagnostic, not a measure of competitive strength. The 32-game result is encouraging but small and sensitive to deck and seat; it does not establish general improvement. Version 10 changes recurrent model capacity and optimization as well as chain order representation, so this comparison cannot isolate the value of order alone. The next experiment should repeat held-out deck families and seeds and compare an equal-capacity unordered-chain ablation.

Reproduction commands (using the project's virtual environment or an equivalent install):

```sh
OMP_NUM_THREADS=1 python scripts/train_behavioral_clone.py replays/sourced_v17_goat_chaos_8400_8401/*.json replays/sourced_v17_chaos_goat_8400_8401/*.json --engine experimental --feature-version 10 --epochs 3 --width 32 --seed 17 --learning-rate 0.001 --output checkpoints/sourced_v17_fv10_8400_8401.pt
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/sourced_v17_fv10_8400_8401.pt --engine experimental --opponent-checkpoint checkpoints/sourced_v17_fv9_8400_8401.pt --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk --seed 8800 --seeds 8 --max-decisions 3000 --reject-training-deck-hashes --output artifacts/sourced_fv10_vs_fv9_chaos_return_warrior_8800_8807.json
OMP_NUM_THREADS=1 python scripts/audit_policy_agreement.py --engine experimental --checkpoint checkpoints/sourced_v17_fv9_8400_8401.pt --checkpoint checkpoints/sourced_v17_fv10_8400_8401.pt --output artifacts/sourced_fv9_fv10_agreement_8600_8601.json replays/sourced_v17_goat_chaos_8600_8601/*.json replays/sourced_v17_chaos_goat_8600_8601/*.json
```

## Ordered-chain versus equal-capacity unordered ablation (2026-10-25)

Feature version 11 is an ablation of version 10: both use the same public-chain GRU, parameter count, and seeded initial weights, but version 11 sorts the visible card/controller pairs before the GRU. Reversing chain links therefore changes version 10's input but leaves version 11's input unchanged. Both models also receive the existing unordered pooled card state. The default remains version 10 while this feature is evaluated.

Version 11 was trained on the same eight replay-verified sourced Goat Control/Chaos Turbo demonstrations as version 10: 4,630 selected heuristic decisions, seed 17, width 32, three epochs, and learning rate 0.001. Its losses were 0.11168, 0.04075, and 0.02738. The ignored local checkpoint `checkpoints/sourced_v17_fv11_unordered_8400_8401.pt` has SHA-256 `f1222cf3f7d39a1909b73023acf5ae13eeda91b9cdae4069e55d6fffc47cb2b1`.

On fresh seeds 8900–8907, ordered version 10 scored **16–15 with one draw** in 32 paired, seat-swapped duels against unordered version 11 on the sourced Chaos Return and Warrior lists. The score rate was 51.56%, with a paired bootstrap 95% interval of 35.94–67.19%. Ordered version 10 went 7–9 as first player, 9–6–1 as second, 6–9–1 with Chaos Return, and 10–6 with Warrior. All 32 duels terminated within the 3,000-decision cap (maximum 746); 13,576 decisions took 33.92 seconds (0.94 duels/s, 400 decisions/s). Both exact training-deck file-hash gates passed. This result provides no evidence that chain order improves competitive strength on this schedule; it does not prove the feature is useless across other decks or decisions.

On the separate verified teacher trajectories from seeds 8600–8601, version 10 matched 116/135 multi-option chain decisions versus 115/135 for version 11. Overall agreement was 4,073/4,139 versus 4,070/4,139. These small differences are off-policy teacher-agreement diagnostics, not strength measurements. The one training seed and one held-out deck family pair still limit the conclusion.

```sh
OMP_NUM_THREADS=1 python scripts/train_behavioral_clone.py replays/sourced_v17_goat_chaos_8400_8401/*.json replays/sourced_v17_chaos_goat_8400_8401/*.json --engine experimental --feature-version 11 --epochs 3 --width 32 --seed 17 --learning-rate 0.001 --output checkpoints/sourced_v17_fv11_unordered_8400_8401.pt
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/sourced_v17_fv10_8400_8401.pt --engine experimental --opponent-checkpoint checkpoints/sourced_v17_fv11_unordered_8400_8401.pt --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk --seed 8900 --seeds 8 --max-decisions 3000 --reject-training-deck-hashes --output artifacts/sourced_fv10_vs_fv11_chaos_return_warrior_8900_8907.json
OMP_NUM_THREADS=1 python scripts/audit_policy_agreement.py --engine experimental --checkpoint checkpoints/sourced_v17_fv10_8400_8401.pt --checkpoint checkpoints/sourced_v17_fv11_unordered_8400_8401.pt --output artifacts/sourced_fv10_fv11_agreement_8600_8601.json replays/sourced_v17_goat_chaos_8600_8601/*.json replays/sourced_v17_chaos_goat_8600_8601/*.json
```

## Additional held-out Chaos Control versus Warrior schedule (2026-10-25)

The prior feature-version-10 tournament used Chaos Return and Warrior. To check deck-family sensitivity, the same version-10 checkpoint was tested on sourced Chaos Control and Warrior Main Decks, in both deck orders and both seats, with fresh seeds 9000–9007. All games used the experimental native engine and a 3,000-decision cap. These Chaos Control and Warrior Main Deck compositions passed the stronger unseen-Main-Deck gate for both version-10 and version-11 checkpoints. Version 9 lacks that provenance field, so its comparison used the exact training YDK-file-hash gate only.

| Agent A versus agent B | Overall A record | A with Chaos Control | A with Warrior | Paired bootstrap 95% score interval |
| --- | ---: | ---: | ---: | ---: |
| Ordered v10 versus unordered v11 | 16–16 | 3–13 | 13–3 | 31.25–68.75% |
| Ordered v10 versus v9 | 17–15 | 4–12 | 13–3 | 31.25–75.00% |
| Heuristic versus Heuristic control | 16–16 | 4–12 | 12–4 | 25.00–75.00% |

All three schedules comprised 32 terminal duels with no draws. Maximum decisions in one game were 1,090, 785, and 666 respectively, each below the cap. The v10/v11 schedule took 35.70 seconds for 15,500 decisions (0.90 duels/s, 434 decisions/s); the v10/v9 schedule took 34.21 seconds for 14,733 decisions. The same-agent control took 11.10 seconds. These rates describe only these local runs. The large Warrior advantage in the same-agent control shows that deck assignment can dominate these aggregate results. This schedule neither reproduces a clear version-10 advantage over version 9 nor finds an advantage over the equal-capacity unordered control. It does not prove equivalence; the intervals remain wide, and the core's full-deck historical correctness is unaudited.

```sh
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/sourced_v17_fv10_8400_8401.pt --engine experimental --opponent-checkpoint checkpoints/sourced_v17_fv11_unordered_8400_8401.pt --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_control_insids_worlds_2022.ydk --seed 9000 --seeds 8 --max-decisions 3000 --reject-training-deck-hashes --require-unseen-main-decks --output artifacts/sourced_fv10_vs_fv11_chaos_control_warrior_9000_9007.json
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/sourced_v17_fv10_8400_8401.pt --engine experimental --opponent-checkpoint checkpoints/sourced_v17_fv9_8400_8401.pt --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_control_insids_worlds_2022.ydk --seed 9000 --seeds 8 --max-decisions 3000 --reject-training-deck-hashes --output artifacts/sourced_fv10_vs_fv9_chaos_control_warrior_9000_9007.json
OMP_NUM_THREADS=1 python scripts/evaluate_native.py --engine experimental --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_control_insids_worlds_2022.ydk --seed 9000 --seeds 8 --max-decisions 3000 --agent-a heuristic --agent-b heuristic --output artifacts/heuristic_chaos_control_warrior_9000_9007.json
```

## Visible field-slot binding experiment (2026-10-25)

Feature version 12 adds the visible card embedding and current monster stats at each action's selected field slot to that action's representation. Version 10 already receives the same cards as a pooled state, but the pool cannot associate two copies of a card with their distinct current ATK or counters. Version 12 has the same parameter count and seeded initial weights as version 10; version 10 remains the default. A unit test swaps the current ATK values of two otherwise identical visible monsters: version 10's scores are unchanged, while version 12's direct and multi-card selection scores change. Unknown face-down identities remain hidden.

Earlier schema-v17 training recordings no longer matched the current native asset fingerprint after card-script changes. Fresh schema-v18 recordings used the sourced Goat Control and Chaos Turbo lists in both deck orders, both teacher seats, and seeds 10400–10401. The eight complete duels contained 6,618 decisions; replay verification preceded both training runs. Demonstrator-seat filtering retained 3,354 decisions made by `HeuristicAgent` against `RandomAgent`. The trainer now accepts fingerprinted schema-v18 recordings. Both models used width 32, seed 17, three epochs, and learning rate 0.001. Version 10 epoch losses were 0.13701, 0.05772, and 0.03565; version 12 losses were 0.14958, 0.06429, and 0.04245. The ignored checkpoint hashes are `f4a48c6c793e93c75cc63ec51e4ccce6e4467a2b5ef0a08772dea1f663fd60b3` (v10) and `0f681f00dbce6b2582aa36d68f0cc1d3c7f5693d79cca646c2479677eb57b238` (v12).

On held-out seeds 10500–10507, version 12 scored **15–17** directly against version 10 in 32 paired, seat-swapped native duels on the sourced Chaos Control and Warrior lists. The paired bootstrap 95% score interval was **31.25–62.5%**. Version 12 went 3–13 as first player, 12–4 as second, 4–12 with Chaos Control, and 11–5 with Warrior. All games terminated within the 3,000-decision cap (maximum 1,108); the 17,163 decisions took 48.21 seconds locally (0.664 duels/s, 356 decisions/s). Both exact deck-file and unseen Main Deck composition gates passed. The evaluation report is the ignored file `artifacts/sourced_v18_fv12_vs_fv10_10500_10507.json`. These results do not establish a playing-strength gain; deck and seat effects remain large, and historical correctness of the complete deck pool is still unaudited.

```sh
OMP_NUM_THREADS=1 python scripts/collect_heuristic_demos.py --engine experimental --deck-a examples/decks/goat_control_lolmarcus_2020.ydk --deck-b examples/decks/chaos_turbo_riclar_2020.ydk --seed 10400 --seeds 2 --output-dir replays/sourced_v18_goat_chaos_10400_10401
OMP_NUM_THREADS=1 python scripts/collect_heuristic_demos.py --engine experimental --deck-a examples/decks/chaos_turbo_riclar_2020.ydk --deck-b examples/decks/goat_control_lolmarcus_2020.ydk --seed 10400 --seeds 2 --output-dir replays/sourced_v18_chaos_goat_10400_10401
OMP_NUM_THREADS=1 python scripts/train_behavioral_clone.py replays/sourced_v18_goat_chaos_10400_10401/*.json replays/sourced_v18_chaos_goat_10400_10401/*.json --engine experimental --feature-version 10 --epochs 3 --width 32 --seed 17 --learning-rate 0.001 --output checkpoints/sourced_v18_fv10_10400_10401.pt
OMP_NUM_THREADS=1 python scripts/train_behavioral_clone.py replays/sourced_v18_goat_chaos_10400_10401/*.json replays/sourced_v18_chaos_goat_10400_10401/*.json --engine experimental --feature-version 12 --epochs 3 --width 32 --seed 17 --learning-rate 0.001 --output checkpoints/sourced_v18_fv12_10400_10401.pt
OMP_NUM_THREADS=1 python scripts/evaluate_policy.py checkpoints/sourced_v18_fv12_10400_10401.pt --engine experimental --opponent-checkpoint checkpoints/sourced_v18_fv10_10400_10401.pt --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --matchup examples/decks/warrior_montague_clash.ydk examples/decks/chaos_control_insids_worlds_2022.ydk --seed 10500 --seeds 8 --max-decisions 3000 --reject-training-deck-hashes --require-unseen-main-decks --output artifacts/sourced_v18_fv12_vs_fv10_10500_10507.json
```

## Six-deck pairwise headless sweep and terminal draw (2026-10-25)

The experimental adapter ran every distinct pair among the six Main Deck examples in the command below: five tournament lists and the Flip Control guide list. This historical sweep predates the later Bazoo Return tournament list and uses a different corpus from the current [tournament card priorities](card_priorities.md). It covered 15 pairings, seeds 9500–9501, and both seats, for 60 random-agent duels. All 60 reached a native terminal result below the 3,000-decision cap. There were 35 agent-A wins, 24 losses, and one draw; those outcomes are protocol coverage, not deck or agent strength estimates. The games used 54,334 decisions in total, with a maximum of 1,472 in one duel. The first sequential run took 52.00 seconds (1.15 duels/s, 1,045 decisions/s). An exact repeat produced the same 60 ordered game results, decision counts, summary, and pinned asset hashes in 51.67 seconds. Runtime varies; only the game outcomes and counts are expected to match.

The draw was Warrior versus Chaos Return at seed 9501, with Warrior in seat 0. A 429-decision trajectory replay-verified against the native core. Its last chain used pre-errata Ring of Destruction on a face-up 3000 ATK Black Luster Soldier while Life Points were 225 and 575. Previously, `GoatEnvironment.step()` returned the prior decision's 225/575 LP observation after the terminal `MSG_WIN`. The adapter now queries a fresh redacted terminal observation for the previous viewer and reports 0/0 LP, no legal actions, and a draw. The native field query represents lethal negative LP as unsigned values; the terminal observation clamps them to zero. Decision records remain pre-action player-visible observations. Schema v18 now stores a separate final player-visible observation; replay verification compares it with the native terminal state, and the offline viewer displays it as a final frame. Older v1–v17 trajectories remain readable and still end on the last preterminal decision. This fixture tests terminal environment behavior and a complete sourced duel; it does not certify every card interaction during that duel.

Reproduce the sweep with the pinned native assets and project environment:

```bash
decks=(examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/warrior_montague_clash.ydk examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/flip_control_goatformat_guide.ydk)
args=()
for ((i=0; i<${#decks[@]}; i++)); do
  for ((j=i+1; j<${#decks[@]}; j++)); do
    args+=(--matchup "${decks[i]}" "${decks[j]}")
  done
done
OMP_NUM_THREADS=1 python scripts/evaluate_native.py --engine experimental "${args[@]}" --agent-a random --agent-b random --seed 9500 --seeds 2 --max-decisions 3000 --output artifacts/sourced_six_deck_pairwise_random_9500_9501.json
```

## Expanded six-deck native sweep (2026-10-25)

The same 15 pairings, both seats, and seeds 9600–9609 produced **300/300 terminal native duels** with no 3,000-decision cap hits. The run used 286,308 decisions (954.36 per duel on average; 1,444 maximum). The ordered outcomes were 198 wins, 97 losses, and five draws from the recorded `agent_a` deck assignment. Both agents were random, so these counts reflect deck and seat effects rather than agent strength. This extends protocol coverage across the six examples in the command above; it does not validate every card ruling or hidden-information path reached in the duels. All five draws ended when pre-errata Ring of Destruction targeted a face-up monster whose current ATK exceeded both Life Point totals: targets had 1800, 1400, 1200, 2400, and 2400 ATK. Each draw was independently rerun with the recorded seed and replay-verified, ending with a 0/0 LP terminal observation. A second automated sourced-deck regression now pins the 1400-ATK Dekoichi case alongside the earlier 3000-ATK BLS case.

On an Intel Core i7-10700K with four spawned native workers and `OMP_NUM_THREADS=1`, the measured tournament wall time was **73.20 seconds**, or **4.10 complete duels/s** and **3,911 decisions/s**. The pinned core was `edo9300/ygopro-core baa3881d0bae48e9994f915f5c931be53c1ba8ef`; the run's JSON report records asset and deck SHA-256 hashes. A one-worker rerun of seeds 9600–9601 took **56.72 seconds** for 60 duels (**1.06 duels/s**). Its 60 ordered `(deck_a, deck_b, seed, seat, winner, decisions, outcome)` records exactly matched the same subset from the four-worker run. Runtime depends on hardware and concurrent load; this comparison establishes deterministic results for the tested subset.

To reproduce, run the `decks` and `args` loop in the preceding section with the project virtual environment, then use:

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_native.py --engine experimental "${args[@]}" --agent-a random --agent-b random --seed 9600 --seeds 10 --max-decisions 3000 --workers 4 --output artifacts/sourced_six_deck_pairwise_random_9600_9609.json
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_native.py --engine experimental "${args[@]}" --agent-a random --agent-b random --seed 9600 --seeds 2 --max-decisions 3000 --workers 1 --output artifacts/sourced_six_deck_pairwise_random_9600_9601_single.json
```

The generated JSON reports are local benchmark artifacts and are excluded from Git.

## Current-code audit of the earlier six-example schedule (2026-10-25)

The earlier archived 60-game report remains a historical measurement. Re-running its exact six-example deck schedule and seeds 9500–9501 on the current adapter produced **60 terminal duels**, **55,135 decisions**, and 37 wins, 22 losses, and one draw from agent A's deck assignment. Eleven of the 60 ordered game records differ from the archived report, although the base core/database/utility and deck hashes in the two reports match. Changes to Python adapter code and in-memory card-script corrections were not represented by those older asset fields, so the archived outcomes should not be presented as current-code exact replay evidence. The changed records cannot be attributed to the Dekoichi correction alone.

The current ordered games and summary matched exactly between one and four native workers. The four-worker tournament took **16.11 seconds** (3.72 duels/s); the one-worker run of the same games took **59.33 seconds** (1.01 duels/s). Runtime measurements were taken in separate runs. New `evaluate_native.py` reports include `source_code_sha256` over project Python source, evaluator, and `pyproject.toml`, plus `card_scripts_sha256` over the pinned Lua script tree. For the four-worker report these were `6ded7a84aa7d43716604cd7f5ac0d8e3ef3c5164a9756de33784a5441640422d` and `f886f54c419d3792fd69888d74190c070992609caad8f5737e3f563bd736b71c`, respectively. Together with the existing native asset and deck hashes, these fields make later implementation drift detectable. The report stays under the ignored `.cache/goat-ai/research/` directory; repeat the `decks` and `args` loop above with `--workers 4` and the same seed options to reproduce it. This remains protocol coverage, not a card-correctness or strength claim.

## Six-tournament-deck pairwise protocol sweep (2026-10-25)

The current [competitive tournament corpus](../src/goat_ai/evaluation/competitive_corpus.py) contains six published tournament Main Decks, including Bazoo Return and excluding the Flip Control guide deck. `evaluate_native.py --tournament-corpus` creates all 15 unordered pairings directly from that list. Seeds 9750–9751 and both seats produced **60/60 terminal native duels** under the 3,000-decision cap. The games used **57,071 decisions** in total, with **1,391** in the longest duel. Agent A's deck assignment recorded 35 wins, 23 losses, and two draws; both agents were random, so these results do not measure playing strength or historical correctness of every card effect.

On the pinned local assets with four native workers and `OMP_NUM_THREADS=1`, the tournament took **17.03 seconds**, or **3.52 duels/s**. The identical schedule with one worker took **61.74 seconds**. All 60 ordered game records, the summary, deck and base asset hashes, Python source hash, and Lua script-tree hash matched exactly across worker counts. The source hash was `58d5344601591d2916fe2071ae7e2cfdd728a7d5852aef2e626f94e4395a40f0`; the script-tree hash was `f886f54c419d3792fd69888d74190c070992609caad8f5737e3f563bd736b71c`. Runtime varies with system load.

Reproduce from the repository root after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python scripts/evaluate_native.py \
  --engine experimental --tournament-corpus --agent-a random --agent-b random \
  --seed 9750 --seeds 2 --max-decisions 3000 --workers 4 \
  --output .cache/goat-ai/research/six_tournament_deck_sweep_9750_9751.json
```

The one-worker check uses the same command with `--workers 1` and a different output path. Generated reports stay in the ignored `.cache` directory.

## Balanced six-deck heuristic baseline (2026-10-25)

The generic `HeuristicAgent` and `RandomAgent` were evaluated on all 15 unordered pairings of the same six Main Deck examples, with **both deck assignments**, **both agent seats**, and seeds 9800–9801: 120 games per report. The exact same schedule and pinned asset/deck hashes were used for a RandomAgent-versus-RandomAgent control. All 240 games reached terminal outcomes below the 3,000-decision cap. The control matters because even with both seats swapped, a fixed candidate deck assignment can dominate a short result; the schedule also reverses which deck candidate A receives.

| Candidate A | Wins | Losses | Draws | Score | Paired score 95% bootstrap interval |
| --- | ---: | ---: | ---: | ---: | ---: |
| HeuristicAgent vs RandomAgent | 76 | 44 | 0 | 63.3% | 53.3–72.5% |
| RandomAgent vs RandomAgent control | 58 | 58 | 4 | 50.0% | 40.8–59.2% |

The new `paired_score_difference` helper matches reports by deck assignment, seed, and seat, then resamples each unordered deck pair and seed as a unit, keeping both assignments and seats together. The measured heuristic-minus-control score difference is **+13.3 percentage points**, with a **95% paired bootstrap interval of +3.3 to +23.3 points**. This is evidence of an advantage over RandomAgent on this small native schedule, not a claim about strong human play or historically complete card rules. Only two seeds per deck pairing were tested, and the heuristic's card choices remain very simple.

The heuristic's candidate-deck wins out of 20 were Goat Control 17, Chaos Turbo 11, Warrior 16, Chaos Control 14, Chaos Return 15, and Flip Control 3. The same deck slots in the random control won 15, 12, 11, 10, 9, and 1 games respectively, with two draws each for Chaos Return and Flip Control. This variation is why policy comparisons need deck and seat splits. The four-worker heuristic tournament used 74,391 decisions in 16.95 seconds; the random control used 104,646 decisions in 27.31 seconds. Throughput differs because the agents produced different game lengths, so these times should not be read as an engine speed comparison.

Reproduce with the pinned native setup and project environment:

```bash
decks=(examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/warrior_montague_clash.ydk examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/flip_control_goatformat_guide.ydk)
args=()
for ((i=0; i<${#decks[@]}; i++)); do
  for ((j=i+1; j<${#decks[@]}; j++)); do
    args+=(--matchup "${decks[i]}" "${decks[j]}" --matchup "${decks[j]}" "${decks[i]}")
  done
done
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_native.py --engine experimental "${args[@]}" --agent-a heuristic --agent-b random --seed 9800 --seeds 2 --max-decisions 3000 --workers 4 --output artifacts/sourced_balanced_heuristic_random_9800_9801.json > /dev/null
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_native.py --engine experimental "${args[@]}" --agent-a random --agent-b random --seed 9800 --seeds 2 --max-decisions 3000 --workers 4 --output artifacts/sourced_balanced_random_random_9800_9801.json > /dev/null
```

The reports are ignored local artifacts. Reproduce the paired interval after both reports exist:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from goat_ai.evaluation import GameResult, paired_score_difference

def load(name):
    report = json.loads(Path('artifacts', name).read_text())
    fields = ('deck_a', 'deck_b', 'seed', 'a_seat', 'winner', 'decisions')
    games = [GameResult(**{key: row[key] for key in fields})
             for row in report['games']]
    return report, games

candidate, candidate_games = load('sourced_balanced_heuristic_random_9800_9801.json')
control, control_games = load('sourced_balanced_random_random_9800_9801.json')
assert candidate['asset_sha256'] == control['asset_sha256']
assert candidate['deck_sha256'] == control['deck_sha256']
print(paired_score_difference(candidate_games, control_games))
PY
```

### Flip-aware heuristic ablation

The generic heuristic scores face-up Normal Summons above monster Sets. A seed-9800 Flip Control action trace showed it Normal Summoning Dekoichi, Mask of Darkness, and Magician of Faith while Set was legal. An optional `flip_heuristic` variant reads the public Flip-monster type flag from the pinned card databases and scores Sets of those monsters above Normal Summons. It uses the same redacted observations and legal actions as other agents; the default `heuristic` is unchanged.

On the identical 120-game, six-deck schedule above, `flip_heuristic` scored **75 wins, 44 losses, and 1 draw** against RandomAgent (62.9%; paired score interval 52.9–72.5%). Its score difference from the original heuristic was **−0.4 percentage points**, with a paired 95% bootstrap interval of **−8.3 to +7.9 points**. Flip Control improved from 3/20 to 6/20 wins, and Chaos Turbo from 11/20 to 15/20, while Chaos Control fell from 14/20 to 7/20. The variant therefore has no measured aggregate improvement; more decision-level analysis and independent seeds are needed before making it the default. The four-worker run used 75,132 decisions in 16.98 seconds on the same pinned assets. All 120 games reached terminal states under the cap.

To reproduce, run the schedule-building shell commands above with `--agent-a flip_heuristic` and `--output artifacts/sourced_balanced_flip_heuristic_random_9800_9801.json`. In the Python snippet above, load that report as the candidate and `sourced_balanced_heuristic_random_9800_9801.json` as the control.

## Dimension Fusion Turbo guide-deck protocol check (2026-10-25)

The [GoatFormat Dimension Fusion Turbo guide](https://www.goatformat.com/dimension-fusion-turbo.html) supplies a 40-card Main Deck built around Thunder Dragon, Bazoo, and Dimension Fusion. `examples/decks/dimension_fusion_turbo_goatformat_guide.ydk` transcribes that guide list with pinned GOAT/pre-errata IDs. The source provides no Extra or Side Deck for this example, so those sections are empty. It is a guide example, not a tournament submission or a metagame frequency sample. The pinned GOAT deck validator accepted the list.

On the local pinned native assets, RandomAgent versus RandomAgent completed all **20** seat-swapped games against the sourced 2020 Chaos Turbo list on seeds 9900–9909 under a 3,000-decision cap. The Dimension Fusion Turbo slot won 11 and lost 9, with no draws. Mean decisions were 907.8 and the maximum was 1,202. Four native workers completed the tournament in 5.06 seconds, or 3.96 complete duels per wall-clock second. The measured score interval was 35–75%, too broad to infer a deck-strength advantage. Two additional seed-1 seat-swapped full-duel fixtures serialize and replay-verify their trajectories. These are protocol and reproducibility checks, not human-strength or complete historical-ruling claims.

```sh
OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python scripts/evaluate_native.py --engine experimental --matchup examples/decks/dimension_fusion_turbo_goatformat_guide.ydk examples/decks/chaos_turbo_riclar_2020.ydk --seed 9900 --seeds 10 --max-decisions 3000 --workers 4 --agent-a random --agent-b random --output artifacts/dft_chaos_random_9900_9909.json
PYTHONPATH=. GOAT_AI_NATIVE_ROOT=.cache/goat-ai .venv/bin/pytest -q tests/test_dimension_fusion_turbo_duel.py tests/test_historical_dimension_fusion.py
```

## Visible-stat combat heuristic and deck-assignment balance (2026-10-25)

`CombatHeuristicAgent` is an experimental, deck-agnostic extension of the original `HeuristicAgent`. It selects a higher-ATK attacker, avoids attacking when every visible opposing monster would beat every available attacker, and prefers a beatable face-up battle target. It uses only `Observation.field` and the current legal actions; it does not query the native duel state or hidden cards. The original heuristic remains available as a fixed control and as the teacher named in earlier demonstration reports. The combat heuristic has no search, matchup model, or card-specific tactics; hidden defenders and response cards can still punish its attacks.

The combat teacher is now version 2: it applies the remembered attacker's stats only to the immediately following battle-target choice. Version 1 could reuse a stale attacker slot at a later, unrelated `select_card` prompt. New collector trajectories record `teacher_version`, and behavioral-cloning checkpoints propagate it per training game; older trajectories and checkpoints without this field retain their original provenance and must not be treated as version 2. A local restricted-core smoke run at seed 18100 completed two seat-swapped duels (288 and 280 decisions), replay-verified both, and trained a one-epoch, 310-decision checkpoint whose two training-game entries each record teacher version 2. This verifies data plumbing and the stale-target guard, not a competitive-strength change.

To check whether that fix changes the prior sourced-deck training data, the 16 CombatHeuristicAgent-versus-RandomAgent duels at seeds 15100–15103 were collected again with the same Goat Control/Chaos Turbo deck assignments and seats. Run the two collection commands below with the current code, changing only their output directories to `.cache/goat-ai/combat-v2-goat-chaos-15100-15103` and `.cache/goat-ai/combat-v2-chaos-goat-15100-15103`. The new trajectories contained 17,729 decisions and 9,117 teacher decisions. Each matched version-1 trajectory had the same decision count, selected action at every decision, and winner; the teacher again won 12 of 16. Thus the previously reported clone trained on those exact decisions does not acquire a new strength result from this guard. Future tournament JSON records baseline agent versions; prior combat-baseline reports were made with version 1 and should be labeled as such when compared with new reports.

A first **unbalanced** head-to-head assigned each agent a fixed deck within each pair and only swapped seats. On seeds 316–323 the combat heuristic won 45/64 games across four directed matchups; on seeds 324–331 it won only 20/48 across three others. The latter included 2/16 when assigned Chaos Control against Goat Control, whereas in the reverse assignment on seeds 332–339 it won 13/16. These results show a large deck-assignment effect and cannot by themselves establish a general agent improvement.

The runner now accepts `--both-deck-assignments` to schedule both agents with each deck in an unordered pair, while still swapping seats. Its percentile score interval resamples the unordered deck pair and seed as one unit, retaining all mirrored games together. With two pairs on seeds 332–339, the combat heuristic scored **37 wins, 26 losses, 1 draw in 64 games** (58.6%; paired 95% bootstrap score interval **53.1–64.1%** after the corrected clustering). On a separate three-pair schedule on seeds 340–347, it scored **54 wins, 42 losses in 96 games** (56.3%; paired 95% interval **52.1–61.5%**). That later schedule includes the Flip Control guide list, which is not a tournament entry. Both samples favor the combat heuristic on their selected deck pairs and seeds; the matchup splits still vary, and neither sample proves broad competitive strength against human players or other agents. The older evaluation reports were generated before this clustering change, so their saved intervals are historical output and may differ if regenerated with the current code. Game outcomes are unaffected.

Reproduce the later balanced schedule after [native setup](native_setup.md):

```bash
PYTHONPATH=. GOAT_AI_NATIVE_ROOT=.cache/goat-ai .venv/bin/python scripts/evaluate_native.py \
  --engine experimental --agent-a combat_heuristic --agent-b heuristic \
  --both-deck-assignments \
  --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk \
  --matchup examples/decks/flip_control_goatformat_guide.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/warrior_montague_clash.ydk \
  --seed 340 --seeds 8 --max-decisions 3000 \
  --output artifacts/combat_heuristic_balanced_340_347.json
```

The ignored local report records individual outcomes, seat and deck assignments, asset and deck hashes, wall time, and the measured interval. Follow-up evaluation should include additional independent tournament deck files, more seeds, and direct comparison against RandomAgent before using this baseline as a behavioral-cloning teacher. No generated report or replay is committed.

## Combat-teacher behavioral cloning (2026-10-25)

The demonstration collector now accepts `--teacher combat_heuristic`. Eight experimental native duels on seeds 11000–11001 included both orders of the sourced Goat Control and Chaos Turbo decks and each teacher seat against RandomAgent. The combat teacher won 7/8. The eight full-duel trajectories contain 7,458 decisions, of which 3,812 belong to the labeled teacher seat. Each trajectory stores the teacher class and seat, deck and native-asset fingerprints, and player-visible observations; the behavioral-cloning command replay-verified all eight before fitting. These are generated agent demonstrations, not human data, and their labels do not establish correct strategy.

A PyTorch CPU policy with feature version 12, width 32, three epochs, seed 17, and learning rate 0.001 reached mean per-decision cross-entropies **0.15483, 0.07044, 0.05118**. Its checkpoint records `CombatHeuristicAgent`, all eight input hashes, exact Main Deck composition hashes, and PyTorch `2.5.1+cpu`; the verified input trajectories carry the pinned asset manifest. A second run with the same inputs and seed reproduced all **34 model tensors**, losses, and provenance exactly. The repeat took **74.45 seconds** of wall time and peaked at **467,668 KB resident memory** under `OMP_NUM_THREADS=1` on Linux 6.8.0 x86_64. The time and memory are measurements of that repeat run, not throughput estimates for other hardware.

On four new replay-verified combat-teacher duels at seed 11002 (2,265 teacher decisions), this checkpoint matched **699/745** decisions with more than one legal action. The earlier feature-version-12 checkpoint trained from the original heuristic matched **691/745** on those same decisions. On multi-option decisions with a nonempty chain the new checkpoint matched **66/83**, versus **68/83** for the earlier checkpoint. This is an off-policy imitation diagnostic, not competitive evaluation.

On unseen Chaos Control, Chaos Return, and Warrior Main Decks, both deck assignments, both seats, and fresh seeds 12000–12003, the new checkpoint split **16–16** against its combat teacher (paired 95% score interval **40.6–59.4%**). On seeds 12004–12007 it scored **16 wins, 13 losses, 3 draws** directly against the earlier version-12 checkpoint (score 54.7%, paired 95% interval **40.6–67.2%**). The exact Main Deck composition gate rejected any training deck overlap in both tournaments. Warrior assignment accounted for most of the new policy's wins; these samples do not establish a competitive improvement. M4 still requires broader, independently audited deck families, larger evaluation samples, and improvement through self-play or another learning method.

Reproduce the collection and training after [native setup](native_setup.md):

```bash
PYTHONPATH=. .venv/bin/python scripts/collect_heuristic_demos.py --engine experimental --teacher combat_heuristic --deck-a examples/decks/goat_control_lolmarcus_2020.ydk --deck-b examples/decks/chaos_turbo_riclar_2020.ydk --seed 11000 --seeds 2 --max-decisions 3000 --output-dir replays/combat_goat_chaos_11000_11001
PYTHONPATH=. .venv/bin/python scripts/collect_heuristic_demos.py --engine experimental --teacher combat_heuristic --deck-a examples/decks/chaos_turbo_riclar_2020.ydk --deck-b examples/decks/goat_control_lolmarcus_2020.ydk --seed 11000 --seeds 2 --max-decisions 3000 --output-dir replays/combat_chaos_goat_11000_11001
OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python scripts/train_behavioral_clone.py replays/combat_goat_chaos_11000_11001/*.json replays/combat_chaos_goat_11000_11001/*.json --engine experimental --feature-version 12 --epochs 3 --width 32 --seed 17 --learning-rate 0.001 --output checkpoints/combat_bc_fv12_11000_11001.pt
```

For the balanced competitive check, use `scripts/evaluate_policy.py` with `--opponent combat_heuristic --both-deck-assignments --require-unseen-main-decks`, the Chaos Control/Warrior and Chaos Return/Warrior matchups, and seeds 12000–12003. The direct checkpoint comparison uses `--opponent-checkpoint checkpoints/sourced_v18_fv12_10400_10401.pt` and seeds 12004–12007. The off-policy audit uses `scripts/audit_policy_agreement.py` on seed-11002 trajectories collected with the same collector options. Checkpoints, generated replays, and reports remain ignored local artifacts.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python scripts/evaluate_policy.py checkpoints/combat_bc_fv12_11000_11001.pt --engine experimental --opponent combat_heuristic --both-deck-assignments --require-unseen-main-decks --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --seed 12000 --seeds 4 --max-decisions 3000 --output artifacts/combat_bc_vs_teacher_unseen_12000_12003.json
OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python scripts/evaluate_policy.py checkpoints/combat_bc_fv12_11000_11001.pt --engine experimental --opponent-checkpoint checkpoints/sourced_v18_fv12_10400_10401.pt --both-deck-assignments --require-unseen-main-decks --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --seed 12004 --seeds 4 --max-decisions 3000 --output artifacts/combat_bc_vs_old_fv12_unseen_12004_12007.json
```

## Combat-clone self-play exploration (2026-10-25)

Starting from the combat-teacher feature-version-12 checkpoint above, the existing episodic REINFORCE-style trainer played 16 native duels on seeds 13000–13015, with Goat Control and Chaos Turbo each assigned to the learner eight times. Its opponents were frozen historical policy snapshots or RandomAgent. The learner won 11 and lost 5 during training; all **16 complete trajectories replay-verified** afterward (10,886 decisions). The run took **42.63 seconds** and peaked at **396,616 KB resident memory** on the same CPU setup. On unseen Chaos Control, Chaos Return, and Warrior Main Decks, both deck assignments and both seats, the child split **16–16** directly against its parent on seeds 14000–14003. It made the same choices as its parent on all 745 multi-option decisions in the separate seed-11002 combat-teacher action audit, despite changes to all 34 weight tensors. The training record is not evidence of improvement.

The trainer now accepts `--learner-temperature`, which applies the same softmax temperature to action sampling and to the log-probability and entropy in its score-function update. The default remains 1.0. A unit test with two trainable logits checks the exact gradient magnitude at temperature 2, so the experiment is optimizing the distribution it samples. A second run started from the same parent and used temperature 2, learning rate 0.0003, entropy coefficient 0.01, and 32 games on seeds 13100–13131. It balanced the two training decks (16 learner games each), won 16, lost 15, and drew 1 against its sampled opponents. All **32 full trajectories replay-verified** afterward (27,102 decisions). Training took **99.26 seconds** and peaked at **387,588 KB resident memory**. On the same unseen deck families with fresh seeds 14100–14103, the child scored **17–15** against its parent (paired 95% score interval **50.0–59.4%**). Its seed-11002 action audit changed one of 745 multi-option teacher decisions, improving exact agreement from 699 to 700. These schedules have only four evaluation seeds; the two training runs also changed several hyperparameters and game count, so the difference cannot be attributed to temperature. No reliable self-play strength gain is established.

Reproduce with the pinned [native setup](native_setup.md), the combat-clone checkpoint above, and ignored local artifacts:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python scripts/train_self_play.py checkpoints/combat_bc_fv12_11000_11001.pt --engine experimental --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk --matchup examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/goat_control_lolmarcus_2020.ydk --seed 13000 --games 16 --max-decisions 3000 --record-dir replays/combat_bc_selfplay_13000_13015 --output checkpoints/combat_bc_selfplay_13000_13015.pt
OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python scripts/train_self_play.py checkpoints/combat_bc_fv12_11000_11001.pt --engine experimental --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk --matchup examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/goat_control_lolmarcus_2020.ydk --seed 13100 --games 32 --learning-rate 0.0003 --learner-temperature 2.0 --entropy-coefficient 0.01 --max-decisions 3000 --record-dir replays/combat_bc_selfplay_explore_13100_13131 --output checkpoints/combat_bc_selfplay_explore_13100_13131.pt
OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python scripts/evaluate_policy.py checkpoints/combat_bc_selfplay_explore_13100_13131.pt --engine experimental --opponent-checkpoint checkpoints/combat_bc_fv12_11000_11001.pt --both-deck-assignments --require-unseen-main-decks --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk --seed 14100 --seeds 4 --max-decisions 3000
```

The next RL experiment needs a stronger credit-assignment or opponent-selection method, controlled hyperparameter comparisons, and larger held-out tournaments. Search work remains gated on simulator and policy reliability.

## Replay-verified staple decision audit

`audit_policy_agreement.py` now reports three card-specific contexts for the ten
cards shared by all five sourced tournament Main Decks in the current corpus:
when a source-card action is offered, when the teacher selects that action, and
when the card is the latest link of a chain asking for a decision. Target-choice
card codes are not counted as played cards. A decision can appear under more
than one card and can be offered repeatedly as a turn progresses. These counts
are an off-policy diagnostic against a heuristic teacher, not independent
competitive decisions or a playing-strength estimate.

On the pinned local assets, the version-12 combat behavioral clone
(`checkpoints/combat_bc_fv12_11000_11001.pt`, SHA-256
`5d78f23fb13f82efc63aee106e1c4d8812e6b65a3fe5d469333e5aad0504b2b4`)
was audited against eight fresh CombatHeuristicAgent-versus-RandomAgent duels.
Both deck assignments of sourced Goat Control and Chaos Turbo, both teacher
seats, and seeds 15000–15001 were included. All eight trajectories
replay-verified against the current core and assets: 8,483 total decisions and
4,455 teacher decisions. The clone matched 1,339 of 1,454 teacher decisions
with multiple legal actions. Card-specific exact matches were:

| Staple | Offered | Teacher selected | Latest chain link |
| --- | ---: | ---: | ---: |
| Breaker the Magical Warrior | 38/49 | 26/36 | 16/16 |
| Nobleman of Crossout | 33/38 | 18/20 | 33/33 |
| Book of Moon | 31/33 | 23/23 | 55/60 |
| Black Luster Soldier | 26/28 | 21/23 | 24/28 |
| Ring of Destruction | 16/19 | 8/8 | 12/14 |
| Snatch Steal | 16/17 | 14/14 | 25/25 |
| Heavy Storm | 9/12 | 6/8 | 11/11 |
| Delinquent Duo | 9/10 | 7/8 | 11/11 |
| Graceful Charity | 7/8 | 7/7 | 18/20 |
| Pot of Greed | 6/7 | 5/5 | 7/7 |

The teacher-selected Breaker split is more specific than its 26/36 total:
Normal Summons matched 7/7 and `chain` actions matched 5/5, while attacks
matched 7/11, position changes 5/10, and Flip Summons 2/3. This sample points
to combat and position decisions involving Breaker, not evidence of a defect in
its Spell Counter effect. BLS `chain` and `activate` actions matched 7/7 and
6/6; four of its latest-chain-link choices differed, warranting a target-choice
audit. In one visible state the teacher activated Heavy Storm while the clone
chose Snatch Steal; in
another, the teacher targeted a Sheep Token with Ring while the clone targeted
its own Breaker. A small heuristic sample cannot establish which choice was
stronger. An attempt to reuse the older seed-8600–8601 trajectories failed
current replay verification (asset fingerprints or observations differed), so
those files were excluded rather than mixed into this report.

Reproduce after [native setup](native_setup.md), using `--teacher
combat_heuristic --engine experimental --max-decisions 3000` in each collector
command:

```bash
for seed in 15000 15001; do
  PYTHONPATH=. OMP_NUM_THREADS=1 python scripts/collect_heuristic_demos.py \
    --engine experimental --teacher combat_heuristic \
    --deck-a examples/decks/goat_control_lolmarcus_2020.ydk \
    --deck-b examples/decks/chaos_turbo_riclar_2020.ydk \
    --seed "$seed" --seeds 1 --max-decisions 3000 \
    --output-dir "replays/staple_audit_goat_chaos_$seed"
  PYTHONPATH=. OMP_NUM_THREADS=1 python scripts/collect_heuristic_demos.py \
    --engine experimental --teacher combat_heuristic \
    --deck-a examples/decks/chaos_turbo_riclar_2020.ydk \
    --deck-b examples/decks/goat_control_lolmarcus_2020.ydk \
    --seed "$seed" --seeds 1 --max-decisions 3000 \
    --output-dir "replays/staple_audit_chaos_goat_$seed"
done
PYTHONPATH=. OMP_NUM_THREADS=1 python scripts/audit_policy_agreement.py \
  --engine experimental --native-root .cache/goat-ai \
  --checkpoint checkpoints/combat_bc_fv12_11000_11001.pt \
  --output .cache/goat-ai/staple-agreement-combat-15000-15001.json \
  replays/staple_audit_goat_chaos_15000/*.json \
  replays/staple_audit_chaos_goat_15000/*.json \
  replays/staple_audit_goat_chaos_15001/*.json \
  replays/staple_audit_chaos_goat_15001/*.json
```

## Larger combat-teacher clone on shared GOAT staples (2026-10-25)

A second feature-version-12, width-32 behavioral clone was trained from **16
fresh replay-verified full duels** of CombatHeuristicAgent versus RandomAgent
on the sourced Goat Control and Chaos Turbo Main Decks. Seeds 15100–15103
covered both deck assignments and both teacher seats. The collector reported
12 teacher wins in 16 games; 9,117 labeled teacher decisions entered training.
Three CPU epochs with seed 17 and learning rate 0.001 produced mean losses
**0.11753, 0.05777, 0.04557**. The ignored local checkpoint is
`checkpoints/combat_bc_fv12_15100_15103.pt`, SHA-256
`eeaeea739d47ea40c2488c3291dc120cfa018c6552150d33bb7bf337ab233484`.
Its metadata records all 16 input trajectories, teacher provenance, seed, and
feature version. These are agent demonstrations, not human games.

On the separate seed-15000–15001 eight-duel audit, this clone matched
**1,368/1,454** teacher decisions with multiple legal options, versus
**1,339/1,454** for the earlier combat clone. Among the ten cards shared by
all five sourced tournament Main Decks, teacher-selected Breaker actions
matched **31/36** instead of **26/36**. Breaker attacks improved from **7/11**
to **11/11**, while position changes remained **5/10**. These are off-policy
agreement counts; they do not measure winning chances or identify optimal
plays.

Held-out tournaments used the separately sourced Chaos Control, Chaos Return,
and Warrior Main Decks, both deck assignments and seats, the experimental GOAT
adapter, and 3,000-decision limits. No game hit the limit. The new clone scored
**37 wins, 25 losses, and 2 draws** directly against its parent on seeds
15300–15307: score **59.4%**, with a matchup-seed clustered 95% bootstrap
interval of **50.8–68.8%**. The deck splits still differed substantially, so
this is evidence for this schedule, not general dominance across archetypes.

Against CombatHeuristicAgent on the same seeds 15400–15407, the new clone
scored **30–32 with 2 draws** (48.4%; paired interval 40.6–56.2%). Its parent
scored **21–42 with 1 draw** (33.6%; 22.7–45.3%) on the identical schedule.
The matched score difference was **+14.8 percentage points**, with a clustered
95% bootstrap interval of **+4.7 to +25.8 points**. Against the original
HeuristicAgent on fresh seeds 15500–15507, the new clone scored **32–31 with
1 draw** (50.8%; 45.3–56.2%). Against RandomAgent it scored **45–19**
(70.3%; 59.4–81.2%). The intervals for absolute performance against the two
heuristic baselines include 50%; no claim that the clone beats either heuristic
is supported. The five tournament decks used here remain an incomplete
metagame sample, and their individual card rulings are still being audited.
M4 remains open: it requires broader held-out families, stronger opponents,
and a reproducible self-play gain. The larger imitation set gives a stronger
starting checkpoint for that work.

Reproduce with [pinned native assets](native_setup.md) and `OMP_NUM_THREADS=1`:

```bash
PYTHONPATH=. OMP_NUM_THREADS=1 python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher combat_heuristic \
  --deck-a examples/decks/goat_control_lolmarcus_2020.ydk \
  --deck-b examples/decks/chaos_turbo_riclar_2020.ydk \
  --seed 15100 --seeds 4 --max-decisions 3000 \
  --output-dir replays/combat_more_goat_chaos_15100_15103
PYTHONPATH=. OMP_NUM_THREADS=1 python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher combat_heuristic \
  --deck-a examples/decks/chaos_turbo_riclar_2020.ydk \
  --deck-b examples/decks/goat_control_lolmarcus_2020.ydk \
  --seed 15100 --seeds 4 --max-decisions 3000 \
  --output-dir replays/combat_more_chaos_goat_15100_15103
PYTHONPATH=. OMP_NUM_THREADS=1 python scripts/train_behavioral_clone.py \
  replays/combat_more_goat_chaos_15100_15103/*.json \
  replays/combat_more_chaos_goat_15100_15103/*.json \
  --engine experimental --native-root .cache/goat-ai \
  --feature-version 12 --epochs 3 --width 32 --seed 17 \
  --learning-rate 0.001 \
  --output checkpoints/combat_bc_fv12_15100_15103.pt
```

The ignored local JSON reports are named `combat_bc_more_vs_parent_15300_15303`,
`combat_bc_more_vs_parent_15304_15307`, `combat_bc_more_vs_teacher_15400_15403`,
`combat_bc_more_vs_teacher_15404_15407`, the corresponding `parent_vs_teacher`
reports, and `combat_bc_more_vs_{heuristic,random}_15500_15507` under
`.cache/goat-ai/`. Run `scripts/evaluate_policy.py` with the two matchups above,
`--both-deck-assignments --require-unseen-main-decks --workers 2 --seeds 4`
for each parent and teacher segment, or `--seeds 8` for the baseline segment.
The action-audit command and fresh seed-15000–15001 trajectories are documented
in the preceding section.

## Self-play from the larger combat clone (2026-10-25)

The larger combat-teacher clone above initialized a bounded, 64-game
REINFORCE-style self-play run on seeds 15600–15663. Goat Control and Chaos Turbo
alternated deck assignments, and the learner alternated seats. The trainer used
learning rate 0.0003, sampling temperature 2.0, entropy coefficient 0.01, a
snapshot every eight games, at most eight snapshots, and a 3,000-decision game
cap. Nineteen opponents were RandomAgent; the other 45 were checkpoint
snapshots. The learner went 32–32 in training, contributing 7,404 decisions.
The ignored local child checkpoint is
`checkpoints/combat_more_selfplay_15600_15663.pt`, SHA-256
`0af7784a27a5b7df1e7deeca531ced8285a7a58784308a628b5ae0bd46a40c9b`.
All 64 recorded training duels, containing **50,620 total decisions**,
replay-verified against the pinned native assets. No training game reached the
decision cap. The training win fraction is not an independent strength measure.

On fresh seeds 15700–15707, the child played its parent across Chaos Control,
Chaos Return, and Warrior, with both deck assignments and both seats. None of
those Main Deck compositions was used in training. The child scored **32 wins,
31 losses, and 1 draw** in 64 games (50.8%). The paired matchup-seed bootstrap
interval was **50.0–52.3%**; the much wider decisive-game Wilson interval was
**38.8–62.7%**. The score interval is unusually tight because paired seat and
deck outcomes mostly cancel in this direct comparison; it should not be read as
evidence of broader deck strength. The child was 13–19 going first and 19–12
with one draw going second. This schedule does not establish a self-play gain.

On the separate eight-duel seed-15000–15001 combat-teacher audit, exact
agreement on choices with multiple legal options was **1,369/1,454** for the
child versus **1,368/1,454** for its parent. Teacher-selected Breaker actions
remained **31/36**, and the other shared staples showed no meaningful change.
These are off-policy agreement counts, not game outcomes. The experiment
reinforces the current M4 gate: more self-play updates with the present trainer
do not by themselves demonstrate stronger play. Prioritize validated
competitive-card rulings and stronger evaluation opponents before claiming a
training advance.

Reproduce after [native setup](native_setup.md) with `OMP_NUM_THREADS=1`:

```bash
PYTHONPATH=. python scripts/train_self_play.py \
  checkpoints/combat_bc_fv12_15100_15103.pt \
  --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_turbo_riclar_2020.ydk \
            examples/decks/goat_control_lolmarcus_2020.ydk \
  --seed 15600 --games 64 --learning-rate 0.0003 \
  --learner-temperature 2.0 --entropy-coefficient 0.01 \
  --snapshot-every 8 --max-snapshots 8 --max-decisions 3000 \
  --record-dir replays/combat_more_selfplay_15600_15663 \
  --output checkpoints/combat_more_selfplay_15600_15663.pt
PYTHONPATH=. python scripts/evaluate_policy.py \
  checkpoints/combat_more_selfplay_15600_15663.pt \
  --engine experimental --native-root .cache/goat-ai \
  --opponent-checkpoint checkpoints/combat_bc_fv12_15100_15103.pt \
  --both-deck-assignments --require-unseen-main-decks \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --seed 15700 --seeds 8 --max-decisions 3000 --workers 2 \
  --output .cache/goat-ai/combat_more_selfplay_vs_parent_15700_15707.json
```

The ignored local action-audit report is
`.cache/goat-ai/combat_more_selfplay_agreement_15000_15001.json`.

## Opt-in equip-target encoding probe

Schema-v19 Goat Control / Chaos Turbo recordings with CombatHeuristicAgent in
both seats on seeds 16000–16001 produced four replay-verified duels and 1,955
teacher decisions. Of these, 239 had a visible Equip Spell target, including 75
with multiple legal actions. The behavioral-cloning CLI now accepts
replay-fingerprinted v19 through v21 recordings. These exact v19 file hashes were
produced at commit `c65fe41`; current collection writes v21 and may yield
different hashes while preserving the same experiment schedule. With one epoch, width 16, learning rate
0.001, and model seed 16000, feature version 12 ended at loss 0.2695023 and
opt-in version 13 at 0.2692132. Common model layers start at exactly the same
seeded weights; v13 adds a separate trainable equip-pair projection. The
training checkpoints remain ignored local artifacts, with SHA-256 prefixes
`907cea72b56e` (v12) and `640e2e773df1` (v13).

The held-out direct comparison used sourced Chaos Control and Warrior Main
Decks in both deck assignments and both player seats, seeds 16100–16103, with
the 3,000-decision cap. Both Main Deck compositions and all seeds were absent
from training. Version 13 scored **7–9** over 16 terminal games; its paired
bootstrap 95% score interval was **31.25–50%**. The outcome was strongly
deck-dependent: 0–8 with Chaos Control as deck A and 7–1 with Warrior as deck A.
The tournament report is
`.cache/goat-ai/equip_v13_matched_vs_v12_16100_16103.json` (SHA-256 prefix
`c0027a88d86c`). This small result does not establish a strength gain.

Four separately recorded and replay-verified Chaos Control teacher duels on
seeds 16110–16111 gave v12 **615/771** and v13 **616/771** exact agreement on
multi-option choices. In the 152 decisions that both had multiple options and
exposed an Equip Spell target, the two checkpoints chose identically, matching
the teacher on **127/152**. This off-policy audit is not a game-strength
measure. Its report is
`.cache/goat-ai/equip_v12_v13_matched_agreement_16110_16111.json` (SHA-256
prefix `4624de930521`). More training data with meaningful equip choices and
larger held-out tournaments are needed before selecting v13 as the default.
A later pinned-native Snatch Steal / Thousand-Eyes Restrict regression checks that
version 13 binds two Equip Cards in opposite players' Spell/Trap Zones to the
same newly stolen monster slot and scores the resulting legal action set. This
validates the cross-control feature path; it is not playing-strength evidence.

Reproduce the matched experiment after [native setup](native_setup.md):

```bash
PYTHONPATH=. python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher combat_heuristic \
  --deck-a examples/decks/goat_control_lolmarcus_2020.ydk \
  --deck-b examples/decks/chaos_turbo_riclar_2020.ydk \
  --seed 16000 --seeds 2 --max-decisions 3000 \
  --output-dir .cache/goat-ai/equip_v19_demos
PYTHONPATH=. python scripts/train_behavioral_clone.py \
  .cache/goat-ai/equip_v19_demos/*.json --engine experimental \
  --feature-version 12 --epochs 1 --width 16 --seed 16000 \
  --output .cache/goat-ai/equip_v12_16000.pt
PYTHONPATH=. python scripts/train_behavioral_clone.py \
  .cache/goat-ai/equip_v19_demos/*.json --engine experimental \
  --feature-version 13 --epochs 1 --width 16 --seed 16000 \
  --output .cache/goat-ai/equip_v13_matched_16000.pt
PYTHONPATH=. python scripts/evaluate_policy.py \
  .cache/goat-ai/equip_v13_matched_16000.pt \
  --opponent-checkpoint .cache/goat-ai/equip_v12_16000.pt \
  --engine experimental --both-deck-assignments --require-unseen-main-decks \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --seed 16100 --seeds 4 --max-decisions 3000 --workers 2 \
  --output .cache/goat-ai/equip_v13_matched_vs_v12_16100_16103.json
PYTHONPATH=. python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher combat_heuristic \
  --deck-a examples/decks/chaos_control_insids_worlds_2022.ydk \
  --deck-b examples/decks/warrior_montague_clash.ydk \
  --seed 16110 --seeds 2 --max-decisions 3000 \
  --output-dir .cache/goat-ai/equip_v19_holdout
PYTHONPATH=. python scripts/audit_policy_agreement.py \
  --engine experimental \
  --checkpoint .cache/goat-ai/equip_v12_16000.pt \
  --checkpoint .cache/goat-ai/equip_v13_matched_16000.pt \
  --output .cache/goat-ai/equip_v12_v13_matched_agreement_16110_16111.json \
  .cache/goat-ai/equip_v19_holdout/*.json
```

After the observation contract advanced to v20 for face-down Equip Card target
slots, a separate pipeline smoke run recorded two terminal restricted-engine
vanilla duels on seed 16200 (237 and 688 decisions). Their 505 HeuristicAgent
decisions replay-verified during a one-epoch feature-v13 behavioral-cloning run
with width 8 and model seed 16200. The measured epoch loss was 0.3800329. This
checks the v20 collection and training path, not policy strength. The replay
files and checkpoint are ignored under `.cache/goat-ai/v20_smoke_demos` and
`.cache/goat-ai/v20_smoke_policy.pt`.

## Public chain-target policy pipeline check

Opt-in feature version 14 binds schema-v21 public field-target slots to their
active chain links and visible field occupants. A sourced Goat Control versus
Chaos Turbo collection on seed 16300, with CombatHeuristicAgent in each seat
against RandomAgent, produced two terminal replay-verified trajectories of 577
and 432 decisions. Eleven of the 522 teacher decisions had a public chain
target; only one also had multiple legal actions. A one-epoch width-8 clone on
all 522 teacher decisions, with model seed 16300 and learning rate 0.001, had
loss 0.361470660887002. The saved v14 checkpoint loaded and selected a legal
action at a four-option, targeted-chain decision. This checks encoding and
training, not any improvement in competitive strength. The two replay hashes
are `fcdeb7ecb7ee6a121b215564073a6f1bf1f57ff24d0a3b9cbfdb58caefcfcab8`
and `716d0f3d8f79a9d9a3ff0847c2e0d2ec92feb988f07f1a3189159efcabd85ebd`;
the checkpoint hash is
`7eabddb0c2095bf9d9fbb9767deac58f21408bf208f9ff18e09b3ee332a8eb51`.
All three files are ignored under `.cache/goat-ai`.

Reproduce from the repository root with the pinned [native assets](native_setup.md):

```bash
PYTHONPATH=. OMP_NUM_THREADS=1 .venv/bin/python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher combat_heuristic \
  --deck-a examples/decks/goat_control_lolmarcus_2020.ydk \
  --deck-b examples/decks/chaos_turbo_riclar_2020.ydk \
  --seed 16300 --seeds 1 --max-decisions 3000 \
  --output-dir .cache/goat-ai/v21_chain_target_demos
PYTHONPATH=. OMP_NUM_THREADS=1 .venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/v21_chain_target_demos/*.json --engine experimental \
  --feature-version 14 --epochs 1 --width 8 --seed 16300 \
  --output .cache/goat-ai/v21_chain_target_policy.pt
```

## Matched public chain-target feature comparison

A controlled opt-in feature-v13/v14 comparison used eight fresh, schema-v21,
replay-verified CombatHeuristicAgent-versus-RandomAgent duels: Goat Control and
Chaos Turbo in both deck orders, teacher in both seats, seeds 16300–16301. The
8 games had 3,201 teacher decisions. Of those, 108 had an active public chain
target and only 5 also had multiple legal options. Both models used one epoch,
width 16, learning rate 0.001, and seed 16300; their common layers had the
same seeded initialization. Version 14 adds target-slot embeddings and a
chain-link target projection. Epoch losses were 0.2840725670557589 for v13
and 0.2850415981427779 for v14. This training set cannot establish the value
of target-aware decisions given only five relevant multi-option examples.

A direct 32-game tournament on seeds 16400–16403 used sourced Chaos Control
versus Warrior and Chaos Return versus Warrior, both deck assignments and
both seats. Neither evaluation Main Deck composition appeared in training.
Feature v14 scored **16 wins, 15 losses, 1 draw** against v13: 51.6% score,
with matchup-seed paired 95% bootstrap interval 50.0–54.7%. It scored 6–10
when moving first and 10–5 with one draw when moving second. The outcome was
strongly deck-dependent: v14 scored 0–7 with one draw when assigned Chaos
Control against Warrior and 8–0 with Warrior against Chaos Control. A separate
off-policy audit on eight replay-verified Chaos Control/Warrior teacher duels,
seeds 16410–16411 in both deck orders and seats, covered 3,268 teacher
decisions. V13 matched 3,085 overall; v14 matched 3,089. There were 106 targeted-chain decisions, including 10 with multiple legal
options. Both models matched all 10 of those teacher choices. These results do not show a target-specific or competitive strength
gain, so feature v14 remains opt-in.

The v13 and v14 checkpoint SHA-256 hashes are
`6e9468be7371d634a0200ce096d3630e2b90aa7e705719eee72c508159f8bb9b`
and `9172ac6fc565149a3130027adf20d8c83bd91df94de7142e10ba6b3b66634b9f`.
The tournament report hash is
`f987b31b6a50a9a7324fb6d74554afb4c1f70bf0c4550f181ccccc647e42d34a`;
the off-policy audit report hash is
`ccbe7cdf97cfc40fcecc5beaadd87b13cf728e107e8b2b189c38712cd2fe7033`.
These local artifacts are ignored under `.cache/goat-ai/`. The tournament took
24.39 seconds with two workers on the reported machine, measuring 1.31 complete
duels and 596 decisions per second; this is the full policy-vs-policy schedule,
not a standalone simulator throughput benchmark.

To reproduce, use the pinned [native setup](native_setup.md), then run the
collector twice on seeds 16300–16301 with `--engine experimental --teacher
combat_heuristic --seeds 2 --max-decisions 3000`, swapping Goat Control and
Chaos Turbo as `--deck-a` and `--deck-b` and using separate output directories.
Train `scripts/train_behavioral_clone.py` on all eight JSON files with
`--engine experimental --epochs 1 --width 16 --seed 16300
--learning-rate 0.001`, once with `--feature-version 13` and once with
`--feature-version 14`. Evaluate with `scripts/evaluate_policy.py` using
`--opponent-checkpoint` for v13, `--both-deck-assignments`,
`--require-unseen-main-decks`, the two matchups above, `--seed 16400 --seeds 4
--max-decisions 3000 --workers 2`. Collect the two Chaos Control/Warrior deck
orders at seeds 16410–16411 with the same teacher schedule, then pass all
eight JSON files and both checkpoints to `scripts/audit_policy_agreement.py
--engine experimental`. Use `OMP_NUM_THREADS=1` for the measured schedule.

## Behavioral-clone optimizer minibatches

The cloning trainer now accepts `--batch-size N` while keeping the original
per-decision update at the default `N=1`. It still encodes and scores one
variable-length decision at a time, accumulates the mean gradient over `N`
records, and takes one optimizer step per group. This reduces optimizer
updates; it is not batched model inference or GPU collation. A gradient test
matches an explicit two-decision mean-loss update.

On the eight replay-verified sourced Goat Control/Chaos Turbo trajectories from
the matched chain-target comparison, a local one-epoch CPU measurement used
3,201 teacher decisions, width 16, feature version 10, model and shuffle seed
16600, learning rate 0.001, and `OMP_NUM_THREADS=1`. With records already
loaded, batch size 1 took **16.33 s** (196.0 decisions/s; epoch loss
0.2497902); batch size 16 took **9.90 s** (323.4 decisions/s; epoch loss
0.3543973). These losses are from different numbers of optimizer updates and
are not a quality comparison. The CLI also replay-verified two schema-v21
competitive-deck duels and trained a width-8 feature-v14 batch-16 checkpoint
from 522 teacher decisions; its epoch loss was 0.3834609. The checkpoint
loaded with `batch_size=16` and `feature_version=14` metadata. No held-out
strength evaluation was run for that small smoke checkpoint; the matched
comparison below uses a larger training set.

The timing measurement loaded the eight ignored JSON files under
`.cache/goat-ai/v21_chain_target_train_goat_chaos/` and
`.cache/goat-ai/v21_chain_target_train_chaos_goat/` via `read_trajectory` and
`demonstrator_records`, then timed only `fit_behavioral_clone` for batch sizes
1 and 16 with the configuration above. It excludes replay verification,
loading, and checkpoint writing. The CLI smoke used
`--batch-size 16 --feature-version 14 --epochs 1 --width 8 --seed 16600`
on `.cache/goat-ai/v21_chain_target_demos/*.json`, with the experimental
engine and output `.cache/goat-ai/v21_batch16_smoke.pt`.

## Held-out optimizer batch-size comparison

Three feature-v10 behavioral clones used the same eight replay-verified Goat
Control/Chaos Turbo teacher duels (3,201 decisions), model/shuffle seed 16600,
width 16, one epoch, and learning rate 0.001. Only optimizer batch size
changed: 1, 4, or 16. The measured CPU fit time, excluding file loading and
replay verification, was **16.33 s / 196.0 decisions/s** for size 1,
**10.84 s / 295.3 decisions/s** for size 4, and **9.90 s / 323.4
decisions/s** for size 16, with `OMP_NUM_THREADS=1`. Epoch losses were
0.2497902, 0.2983295, and 0.3543973 respectively. Larger batches made
fewer optimizer updates on the same records.

On separate sourced Chaos Control/Warrior and Chaos Return/Warrior Main Decks,
seeds 16610–16613, the both-deck-assignment, seat-swapped direct tests gave
batch size 4 **16–16** against size 1 (50.0% score; matchup-seed paired 95%
bootstrap interval 37.5–62.5%). Batch size 16 scored **12–18 with 2 draws**
against size 1 (40.6%; paired interval 31.3–53.1%). The latter interval still
contains 50%, so this is not a proven strength difference. An independent
replay-verified teacher audit on eight unseen-deck duels at seeds 16410–16411
found exact agreement on **3,135/3,268** decisions for size 1,
**3,096/3,268** for size 4, and **3,037/3,268** for size 16. Among 1,063
decisions with multiple legal actions, the counts were **930**, **891**, and
**832**. All three matched the teacher on the 10 multi-option decisions with
public chain targets. Staple-specific counts are in the ignored audit JSON.
The default remains batch size 1; future experiments should compare compute
budgets, multiple training seeds, and stronger teachers before promoting a
larger batch.

The batch-1, batch-4, and batch-16 checkpoint SHA-256 hashes are respectively
`e08f24ed7239070e88ab940643715610f753fbef928a05624325f21053a152d6`,
`29383276ed9a3314420d8fe14fed7920e6383f714d0a9eb1080d88d947aaea2f`,
and `572b078576a7894b4f2c8e5d7c73c3267a723a1cf7610327d5e20a8a93c33376`.
The size-4 and size-16 tournament report hashes are
`fb8b7806465946c2724e1da63fe4c04612372fd39fd68f972994d5fc67bfe9d7`
and `e3c17ae927da6ff51c4214626247e0a7dd32cb0e44f947d51df8fe8dfc2f44fc`.
All artifacts are ignored under `.cache/goat-ai/`.

Reproduce with the same eight input paths in the previous section. Train each
checkpoint using `scripts/train_behavioral_clone.py` with
`--engine experimental --feature-version 10 --epochs 1 --width 16
--seed 16600 --learning-rate 0.001`, changing only `--batch-size` and the
output path. For each comparison, run `scripts/evaluate_policy.py` with the
larger-batch checkpoint as the first argument, the batch-1 checkpoint as
`--opponent-checkpoint`, `--engine experimental`, `--both-deck-assignments`,
`--require-unseen-main-decks`, the two matchups above,
`--seed 16610 --seeds 4 --max-decisions 3000 --workers 2`. Run
`scripts/audit_policy_agreement.py --engine experimental` with the batch-1
and comparison checkpoints on the eight previously collected Chaos
Control/Warrior trajectories at seeds 16410–16411.

## Opt-in shared-staple decision sampling

The behavioral-cloning CLI now accepts repeated `--focus-card` IDs and a
`--focus-weight`. When the weight exceeds one, it samples with replacement for
the same number of decisions per epoch. A decision qualifies only if it has
multiple legal actions and a focused card is the source of an offered action,
or that card appears in a public chain link. A target card ID alone does not
qualify. The unweighted trainer still shuffles all records once per epoch.
This is an exposure experiment, not a card-specific policy rule.

On the current experimental engine, 16 fresh CombatHeuristicAgent versus
RandomAgent duels on sourced Goat Control and Chaos Turbo Main Decks at seeds
16700–16703 produced 16,866 total decisions and 8,763 teacher decisions.
All 16 trajectories replay-verified before training. Of the teacher decisions,
379 qualified for the ten card IDs shared by the five tournament Main Decks
in `tests/test_policy.py`: Breaker (71413901), Delinquent Duo (44763025),
Snatch Steal (45986603), Pot of Greed (55144522), Nobleman of Crossout
(504700116), Book of Moon (14087893), Black Luster Soldier (504700118), Heavy
Storm (19613556), Ring of Destruction (511000824), and Graceful Charity
(79571449). The two width-16, feature-v12 clones used
the same initialization seed 16700, one epoch, batch size one, and 8,763
optimizer decisions. Only the sampling weight differed: one or four. Their
epoch losses were 0.1681214 and 0.1830156, respectively; losses under
different sampling distributions are not a strength comparison. Checkpoint
SHA-256: `304eb5dbd4d95d9958e9c3d785e5cbbbb37405d8557a9c4199000e36c1b666b3`
and `bd7e5e99eb72786955516d4d2600cfeed8ac86c51cbb53a0719cc0fb86c54047`.

An eight-duel, replay-verified CombatHeuristicAgent audit on unseen Chaos
Control and Warrior Main Decks at seeds 16800–16801 contained 2,728 teacher
decisions. Exact agreement on 947 multi-option decisions rose from 839 to
851; offered-staple agreement rose from 79/86 to 80/86. Teacher-selected
staple agreement stayed 59/63, public staple-chain agreement stayed 108/114,
and multi-option chain-target agreement stayed 14/15. These overlapping
contexts are off-policy diagnostics. In 32 direct games on unseen Chaos
Control, Chaos Return, and Warrior Main Decks at seeds 16810–16813, both deck
assignments and seats, the weighted clone scored **16–16** against the
unweighted clone (50.0%; paired matchup-seed 95% bootstrap interval
37.5–62.5%). The experiment does not establish a playing-strength gain;
focused sampling remains opt-in. The audit and tournament JSON are ignored
local artifacts with SHA-256
`7df56577e11922eb0c252ac452f1f0f98e6ac7f8a9d17fbdee2e9b606aa7868f`
and `c3e06758d9fc8d3bf13e95fd13dcad972c93dac431d9cc524a7e28f0849e5e7b`.

To reproduce, collect the two training deck orders with
`scripts/collect_heuristic_demos.py --engine experimental --teacher
combat_heuristic --seed 16700 --seeds 4 --max-decisions 3000`; collect both
Chaos Control/Warrior orders with seeds 16800–16801 for the separate audit.
Train both checkpoints with `scripts/train_behavioral_clone.py --engine
experimental --feature-version 12 --epochs 1 --width 16 --seed 16700`, adding
`--focus-weight 4` and one `--focus-card` per ID above only to the weighted
run. Audit with `scripts/audit_policy_agreement.py --engine experimental` and
both checkpoints. Run `scripts/evaluate_policy.py` with the weighted checkpoint
against the unweighted `--opponent-checkpoint`, `--engine experimental`,
`--both-deck-assignments`, `--require-unseen-main-decks`, the Chaos
Control/Warrior and Chaos Return/Warrior matchups, `--seed 16810 --seeds 4
--max-decisions 3000 --workers 2`. Use the pinned assets in
[native setup](native_setup.md) and `OMP_NUM_THREADS=1`.

## Six tournament-deck baseline, October 2026

The [six sourced tournament Main Decks](card_priorities.md) form a balanced
baseline schedule for future policies. This is a small project corpus, not an
estimate of historical metagame frequencies or playing strength against
humans. All 15 unordered deck pairs were played in both deck assignments and
both seats. The experimental GOAT-mode adapter, pinned core
`baa3881d0bae48e9994f915f5c931be53c1ba8ef`, and
`--max-decisions 3000` were used. The host was Linux x86_64 on an Intel
Core i7-10700K; the reported wall times measure only the tournament portion
of each script run.

With `CombatHeuristicAgent` as agent A and `HeuristicAgent` as agent B, a
four-worker pilot on seeds 9800–9801 finished 120/120 games: 67 wins, 50
losses, 3 draws for A, or a 57.1% score (paired bootstrap 95% interval
52.9–62.1%). It took 15.69 seconds and 62,651 decisions. Repeating the
identical schedule with one worker produced exactly the same ordered games,
summary, deck hashes, core hashes, and script hashes; its tournament wall time
was 56.44 seconds. The differing JSON files retain their worker counts and
measured runtimes. Their SHA-256 values are respectively
`e33b8699a6b6f1f67332b79e9a91d2fe0ca0ed6eb4f856d5748b4f1837411cd5`
and `c3cd63dbc4c6bb1c174d2ce592ca3f797208c6f6951e02d8da7fe2f0b5618a24`.

A separate four-worker run on seeds 9810–9817 finished 480/480 games under
the same decision cap. A scored **269 wins, 205 losses, and 6 draws**: 56.7%
score, with a paired bootstrap 95% interval of 54.6–59.0%. It took 63.87
seconds for 263,038 decisions (7.52 duels and 4,118 decisions per second in
this run); the longest duel had 2,066 decisions. A scored 60.6% in the first
seat and 52.7% in the second. The report SHA-256 is
`c5ab0708789cd588975ebde80e25a433f62f5e873a19d0f0547cceb15cdfccb6`.
Its source-code fingerprint is
`58d5344601591d2916fe2071ae7e2cfdd728a7d5852aef2e626f94e4395a40f0`
and loaded-card-script fingerprint is
`f886f54c419d3792fd69888d74190c070992609caad8f5737e3f563bd736b71c`.

Agent A's score also varied strongly with its assigned deck, averaged over
all five opposing deck files and both seats: Warrior 81.2% (64–14–2), Goat
Control 76.2% (61–19–0), Bazoo Return 72.5% (58–22–0), Chaos Return 43.8%
(35–45–0), Chaos Turbo 40.0% (31–47–2), and Chaos Control 26.2%
(20–58–2). Each deck has 80 games. The evaluator now includes a `by_deck_a`
summary for this split in future reports; these measured counts were computed
from the saved older report's per-game records because adding the summary did
not change any game. The mixed deck results warrant policy evaluation across
all six archetypes rather than assuming the aggregate gain applies to every
deck. This result supports CombatHeuristicAgent as a provisional baseline or
demonstration teacher, but it does not establish human-level play, historical
correctness of every card, or a learned-policy improvement.

Reproduce the schedules after [native setup](native_setup.md) with:

```bash
PYTHONPATH=. .venv/bin/python scripts/evaluate_native.py \
  --native-root .cache/goat-ai --engine experimental \
  --tournament-corpus --both-deck-assignments \
  --agent-a combat_heuristic --agent-b heuristic \
  --seed 9810 --seeds 8 --workers 4 --max-decisions 3000 \
  --output .cache/goat-ai/competitive-combat-heuristic-9810-9817.json
```

Use `--seed 9800 --seeds 2` for the pilot, and change only `--workers` to
`1` for its deterministic cross-worker check. Generated reports stay in the
ignored `.cache` directory. Later report JSON will include `by_deck_a` and
therefore have a different whole-file hash from the one above, while the
ordered game outcomes should remain the same with the pinned assets and agent
versions.

## Four-tournament-deck combat clone, held-out deck check (2026-10-25)

The balanced six-deck baseline above suggested testing whether broader
imitation data helps a policy generalize. A fresh feature-v12, width-32
behavioral clone used **32 full native duels** of CombatHeuristicAgent version
2 against RandomAgent. The teacher played both seats and both deck orders in
Goat Control versus Chaos Turbo and Warrior versus Bazoo Return, with seeds
17000–17003. The teacher won 29/32 collection games. All **20,031 decisions**
replay-verified before training; the demonstrator-seat filter retained
**10,449 teacher decisions**. Three CPU epochs at learning rate 0.001 and seed
17 gave mean cross-entropies 0.12419, 0.05738, and 0.04456. The ignored local
checkpoint is `checkpoints/combat_fourdeck_fv12_17000_17003.pt`, SHA-256
`1a1ca996a96b680e45e6141fd1634a9f2517787e7f06faaabecddb6c97b2f4a4`.
Its metadata records all input trajectory hashes, four training seeds, four
Main Deck compositions, and the teacher version. These are agent-generated
demonstrations, not human games.

Chaos Control and Chaos Return Main Decks were **excluded from training**.
`--require-unseen-main-decks` rejected any overlapping training composition
before each evaluation. On these two held-out decks, with both deck
assignments and both seats over seeds 17100–17107, the new clone scored
**12–20** against CombatHeuristicAgent (37.5% score; paired 95% interval
21.9–53.1%). The older two-deck clone
`checkpoints/combat_bc_fv12_15100_15103.pt` scored **11–21** on the identical
schedule (34.4%; 21.9–46.9%). The matched score difference was +3.1 points,
with a matchup-seed bootstrap interval from −15.6 to +15.6 points. On fresh
seeds 17120–17135, the new clone scored **34–30 directly** against that older
checkpoint (53.1%; paired interval 46.9–59.4%). None of these intervals
establish a competitive gain. The direct-match deck split was 13–19 with
Chaos Control and 21–11 with Chaos Return, so even the small aggregate lead
was not uniform across held-out decks.

A separate off-policy audit used four fresh CombatHeuristicAgent v2 versus
RandomAgent duels on those same held-out deck files, with seed 17200 in both
deck orders and teacher seats. All 4,067 recorded decisions replay-verified;
2,082 were teacher decisions. Among 718 with multiple legal actions, the new
clone matched 687 exact choices versus 682 for the older clone. Its offered
staple decisions matched one additional Nobleman of Crossout and one additional
Ring of Destruction choice; the other eight shared-staple offered counts were
identical in this small audit. This measures agreement with a heuristic, not
optimal play. The audit report SHA-256 is
`f5a9b7b6a43257241984ad9e28235df96633ad00bccf22c680036ff8907346f0`.

The three ignored tournament JSON SHA-256 values, in the order new versus
teacher, older versus teacher, and new versus older, are
`caa906dd0579801f7c80662332dc18d1d44fcee04373d0cffb94707ca8905baf`,
`96c34f2b36c24c0021f62f65689a8afb653dc72355ecb6a4961d3b2650bcadaf`,
and `3409d8c4012021dbf8db8b21423b754e034db1ad5aecda872be1bf304db84dfc`.
The experimental GOAT-mode adapter and pinned assets were used throughout.
The older checkpoint lacks explicit teacher-version metadata and differs in
training deck diversity and decision count, so the head-to-head comparison
does not isolate any one cause. This experiment does not meet M4's held-out
strength gate or establish a self-play gain.

Reproduce the collection from the repository root with pinned native
assets. The four pair labels fix the input order and saved paths:

```bash
for entry in \
  goat_control_lolmarcus_2020:chaos_turbo_riclar_2020:gc_ct \
  chaos_turbo_riclar_2020:goat_control_lolmarcus_2020:ct_gc \
  warrior_montague_clash:bazoo_return_weirdchamp_worlds:war_baz \
  bazoo_return_weirdchamp_worlds:warrior_montague_clash:baz_war; do
  IFS=: read -r deck_a deck_b label <<< "$entry"
  for start in 17000 17002; do
    end=$((start + 1))
    PYTHONPATH=. OMP_NUM_THREADS=1 .venv/bin/python \
      scripts/collect_heuristic_demos.py \
      --native-root .cache/goat-ai --engine experimental \
      --teacher combat_heuristic --max-decisions 3000 \
      --deck-a "examples/decks/$deck_a.ydk" \
      --deck-b "examples/decks/$deck_b.ydk" \
      --seed "$start" --seeds 2 \
      --output-dir "replays/combat_fourdeck_${label}_${start}_${end}"
  done
done
```

Train all resulting JSON files with:

```bash
PYTHONPATH=. OMP_NUM_THREADS=1 .venv/bin/python \
  scripts/train_behavioral_clone.py \
  replays/combat_fourdeck_{baz_war,ct_gc,gc_ct,war_baz}_{17000_17001,17002_17003}/*.json \
  --native-root .cache/goat-ai --engine experimental \
  --output checkpoints/combat_fourdeck_fv12_17000_17003.pt \
  --epochs 3 --width 32 --feature-version 12 --learning-rate 0.001 --seed 17
```

Run `scripts/evaluate_policy.py` with the Chaos Control/Chaos Return matchup,
`--both-deck-assignments --require-unseen-main-decks --max-decisions 3000`,
seeds 17100–17107 against `--opponent combat_heuristic` for each checkpoint,
then seeds 17120–17135 with the new checkpoint against
`--opponent-checkpoint` pointing to the older one. Run
`scripts/audit_policy_agreement.py` on the fresh seed-17200 trajectories with
both `--checkpoint` flags for the off-policy diagnostic. Generated data and
checkpoints remain ignored by Git.
## Public occupancy feature ablation (2026-10-25)

Feature version 15 adds twelve public zone and pile counts to the state
encoder. The hypothesis was that the previous average-card pooling loses
board size, which matters for common cards such as Torrential Tribute,
Mirror Force, and Heavy Storm. The feature is opt-in; the default and
existing v12 checkpoint format are unchanged. This experiment compares the
new version against the four-deck feature-v12 clone described above; v15
also includes the v13 equip and v14 chain-target features, so the result
cannot isolate the twelve counts alone.

The v15 width-32 clone used the same 32 replay-verified training duels,
10,449 CombatHeuristicAgent v2 demonstrator decisions, three epochs,
learning rate 0.001, and seed 17 as the v12 clone. Mean training losses were
0.12071, 0.05784, and 0.04262. Its ignored checkpoint
`checkpoints/combat_fourdeck_fv15_17000_17003.pt` has SHA-256
`c3d71929213b37dd293635a117a8c9cb77894252c7e4fe1aaea2eead5d802035`.
These are agent-generated demonstrations, not human gameplay.

Four held-out Chaos Control/Chaos Return teacher trajectories, seed 17200,
replay-verified **4,067 decisions**, including 718 teacher decisions with
multiple legal actions. V15 matched **681/718** exact choices versus
**687/718** for v12. The agreement report SHA-256 is
`347fb25dc7aeb1beb21c3b73ba26aa309c7b5e10e41a01aed6b375540c46a08d`.

On unseen Chaos Control and Chaos Return Main Decks, with both deck
assignments and both seats over seeds 17300–17307, v15 scored **13–18–1**
directly against v12: a 42.2% score with a paired 95% bootstrap interval
of **34.4–50.0%**. Its first-seat score was 12.5% and second-seat score
71.9%, underscoring how uneven this small evaluation remains. The 32-game
single-process run took 54.49 seconds on the recorded x86_64 CPU, with
17,209 decisions. The report SHA-256 is
`cdc2fdbfa914d919cebe7cda98f32f80875ab298d4a70d279afd8b97f85f6abe`.
This is a negative pilot for adopting v15; it neither proves the counts
harm strength in general nor meets the M4 competitive-policy exit.

Reproduce with pinned assets and the existing local trajectories:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  replays/combat_fourdeck_{baz_war,ct_gc,gc_ct,war_baz}_{17000_17001,17002_17003}/*.json \
  --native-root .cache/goat-ai --engine experimental \
  --output checkpoints/combat_fourdeck_fv15_17000_17003.pt \
  --epochs 3 --width 32 --feature-version 15 --learning-rate 0.001 --seed 17
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/audit_policy_agreement.py \
  --checkpoint checkpoints/combat_fourdeck_fv15_17000_17003.pt \
  --checkpoint checkpoints/combat_fourdeck_fv12_17000_17003.pt \
  --native-root .cache/goat-ai --engine experimental \
  --output .cache/goat-ai/combat_fourdeck_fv15_vs_v12_agreement_17200.json \
  replays/combat_fourdeck_holdout_{cc_cr,cr_cc}_17200/*.json
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/evaluate_policy.py \
  checkpoints/combat_fourdeck_fv15_17000_17003.pt \
  --native-root .cache/goat-ai --engine experimental \
  --opponent-checkpoint checkpoints/combat_fourdeck_fv12_17000_17003.pt \
  --both-deck-assignments --require-unseen-main-decks \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
    examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --seed 17300 --seeds 8 --max-decisions 3000 \
  --output .cache/goat-ai/combat_fourdeck_fv15_vs_v12_17300_17307.json
```

## Visible combat-margin policy experiment (2026-10-25)

An audit of the four-deck v12 clone's 31 held-out multi-option mistakes found
ten Battle Phase decisions where it attacked but the CombatHeuristicAgent v2
teacher moved to Main Phase 2. Each offered attack had a negative margin
against all visible opposing monsters, including Sheep Token attacks. The
new opt-in feature version 16 branches from v12 and supplies each attack
action with its source ATK, its margin against the weakest visible opposing
battle stat, a complete-visibility bit, and an empty-opposing-field bit. A
hidden opponent monster suppresses the numeric margin. All inputs are from
the player-visible observation and legal action. V16 deliberately excludes
the unrelated v13–v15 experiments; version 10 remains the default.

A width-32 v16 clone trained on the **same 32 replay-verified duels and
10,449 CombatHeuristicAgent v2 decisions** as the v12 four-deck clone, using
three CPU epochs, learning rate 0.001, and seed 17. Mean training losses
were 0.12346, 0.05122, and 0.03360. The ignored local checkpoint is
`checkpoints/combat_fourdeck_fv16_17000_17003.pt`, SHA-256
`684133751518a6d59f3acc99d59134a82e421a79957fc0a2e28e5e11bce1a5b1`.
The demonstrations are generated by a heuristic, not collected from humans.

The four held-out Chaos Control/Chaos Return seed-17200 teacher trajectories
replay-verified 4,067 decisions. On the 718 multi-option teacher decisions,
v16 matched **689** exact choices versus v12's **687**. The specific
attack-versus-Main-2 error fell from **10 to 3**. The off-policy report
SHA-256 is
`29628df27b6f051c592c3503b6dcec6799d19c2972d931d94613d12575384fad`.
This diagnostic does not measure playing strength.

On unseen Chaos Control and Chaos Return Main Decks, both deck assignments
and both seats, v16 beat v12 **24–8** over seeds 17400–17407 (75.0%, paired
95% interval 53.1–93.8%; report SHA-256
`781da2b43a723826f11e0e293927a55450cf47d9c7d7e9148d3a7f3cadb5c5a7`).
A matched 64-game teacher comparison on seeds 17500–17515 gave v16
**35–29** and v12 **25–38–1**. The paired v16-minus-v12 score difference
was **+14.8 percentage points** with a matchup-seed bootstrap interval of
**+4.7 to +25.0 points**. The two teacher-report hashes are
`38b550dfcfae3fb0c4321967877e0cfe80511c3d6dea696294e5dd07b506899d`
and `6b234fb5d696f5c89e571a2adaca9c8095f1750da4c867f3ab0b5481a3be3dfb`.

An independent 128-game direct match on seeds 17900–17931 reproduced an
aggregate v16 advantage over v12: **79–48–1**, a 62.1% score with paired
95% interval **56.6–67.6%**. Chaos Control split 29–34–1 while Chaos Return
split 50–14, so the gain was not uniform across held-out decks. The
two-worker run took 117.94 seconds; report SHA-256 is
`5e3468c64a47ea3e6cf5513a6dc618f2595ae1d0d5fdb452b3e6ecc835ade287`.

A larger, predeclared 256-game combat-teacher run on independent seeds
17600–17663 scored **139–114–3** (54.9%; paired 95% interval **49.2–60.4%**).
Chaos Control scored 60–66–2 (47.7%), while Chaos Return scored 79–48–1
(62.1%). The two-worker run took 171.66 seconds on the recorded x86_64 CPU;
report SHA-256 is
`3c178708351a708f7375c45b042097dbf00bae96cac2839a5462ede8f425d038`.
Thus this schedule does not establish an absolute advantage over the stronger
combat baseline or balanced strength across the two held-out archetypes.

On separate seeds 17700–17731, 128 games per opponent, v16 scored
**81–46–1 against HeuristicAgent** (63.7%, paired interval 56.2–71.1%;
report SHA-256 `ddb4d67936ce8e62e2c61b9a0875f23e375eb7d6a720ccd54cf5fd669d81a9a0`)
and **86–41–1 against RandomAgent** (67.6%, paired interval 59.8–75.0%;
report SHA-256 `39195d8c71a890281e5ab3eb4181341be2947c6c50376a47090d8c5b40658ec9`).
All evaluation Main Deck compositions were excluded from training with
`--require-unseen-main-decks`. These measured baseline gains are narrower
than the M4 objective: stronger combat play, more held-out deck families,
and a self-play improvement still need evidence.

Reproduce training and the held-out action audit with the v15 commands above,
substituting `--feature-version 16` and the v16 checkpoint path. For the
native evaluations use `scripts/evaluate_policy.py` with
`--engine experimental --both-deck-assignments --require-unseen-main-decks`,
the Chaos Control/Chaos Return matchup above, and the exact seed ranges,
opponents, worker counts, and output names stated here. The report JSONs
record the checkpoint and native-asset fingerprints, deck hashes, platform,
individual games, and confidence intervals. Checkpoints, trajectories, and
reports stay outside Git.

For the two larger competitive checks, run:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/evaluate_policy.py \
  checkpoints/combat_fourdeck_fv16_17000_17003.pt \
  --native-root .cache/goat-ai --engine experimental \
  --opponent combat_heuristic --both-deck-assignments \
  --require-unseen-main-decks \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
    examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --seed 17600 --seeds 64 --workers 2 --max-decisions 3000 \
  --output .cache/goat-ai/combat_fourdeck_fv16_vs_teacher_17600_17663.json
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/evaluate_policy.py \
  checkpoints/combat_fourdeck_fv16_17000_17003.pt \
  --native-root .cache/goat-ai --engine experimental \
  --opponent-checkpoint checkpoints/combat_fourdeck_fv12_17000_17003.pt \
  --both-deck-assignments --require-unseen-main-decks \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
    examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --seed 17900 --seeds 32 --workers 2 --max-decisions 3000 \
  --output .cache/goat-ai/combat_fourdeck_fv16_vs_v12_17900_17931.json
```

## Feature-v16 self-play continuation (2026-10-25)

The snapshot-pool trainer now has an opt-in `--skip-capped-games` mode. A duel
that reaches `--max-decisions` is recorded as `decision_limit`, receives no
reward label or gradient update, produces no trajectory, and is excluded from
the child checkpoint's training-game provenance. It is not a draw. The default
still raises an error so a capped game cannot silently enter an experiment.

Starting from the v16 checkpoint above, a 64-seed continuation used the four
training Main Decks (Goat Control, Chaos Turbo, Warrior, Bazoo Return), both
learner seats, temperature 2, learning rate 0.0003, entropy coefficient 0.01,
and a 10,000-decision cap. **62 games terminated** (36 learner wins, 26 losses);
seeds 18248 and 18252 were censored at the cap. The terminal games contain
51,401 decisions, all replay-verified against the pinned experimental core;
6,938 learner decisions had legal alternatives for policy updates. The
longest terminal game had 8,842 decisions. The child checkpoint SHA-256 is
`add7930ab17798df4445a742f1315bc893d60bf999ce9962e1f3980edd81e074`;
the training report SHA-256 is
`bcbfe0c76495923262946844dc314230a41ef7db2b729d4bc21f0bbe66a05a1a`.
The high cap and two censored games show that this policy can produce very long
duels; the training win fraction is conditional on termination and is not an
evaluation score.

On fresh seeds 18300–18331, both assignments and seats of held-out Chaos
Control and Chaos Return, the child scored **62–66** directly against its v16
parent (48.4%, matchup-seed paired 95% interval **45.3–51.6%**). It scored
22–42 with Chaos Control and 40–24 with Chaos Return. All 128 evaluation
duels terminated under 3,000 decisions; the four-worker tournament took
64.06 seconds on the recorded CPU. The report SHA-256 is
`8eb5c23c5fca48a99efa633f16b77349d8f5989cc9a1a8650b81294083724458`.
Exact Main Deck composition and seed gates excluded the training games from
evaluation. This update does not demonstrate a self-play strength gain or fix
the Chaos Control weakness.

Reproduce training with this command, then use `scripts/evaluate_policy.py`
with the parent checkpoint as `--opponent-checkpoint` and
`--both-deck-assignments --require-unseen-main-decks --seed 18300 --seeds 32
--workers 4 --max-decisions 3000` on the held-out Chaos Control/Chaos Return
pair. The reports include the exact deck and native-asset fingerprints.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  checkpoints/combat_fourdeck_fv16_17000_17003.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
    examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_turbo_riclar_2020.ydk \
    examples/decks/goat_control_lolmarcus_2020.ydk \
  --matchup examples/decks/warrior_montague_clash.ydk \
    examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/bazoo_return_weirdchamp_worlds.ydk \
    examples/decks/warrior_montague_clash.ydk \
  --seed 18200 --games 64 --learning-rate 0.0003 \
  --learner-temperature 2.0 --entropy-coefficient 0.01 \
  --max-decisions 10000 --skip-capped-games \
  --record-dir replays/combat_fv16_selfplay_18200_18263 \
  --output checkpoints/combat_fv16_selfplay_18200_18263.pt
```

## Tournament-trajectory legal-choice visibility audit (2026-10-25)

The read-only `scripts/audit_trajectory_visibility.py` checks schema-v17-or-newer
decision records against each acting player's visible field and known opponent
hand. A choice targeting an opposing face-down field slot must omit card ID and
dynamic stats; a face-up field choice's ID must match the visible card; a
choice naming an opponent hand card must name an already known card and omit
the native hand slot. Within one grouped or staged action, the number of named
copies cannot exceed the known hand multiset; separate legal alternatives are
checked independently. The audit also checks actor and viewer agreement.

```bash
PYTHONPATH=src:. .venv/bin/python scripts/audit_trajectory_visibility.py \
  replays/tournament_verified_18500
```

On the 30 locally saved, previously replay-verified sourced-tournament duels,
the audit passed **16,979 decisions**, including **583 opponent-field target
choices**, **55 face-down opposing field choices**, and **13 opponent-hand
choices**. The directory contains schema-v21 trajectories. Counts refer to
legal choices, so multiple offered targets at one decision are counted
separately. This checks the stated action/observation invariants over those
recordings; it does not prove hidden-state noninterference or historical
correctness for every card. The native differential tests remain necessary.
A paired Nobleman regression now swaps two unknown opponent monster identities
between field slots and verifies that its full observation and both target
choices are unchanged at the decision boundary; see [GOAT rules](goat_rules.md).
A complementary Mystical Space Typhoon differential swaps Set Solemn Judgment
and Book of Moon between two backrow slots and finds the same observation and
target choices. The native queries confirm both underlying swaps.

The audit also passed all **128 locally saved schema-v21 trajectories** found
under `replays/`: **92,478 decisions**, **3,016 opponent-field choices**, **569
opposing face-down field choices**, and **234 opponent-hand choices**. Reproduce
the wider audit with:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/audit_trajectory_visibility.py \
  --schema 21 replays
```

Older trajectory schemas are excluded by this command because the known-hand
field needed for the hand-choice check was added in schema v17. This remains a
recorded-choice audit, not proof that arbitrary hidden-state changes cannot
influence all future observations or action ordering.

## Attack-target observation and feature-v17 pilot (2026-10-25)

Schema v22 now records the acting player's **own attacker field slot** at the
attack-target prompt. It is derived from that player's preceding legal attack
action and is absent at other decisions. Opt-in policy feature v17 uses that
slot to pair the attacker's public ATK with each candidate target's visible
ATK or DEF. A face-down target contributes no hidden battle stat. The default
policy feature remains v10; the evaluated v16 checkpoint is unchanged.

The original four-deck CombatHeuristicAgent v2 training schedule was replayed
on the pinned core with seeds 17000–17003 and both teacher seats. All **32**
schema-v22 duels matched the earlier recordings in selected action sequence,
decision count, and result: **20,031 decisions** in all, including **154
multi-option attack-target prompts**. The teacher supplied **10,449** training
decisions. A width-32 v17 clone trained for three CPU epochs at learning rate
0.001 and seed 17; mean losses were 0.12618, 0.05376, and 0.03646. Its ignored
checkpoint SHA-256 is
`f2584edd823d054c23c2f08fe49307b049fa8b7b9edf8611866ee4a3d6941deb`.
The data are synthetic teacher demonstrations, not human gameplay.

Four regenerated held-out Chaos Control/Chaos Return teacher duels at seed
17200 replay-verified **4,067 decisions**. On the **16** teacher attack-target
choices, v17 matched 15 and v16 matched 13. Across all 718 multi-option
teacher choices, v17 matched 687 and v16 matched 689. The agreement report
SHA-256 is
`329f37ebc292218fad163e0e94187b6019e4f5be6a31d437fe87f9eaaf44693f`.
These small action counts are diagnostic, not evidence of stronger play.

The predeclared direct match used held-out seeds 18400–18431, both deck
assignments and seats, and exact Main Deck composition exclusion from training.
V17 scored **68–59–1** against v16 over **128 terminal games** (53.5% score;
matchup-seed paired 95% bootstrap interval **48.4–58.2%**). Chaos Control
scored 28–36; Chaos Return scored 40–23–1. The four-worker CPU tournament took
73.85 seconds; report SHA-256 is
`515c14db598a9dc725fb494bf7ef7ef99fde8d1c69d7694e789995d5eca53a95`.
The interval crosses 50% and the Chaos Control split worsened, so this pilot
does not establish a competitive gain or close M4. It does establish that the
previously omitted attacker context reaches the policy without hidden state.

Reproduce the v22 collection with `scripts/collect_heuristic_demos.py` using
the four deck orders and seeds in the earlier four-deck collection command,
writing to separate ignored directories. Train with
`scripts/train_behavioral_clone.py --feature-version 17 --width 32 --epochs 3
--learning-rate 0.001 --seed 17`; v17 requires schema-v22 input. Run the
off-policy audit on both checkpoints and the four regenerated seed-17200
trajectories. For the direct match, run `scripts/evaluate_policy.py` with the
v17 checkpoint, `--opponent-checkpoint` pointing to the v16 checkpoint,
`--engine experimental --both-deck-assignments --require-unseen-main-decks`,
the Chaos Control/Chaos Return matchup, `--seed 18400 --seeds 32 --workers 4`,
and `--max-decisions 3000`. Generated trajectories, checkpoints, and reports
remain ignored outside Git.

## Combat teacher target-prompt correction (2026-10-25)

An audit of the schema-v22 CombatHeuristicAgent v2 recordings found that the
agent applied its visible-stat target preference only in `battle_step`.
Ocgcore requested most attack targets in `battle_start`, so those choices
fell through to the generic first-legal-action preference. Of 127 training
attack-target prompts, 113 occurred in `battle_start` and 14 in
`battle_step`; the held-out split was 14 and 2 of 16. Replaying those exact
observations through the corrected teacher changes 26/127 training and 8/16
held-out target choices. These are off-policy differences, not game wins.

CombatHeuristicAgent teacher version 3 uses the schema-v22 acting player's
own attacker slot in either phase, while retaining the earlier in-memory
fallback for older observation schemas. The teacher still uses only public
field stats and treats face-down targets as unknown. Earlier v2 recordings
and model comparisons retain their v2 provenance; newly collected v3 data
must be kept separate.

For a direct diagnostic, v3 played the committed v2 implementation on the
experimental native adapter. The schedule used seeds 701–708, both seats,
both deck assignments, and two sourced pairings: Chaos Control versus Goat
Control, and Chaos Return versus Warrior. Across 64 terminal games v3 scored
**32–30–2** (51.6%; matchup-seed paired bootstrap 95% interval
**46.9–56.2%**). This small comparison does not establish stronger play.
The correction is retained because the target rule now executes at the
documented prompt and the selected action uses only visible information.

## Competitive-deck combat-teacher v3 clone pilot (2026-10-25)

To test the corrected teacher on cards found in sourced GOAT lists, the
four-deck v2 collection schedule above was rerun with CombatHeuristicAgent
v3: Goat Control/Chaos Turbo and Warrior/Bazoo Return in both deck orders,
seeds 17000–17003, and both teacher seats. The experimental native adapter
replayed and verified all **32** complete schema-v22 duels: **19,483** total
decisions, **10,164** teacher decisions, and **118** multi-option attack-target
choices. The teacher won 28/32 collection games; v2 had won 29/32 on the
same schedule. Collection wins against RandomAgent do not establish a better
teacher. The v3 trajectories are ignored under
`.cache/goat-ai/combat_v3_17000_17003/`, separate from the v2 recordings.

A width-32 feature-v17 clone used the same three CPU epochs, learning rate
0.001, and initialization seed 17 as the v2 feature-v17 pilot. Mean losses
were 0.12108, 0.05110, and 0.03322. The ignored checkpoint is
`checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt`, SHA-256
`63f300c568a2270510210cf7bd919b94c4519480270caadd7d6890316b807023`.
Its metadata records version-3 teacher provenance and trajectory hashes.
These are synthetic demonstrations, not human decisions.

Four new held-out v3 teacher duels on Chaos Control/Chaos Return in both
orders and seats at seed 17200 replay-verified **3,432** decisions, including
1,770 teacher decisions and 611 multi-option teacher choices. The v3 clone
matched **593/611** multi-option choices and **16/16** attack-target choices;
the previously trained v2 feature-v17 clone matched **581/611** and **11/16**
on those *same* v3 decisions. This is off-policy teacher agreement, not
playing strength. The agreement report SHA-256 is
`7ec439096dd6187f8c2e80d9acbd52ddf8193c2889ffa68c9391937db9294efb`.

In a held-out direct match on seeds 18450–18481, both Chaos Control/Chaos
Return deck assignments and both seats, the v3 clone scored **72–56** against
the v2 feature-v17 clone over **128 terminal games** (56.25% score; paired
matchup-seed bootstrap 95% interval **49.2–62.5%**). Its Chaos Control split
was **27–37** and its Chaos Return split **45–19**. The four-worker tournament
took 64.55 seconds on the host described in the report; its ignored JSON
SHA-256 is
`d67d93478f6433161f130d1b6550e831a3341eff915731eae09b5a3dbc8f88a7`.
The interval crosses 50% and the deck split is uneven, so this does not
establish a cross-deck strength gain or satisfy M4.

Reproduce collection with the four deck orders in the command above,
`--teacher combat_heuristic --seed 17000 --seeds 4 --engine experimental`,
writing to a distinct v3 directory. Run `scripts/verify_trajectory.py
--experimental` on every resulting JSON before training. Train with
`scripts/train_behavioral_clone.py --engine experimental --feature-version
17 --width 32 --epochs 3 --learning-rate 0.001 --seed 17`. Audit the separate
held-out v3 recordings with `scripts/audit_policy_agreement.py` and both
feature-v17 checkpoints. Run `scripts/evaluate_policy.py` with the v3
checkpoint, `--opponent-checkpoint` set to the v2 feature-v17 checkpoint,
`--engine experimental --both-deck-assignments --require-unseen-main-decks`,
the Chaos Control/Chaos Return matchup, `--seed 18450 --seeds 32 --workers 4`,
and `--max-decisions 3000`.

## Return selection boundary and v3 self-play continuation (2026-10-25)

A 64-game, four-deck snapshot-pool continuation from the v3 feature-v17
clone initially stopped at seed 18855. The native `MSG_SELECT_CARD` request
offered **3,003** combinations, above the adapter's 2,048-choice guard.
Inspection of the reproduced seed-18855 decision identified Return from the
Different Dimension (`27174286`) at turn 45: five cards were selected from
15 eligible cards in the acting player's public banished pile. The public
action parameters contain banished-card IDs and slots, not private Deck order.
At the time, the decoder permitted up to 4,096 combinations, with a synthetic
3,003-way decoder regression and an explicit rejection above the bound. This extends
coverage for a card defining the sourced Bazoo Return decks; larger
combinatorial selections required further work at the time of this pilot.

The trainer also has opt-in `--skip-unsupported-games`. It records a native
protocol failure with seed, decks, opponent, and error while withholding a
terminal reward, gradient update, trajectory, and training-game provenance.
The default still raises immediately. This option is for preserving other
experimental episodes when an unaudited request appears; a skipped game is
not evidence of a complete duel.

Rerunning seeds 18800–18863 with the raised bound and the explicit skip
options completed **64/64 terminal duels**, with zero unsupported or capped
episodes. All **44,056** recorded decisions in the 64 saved schema-v22
trajectories replay-verified against fresh pinned native instances. The
learner made 6,666 multi-option decisions and went 37–27 against its training
pool of frozen snapshots and RandomAgent.
The first 55 trajectory JSON files were byte-identical to those saved before
the decoder stopped; the new bound changed the outcome only after that
previously unsupported prompt.
The separate read-only visibility audit passed all 44,056 decisions,
including 1,709 opponent-field choice entries, 338 face-down opponent-field
entries, and 132 opponent-hand choice entries. This checks recorded action
redaction invariants, not every possible hidden-state counterfactual.

Training used the four ordered
Goat Control/Chaos Turbo and Warrior/Bazoo Return pairings, both learner
seats, temperature 2.0, learning rate 0.0001, historical opponent probability
0.75, one snapshot every four games, up to eight snapshots, entropy weight
0.001, and a 3,000-decision cap. The ignored child checkpoint SHA-256 is
`9e8797d11cdb711c204dcd77e20a1cc146dfc8de989d4f29b66deb1e62143a91`;
the training report SHA-256 is
`ef37c7efc91b066d89d3294e0b11efe5ca5b9ebc6802af4a450eecf869d3f24c`.

On held-out seeds 18900–18931 with both assignments and seats for unseen
Chaos Control/Chaos Return Main Decks, the child scored **64–62–2** directly
against its parent over **128 terminal games** (50.8% score; matchup-seed
paired bootstrap 95% interval **50.0–52.3%**). It scored 28–35–1 when
assigned Chaos Control and 36–27–1 with Chaos Return. The four-worker
tournament took 76.37 seconds; ignored report SHA-256 is
`c1576e64b481301dcc481ed203864f5985c1463a48b4eb8f6059283e672fd4e7`.
The interval includes 50%, and the two deck splits disagree; this does not
establish a self-play gain or close M4. The earlier aborted run produced no
child checkpoint and is excluded from these results.

Reproduce with `scripts/train_self_play.py` from the v3 feature-v17 parent,
`--engine experimental --seed 18800 --games 64 --max-decisions 3000
--skip-capped-games --skip-unsupported-games --learner-temperature 2.0`, the
four ordered pairings above, and the other parameters in this section.
Verify every saved trajectory using `scripts/verify_trajectory.py
--experimental`. Run `scripts/evaluate_policy.py` against the parent with
`--engine experimental --both-deck-assignments --require-unseen-main-decks`,
the Chaos Control/Chaos Return matchup, `--seed 18900 --seeds 32 --workers 4`,
and `--max-decisions 3000`.

## Staged native card selection beyond the flat action bound (2026-10-25)

`MSG_SELECT_CARD` requests with more than 4,096 complete combinations now
expose at most one `select_card` action per remaining card, rather than
materializing every subset. The selected-card prefix appears only in the
acting player's legal-action parameters. The adapter offers
`finish_selection` once the native minimum is met, automatically submits at
the maximum, and validates the exact canonical response before passing it
to ocgcore. The core performs the card effect; the Python adapter only
collects a legal native choice. Other bounded request types, such as tribute
selection and card sorting, are unchanged.

With the flat threshold forced to one combination, a native Graceful
Charity fixture selected two hand cards in separate decisions, completed
a duel, serialized it, and replay-verified the full trajectory. Three
native GOAT Thunder Dragon branches chose zero, one, or two Deck copies
through staged actions. Each branch produced the same next observation
and legal actions as the corresponding flat native selection. A local
read-only replay of the seed-18855 Return game, with the threshold lowered
to 2,048, followed 958 unchanged recorded decisions to the 3,003-way
prompt. Selecting the same five public banished cards in stages produced
the exact next observation and legal actions from the original complete
choice. The remaining recorded decisions also matched through the terminal
result: 1,021 original decisions plus four extra staged decisions, with
the same winner. The saved Return trajectory is ignored and is not a
committed test fixture. The affected native and visibility suites passed
**37/37** tests, plus **59/59** probe, query, and policy tests.
The visibility audit now checks selected-card prefixes on staged actions;
broader counterfactual hidden-state checks remain separate M1 work.

## Tournament replay and visibility recheck (2026-10-25)

The seed-28500 [six-tournament-deck schedule](competitive_action_coverage.md)
was rerun with trajectory recording and replay verification enabled. All 30
seat-swapped duels completed, and a fresh pinned engine matched every one of
their **18,283 decisions** through the terminal result. The 30 schema-v22
JSON trajectories total 149,437,757 bytes in the ignored native cache; they
are not committed. The generated report's SHA-256 is
`c95f495143a2b2e45a6b9e15dc73260302808a6ef9ea104e3c4204db039a2a83`.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/probe_competitive_card_actions.py \
  --native-root .cache/goat-ai --tournament-corpus --seed 28500 --seeds 1 \
  --agent combat_heuristic --max-decisions 3000 --verify-replays \
  --record-dir .cache/goat-ai/tournament_card_audit_28500_replays \
  --output .cache/goat-ai/tournament_card_audit_28500_verified.json \
  > .cache/goat-ai/tournament_card_audit_28500_verified.stdout
PYTHONPATH=src:. .venv/bin/python scripts/audit_trajectory_visibility.py \
  .cache/goat-ai/tournament_card_audit_28500_replays
```

The read-only visibility audit passed all 18,283 decisions and checked 671
offered opposing field choices, including 106 face-down slots, plus 22
opposing hand choices. The auditor now also checks single and grouped Tribute
choices; a focused regression verifies that a grouped Tribute payload cannot
name a hidden opposing monster. This sample contained no opposing Tribute
choice, so the aggregate counts did not change when that check was added.
The hand-choice audit also now checks multiplicity within each legal action:
one known copy cannot justify a two-copy grouped selection or a staged prefix
plus candidate. Reauditing these 30 trajectories gave the same counts above;
the duplicate-copy case has a focused regression. The wider saved schema-v21
set also passed this stricter audit: 128 trajectories, 92,478 decisions,
3,016 opposing field choices, 569 face-down opposing field choices, and 234
opposing hand choices. This is the same set and count reported in the earlier
visibility-audit section.
Replay equivalence establishes reproducibility for these pinned assets and
seeds; the action audit enforces its listed selection invariants. Neither
establishes historical correctness or general hidden-state noninterference.

## Doubling combat-teacher v3 demonstrations (2026-10-25)

The feature-v17 v3 clone above missed several held-out card selections,
including repeated Metamorphosis Tribute choices. To test whether more
ordinary competitive-deck demonstrations would help, four ordered training
matchups (Goat Control/Chaos Turbo and Warrior/Bazoo Return, each in both
orders) were collected again on seeds 17004–17007 with CombatHeuristicAgent
v3 against RandomAgent in both teacher seats. The 32 additional terminal
duels contain **22,164** decisions and **11,635** labeled teacher decisions.
The read-only visibility audit passed all 32, including 231 hidden-field
choices and 67 opponent-hand choices. The collector labels these as synthetic
heuristic demonstrations, not authorized human play.

A matched width-32 feature-v17 clone was initialized with seed 17 and trained
for three CPU epochs at learning rate 0.001 on the original and additional
records. The training CLI replay-verified all **64** fingerprinted duels
(41,647 decisions) before fitting the **21,799** teacher decisions from four
training Main Deck compositions. Mean training losses were 0.09234, 0.03859,
and 0.02814. The ignored checkpoint is
`checkpoints/combat_fourdeck_fv17_v3_17000_17007.pt`, SHA-256
`66c311d17b833fd06381e26d3383ac667bc3fdf7281b78228dd6d21f0abf2263`.

On the same four replay-verified held-out seed-17200 teacher duels used above,
the enlarged clone matched **595/611** multi-option teacher choices versus
**593/611** for the original v3 clone. It matched **77/89** multi-option chain
choices versus **73/89**. These are off-policy agreement counts, not playing
strength; the paired agreement report SHA-256 is
`1d920871c16005bba86ae2634b18715c6bc373d8f93a96ae8a89419006176f13`.

On fresh seeds 19050–19081, unseen Chaos Control and Chaos Return Main Decks,
both deck assignments, and both policy seats, the enlarged clone scored
**57–68–3** against the original over 128 terminal games: **45.7%** score,
with a paired bootstrap 95% interval of **40.6–50.8%**. It scored 16–46–2
when assigned Chaos Control and 41–22–1 with Chaos Return. The four-worker
match took 63.86 seconds on the hardware recorded in the report; the ignored
JSON SHA-256 is
`2d629a58bb38254cadafd562c435b7316f807e83eb6715c7cdaf4826524951bb`.
The interval includes 50% and the deck splits diverge. More demonstrations
from the same four training decks did **not** establish a general strength
gain. Keep the smaller v3 clone as the reference and investigate source-aware
target choices and cross-deck evaluation before promoting another model.

Reproduce collection and evaluation with:

```bash
while read -r matchup_name deck_one deck_two; do
  OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_heuristic_demos.py \
    --native-root .cache/goat-ai --engine experimental \
    --teacher combat_heuristic \
    --deck-a "examples/decks/$deck_one" --deck-b "examples/decks/$deck_two" \
    --seed 17004 --seeds 4 --max-decisions 3000 \
    --output-dir ".cache/goat-ai/combat_v3_extra_17004_17007/$matchup_name"
done <<'MATCHUPS'
gc_ct goat_control_lolmarcus_2020.ydk chaos_turbo_riclar_2020.ydk
ct_gc chaos_turbo_riclar_2020.ydk goat_control_lolmarcus_2020.ydk
war_baz warrior_montague_clash.ydk bazoo_return_weirdchamp_worlds.ydk
baz_war bazoo_return_weirdchamp_worlds.ydk warrior_montague_clash.ydk
MATCHUPS
PYTHONPATH=src:. .venv/bin/python scripts/audit_trajectory_visibility.py \
  .cache/goat-ai/combat_v3_extra_17004_17007
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/combat_v3_17000_17003/*/*.json \
  .cache/goat-ai/combat_v3_extra_17004_17007/*/*.json \
  --native-root .cache/goat-ai --engine experimental \
  --output checkpoints/combat_fourdeck_fv17_v3_17000_17007.pt \
  --epochs 3 --width 32 --feature-version 17 --learning-rate 0.001 --seed 17
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/audit_policy_agreement.py \
  --checkpoint checkpoints/combat_fourdeck_fv17_v3_17000_17007.pt \
  --checkpoint checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt \
  --native-root .cache/goat-ai --engine experimental \
  .cache/goat-ai/combat_v3_heldout_17200/*/*.json
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/evaluate_policy.py \
  checkpoints/combat_fourdeck_fv17_v3_17000_17007.pt \
  --opponent-checkpoint checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt \
  --native-root .cache/goat-ai --engine experimental \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
  examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 19050 --seeds 32 --workers 4 --max-decisions 3000
```

## Thunder Dragon zero-search policy decision (2026-10-25)

The native GOAT Thunder Dragon prompt offers a legal `cancel` response that
resolves as a zero-copy search. Policy inference version 2 always overrode
`cancel`, even when the model ranked it highest. The two held-out Thunder
Dragon prompts in the replay-verified seed-17200 teacher sample exposed this:
both saved feature-v17 checkpoints scored `cancel` highest, while the wrapper
selected a Deck copy. Version 3 permits the first cancellation at a distinct
player-visible prompt and uses the best non-cancel action if that same prompt
recurs. The guard ignores history text and transient action IDs but compares
the visible state and legal choices; it keeps only 64 prompts per turn.

On the same 611 multi-option held-out teacher decisions, the 32-duel parent
checkpoint now agrees on **595/611** (previously 593/611) and the 64-duel
clone on **597/611** (previously 595/611). Both recovered decisions are
Thunder Dragon zero-search choices. A seeded native fixture confirms that
`cancel` and explicit empty selection both leave the two Deck copies in
place and reveal nothing. An eight-duel experimental-engine smoke run of the
parent checkpoint against CombatHeuristicAgent on unseen Chaos Control and
Chaos Return Main Decks, seeds 19100–19101 with both deck assignments and
seats, completed all games under 3,000 decisions and scored **3–5–0**. The
sample is too small to estimate a strength change. The machine-readable
report is stored locally at
`.cache/goat-ai/thunder_cancel_inference_v3_eval.json` and is not committed.

## Chain-source/target feature pilot (2026-10-25)

The 32-duel feature-v17 combat clone missed a Metamorphosis Tribute choice
and a later Chaos Sorcerer target choice in the held-out Chaos Control game:
both teacher actions selected Thousand-Eyes Restrict, while the policy chose
Kycoo. Feature version 18 adds an opt-in learned pair between the last
player-visible chain card and each candidate action card. It retains v17's
schema-v22 combat inputs and does not read native hidden state. When no chain
is present, the pair contributes nothing. The same 32 replay-verified
synthetic teacher duels, width 32, seed 17, three epochs, and learning rate
0.001 were used to isolate the feature. All **10,164** teacher decisions were
verified before fitting. The ignored checkpoint is
`checkpoints/combat_fourdeck_fv18_v3_17000_17003.pt`, SHA-256
`cc8481c00a538f0b13934ccf5079f08f9d61e4df278b1e188685605f1f026600`.
Its epoch losses were 0.11968, 0.04905, and 0.03572.

On four replay-verified held-out teacher duels (seed 17200), v18 matched
**591/611** multi-option actions and **72/89** multi-option chain actions.
The matched v17 checkpoint under inference version 3 matched **595/611** and
**75/89**. V18 did not recover either motivating Thousand-Eyes Restrict
choice. The ignored agreement report SHA-256 is
`1ba568854a51f1d8c7d81efc77c7f9ec309e1a572f9df7cd788daca71381758d`.

On fresh seeds 19200–19215 with unseen Chaos Control and Chaos Return Main
Decks, both deck assignments, and both seats, v18 scored **34–29–1** directly
against v17 over **64 terminal duels**: 53.9% score with a paired bootstrap
95% interval of 47.7–60.9%. Its split was 14–18–0 as Chaos Control and
20–11–1 as Chaos Return. This interval includes 50%; the pilot does not
establish a strength gain. The ignored match report SHA-256 is
`e09bd5745047b258677689d171a8ed8f9a41bbbe63022cc87e953a965f594735`.
V18 remains an opt-in experiment; v17 remains the reference checkpoint.

Reproduce the pilot with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/combat_v3_17000_17003/*/*.json \
  --native-root .cache/goat-ai --engine experimental \
  --output checkpoints/combat_fourdeck_fv18_v3_17000_17003.pt \
  --epochs 3 --width 32 --feature-version 18 --learning-rate 0.001 --seed 17
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/audit_policy_agreement.py \
  --checkpoint checkpoints/combat_fourdeck_fv18_v3_17000_17003.pt \
  --checkpoint checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt \
  --native-root .cache/goat-ai --engine experimental \
  .cache/goat-ai/combat_v3_heldout_17200/*/*.json
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/evaluate_policy.py \
  checkpoints/combat_fourdeck_fv18_v3_17000_17003.pt \
  --opponent-checkpoint checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt \
  --native-root .cache/goat-ai --engine experimental \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
  examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 19200 --seeds 16 --workers 4 --max-decisions 3000
```

## Matched combat-clone self-play learning-rate pilot (2026-10-25)

To test whether small updates explained the earlier self-play plateau, two
feature-v17 children started from the same 32-duel combat clone (SHA-256
`63f300c568a2270510210cf7bd919b94c4519480270caadd7d6890316b807023`).
Both used the same four ordered Goat Control/Chaos Turbo and Warrior/Bazoo
Return matchups, seeds 19300–19331, both learner seats, snapshot probability
0.75, temperature 2, entropy coefficient 0.001, and 3,000-decision cap. Only
the learning rate differed: **0.001** versus **0.0001**. Because policy weights
change after each game, their later sampled games diverged despite matching
seeds; training win counts are therefore not a paired strength comparison.

At rate 0.001, all **32** games terminated (17–15 against the training pool),
and a fresh pinned engine replay-verified **19,958** recorded decisions. The
visibility audit passed all decisions, including 129 hidden opposing field
choices and 51 opposing hand choices. The child checkpoint SHA-256 is
`7b6f2b1036e58e26e81709f284b879a51a916a6ae218d4ac6a0b1e3d6aaa72a7`.
At rate 0.0001, all **32** games terminated (20–12 against its diverged pool),
and **20,829** decisions replay-verified. Its visibility audit passed,
including 124 hidden opposing field choices and 45 opposing hand choices.
That child SHA-256 is
`b40adcad805418da5b4ecf8aea5bdd9546877573c6a175e465d0494d3e35219b`.
The ignored training-output SHA-256 values are respectively
`f18c5210bd696b415e7592cd82e425cd645853349f8130eeda4edad4ccd6d937`
and `dd879bb8254bdbf16b899c08736098b9f45effee86effac0563f774831f62914`.

On four replay-verified held-out teacher duels (seed 17200), both children
and their parent matched **595/611** multi-option choices and **75/89** chain
choices. The higher-rate child changed four greedy choices: it recovered two
Thousand-Eyes Restrict choices under Metamorphosis and Chaos Sorcerer, but
regressed on two other targets. The lower-rate child changed none. The
agreement report SHA-256 is
`d8f3fb70ec435f490a1a36a6c181e1a3b14ca67faa9ad9d7ac5e7cd38ce4377d`.

On fresh unseen Chaos Control/Chaos Return Main Decks, seeds 19400–19415 with
both deck assignments and policy seats, **each child scored 32–32** against
the parent over 64 terminal games. The higher-rate child's paired 95% score
interval was 43.8–56.3%; its split was 10–22 as Chaos Control and 22–10 as
Chaos Return. The lower-rate split was 11–21 and 21–11. On separate fresh
seeds 19500–19515, the higher-rate child also split **32–32** directly with
the lower-rate child on that Chaos pair. On a second unseen, whitelist-legal
guide-deck matchup, Flip Control versus Dimension Fusion Turbo, seeds
19600–19615, the higher-rate child scored **32–30–2** against the lower-rate
child (51.6%; paired 95% interval 44.5–58.6%). Those guide lists are not
tournament submissions. The four ignored evaluation report SHA-256 values,
in the same order, are
`1376504e6dabc92b723b3626d9732d152f2637b2e10bb11204a0ada5be350237`,
`892f3afd8fb3a2780fed48bd3e12d394abe22485085039a960dc8c5d3ed3ba36`,
`1a492935f319644f8c2b12220afad0e9ce34e128552e35f4ca74b99a58c0228d`,
and `8fcab9a7847490a7e90e3d9fdf76f115861194395e1ea17ebb4a424bc472757b`.
No tested schedule establishes a self-play strength gain. Increasing the
learning rate alone produced a few offsetting held-out choice changes and did
not solve the deck-assignment imbalance. The original clone remains the
reference checkpoint.

Reproduce both training runs by setting `rate` to `0.001` and `0.0001` in
turn; use a distinct output and record directory for each:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/goat_control_lolmarcus_2020.ydk \
  --matchup examples/decks/warrior_montague_clash.ydk examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/bazoo_return_weirdchamp_worlds.ydk examples/decks/warrior_montague_clash.ydk \
  --seed 19300 --games 32 --learning-rate "$rate" --learner-temperature 2 \
  --entropy-coefficient 0.001 --max-decisions 3000 \
  --record-dir ".cache/goat-ai/combat_v3_sp_${rate}_19300_19331" \
  --output "checkpoints/combat_v3_sp_${rate}_19300_19331.pt"
```

Run `scripts/verify_trajectory.py --experimental` on each saved JSON,
`scripts/audit_trajectory_visibility.py` on each record directory, then
`scripts/audit_policy_agreement.py` on the seed-17200 holdout. The direct
matches used `scripts/evaluate_policy.py` with `--engine experimental`,
`--both-deck-assignments`, `--require-unseen-main-decks`, `--seeds 16`,
`--workers 4`, and `--max-decisions 3000`, with the seeds and matchups above.

## Experimental Flip-type combat teacher

The opt-in `CombatFlipHeuristicAgent` reads only a known card's public Flip
type from the pinned card databases. It prefers an offered Flip Summon of a
Flip monster before other actions, and uses the existing type-aware Set
preference. The default `CombatHeuristicAgent` remains version 3; this
candidate is version 1. It does not use deck-specific card scripts or the
simulator's hidden state.

On seed 9700's fixed three-pair, both-seat sourced-deck schedule, the
candidate's six complete duels selected Dekoichi Flip Summon 5 times versus
the baseline's 1, and Magician of Faith Flip Summon 6 times versus 0. The
candidate selected Dekoichi Set 13 times versus 0. All six candidate duels
(4,681 decisions) and six baseline duels (3,534 decisions) serialized and
replay-verified against fresh native engines. Their ignored report SHA-256
values are
`f1ee74dd3f10a9337f7b4502095d6a2427e7f66af1c7bde979771ae64d65bbd5`
and
`881ffca7fc48a3ee950e29e8c254f5b213e975a80995d2da71bcb53c56d6aae8`.
The trajectories differ in length, so these action counts establish behavior
coverage, not a controlled win-rate effect.

In a held-out paired tournament against combat version 3, seeds 11600–11603
on Goat Control/Chaos Turbo and Chaos Control/Chaos Return with both deck
assignments and agent seats, the candidate scored **14–17–1** in 32 complete
games (45.3%; paired 95% score interval 31.3–60.9%). Its splits were 4–3–1
as Goat Control, 2–6 as Chaos Turbo, 5–3 as Chaos Control, and 3–5 as Chaos
Return. The report records two workers, 26,998 decisions, pinned native asset
hashes, deck hashes, and source hash
`521d0940bc57d923c8bbe534f16ce1f20e8281f0bd30c682f0cbaf26972fedad`;
its ignored JSON SHA-256 is
`08bcc896e59e9c8ec70bfaa635c3d6a0579e867fc4ab07f370413e5485e98f54`.
The JSON digest identifies this local report; wall-clock fields mean an exact
byte-for-byte digest is not expected on another run. Game outcomes and
schedules are deterministic under the pinned assets and seed. This pilot does
not establish a competitive improvement. Keep the original
combat teacher as the default and do not use the candidate as a training
teacher without a stronger held-out result.

Reproduce the paired match after [native setup](native_setup.md):

```bash
PYTHONPATH=src:. .venv/bin/python scripts/evaluate_native.py \
  --engine experimental --agent-a combat_flip --agent-b combat_heuristic \
  --both-deck-assignments \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --seed 11600 --seeds 4 --max-decisions 3000 --workers 2 \
  --output .cache/goat-ai/combat-flip-pilot-11600.json
```

For the action probe, use `scripts/probe_competitive_card_actions.py` with
`--agent combat_flip` and again with `--agent combat_heuristic`, both with
`--seed 9700 --seeds 1 --verify-replays` and separate `--record-dir` and
`--output` paths.

## Deck-attributed policy agreement on six tournament decks (2026-10-25)

The policy agreement audit now attributes each recorded decision to the
acting player's deck, including trajectories where both seats are
demonstrators. Previously those decisions were grouped under `both seats`,
which hid deck-specific errors. The corrected audit replay-verified all
30 [heuristic corpus trajectories](competitive_action_coverage.md), then
compared the existing combat-teacher feature-v12 clone (checkpoint SHA-256
`5d78f23fb13f82efc63aee106e1c4d8812e6b65a3fe5d469333e5aad0504b2b4`)
against those basic-heuristic choices. Its exact agreement on decisions with
multiple legal actions was **4,059/4,323** overall:

| Acting Main Deck | Exact / multi-option decisions |
| --- | ---: |
| Goat Control | 892 / 921 |
| Chaos Turbo | 660 / 688 |
| Chaos Control | 807 / 861 |
| Bazoo Return | 681 / 721 |
| Chaos Return | 551 / 608 |
| Warrior | 468 / 524 |

The saved audit report's SHA-256 is
`4bc4a37cec9197db3d67ecbf32b8f86f8924c1f51de6a0f9c9f2513fb549c8c3`.
Reproduce it with the ignored checkpoint and replay files:

```bash
OMP_NUM_THREADS=1 .venv/bin/python -m scripts.audit_policy_agreement \
  --checkpoint checkpoints/combat_bc_fv12_11000_11001.pt \
  --native-root .cache/goat-ai --engine experimental \
  --output /tmp/goat_policy_by_deck_19600.json \
  /tmp/goat_heuristic_replays_19600/*.json \
  > /tmp/goat_policy_by_deck_19600.stdout
```

These are choices by a different, weaker heuristic than the combat teacher
used to train the checkpoint. Agreement cannot establish competitive
strength, and the denominator varies by deck. The lower Warrior and Chaos
Return agreement identifies where to inspect decision classes and collect
stronger, source-backed demonstrations before another model comparison.

For high-play cards, the audit also counts decisions where the basic heuristic
selected a card-source action. The clone exactly matched Heavy Storm in 19/32
such decisions, Breaker the Magical Warrior in 89/100, Book of Moon in 85/92,
Snatch Steal in 30/34, Black Luster Soldier in 23/25, and Nobleman of Crossout
in 49/50. It matched all 18 Delinquent Duo, 26 Pot of Greed, 21 Graceful
Charity, and 51 Ring of Destruction selections. Heavy Storm and Breaker have
the most observed disagreements in this corpus and are the next decision
classes to inspect. These counts do not distinguish mistakes by the clone
from mistakes by the heuristic.

A follow-up audit records the clone's alternative action kind and deduplicates
*exact* visible decisions (observation, legal actions, and heuristic choice).
It replay-verified the same 30 duels; the detailed report SHA-256 is
`8d15fc78e96338fbd07ec12c821554cd1a3a075089a39a0193b5fc8bac4e7489`.
Heavy Storm had 8 mismatches among 21 distinct activation demonstrations:
the clone chose another activation twice, Normal Summon four times, Flip
Summon once, and Special Summon once. Its 5 raw Set-action mismatches represent
3 distinct demonstrations; all clone alternatives were different Set cards.
For Breaker, 6 of 27 attack demonstrations disagreed: four times the clone
went to Main Phase 2 and twice it chose a different attacker. Four of 17
position-change demonstrations also disagreed. All 21 Breaker chain responses
matched, so that class is a lower priority for policy work in this sample.
Exact deduplication removes repeated states but does not make the remaining
decisions statistically independent. Inspect Heavy Storm activation timing and
Breaker combat choices on held-out decks before changing training weights;
neither agent's choice is treated as ground truth for strategic quality.

### Checking the stronger combat model before retraining

The same 30 trajectories were replay-verified against both the older
feature-v12 clone and the saved four-deck feature-v16 combat clone. The report
SHA-256 is
`fc669b666c3e53318b83f7f9892d26b357111d4b7203c94844e814bcbae214d7`.
On the two Main Decks absent from **both** checkpoints' training games, exact
agreement with the basic heuristic was:

| Selected card and acting deck | v12 | v16 |
| --- | ---: | ---: |
| Heavy Storm, Chaos Control | 6/11 | 6/11 |
| Heavy Storm, Chaos Return | 2/5 | 5/5 |
| Breaker, Chaos Control | 2/2 | 2/2 |
| Breaker, Chaos Return | 18/21 | 20/21 |

Across all six decks, the v16 clone matched 23/25 Heavy Storm activations
versus 17/25 for v12, and 25/27 Breaker attacks versus 21/27. It matched all
17 Breaker position changes versus v12's 13/17. The remaining five Heavy
Storm Set mismatches repeat a Chaos Control opening in which the basic
heuristic Sets Storm while both clones Set another Trap; they are only three
distinct exact demonstrations. This evidence gives no reason to train toward
those Set choices. The checkpoints differ in training data and architecture,
so the comparison cannot attribute any difference to the feature version.
It is an off-policy diagnostic, not a competitive strength result.

```bash
OMP_NUM_THREADS=1 .venv/bin/python -m scripts.audit_policy_agreement \
  --checkpoint checkpoints/combat_bc_fv12_11000_11001.pt \
  --checkpoint checkpoints/combat_fourdeck_fv16_17000_17003.pt \
  --native-root .cache/goat-ai --engine experimental \
  --staple-code 19613556 --staple-code 71413901 \
  --output /tmp/goat_policy_v12_v16_by_deck_19600.json \
  /tmp/goat_heuristic_replays_19600/*.json \
  > /tmp/goat_policy_v12_v16_by_deck_19600.stdout
```

## Per-deck self-play reward baseline pilot (2026-10-25)

The snapshot-pool trainer now has an opt-in `--baseline-scope learner_deck`.
Its exponential terminal-reward baseline is tracked by the learner's deck
path; `global` retains the previous single-baseline behavior. A matched
pilot started both children from feature-v17 combat teacher v3 checkpoint
`combat_fourdeck_fv17_v3_17000_17003.pt`. Each used the same four ordered
Goat Control/Chaos Turbo and Warrior/Bazoo Return matchups, seeds
19700–19731, learning rate 0.001, learner temperature 2, entropy coefficient
0.001, and 3,000-decision cap. The only configuration difference was baseline
scope. All 32 games in each run terminated. All 32 complete
sampled trajectories were byte-identical between runs, though the final model
weights differed. Both runs scored 17–15 against their evolving training
pools; that count is not a strength evaluation.

All 64 saved trajectories and **42,544** decisions replay-verified against
fresh pinned native engines. The visibility audit passed, covering 250 hidden
opposing field choices and 144 opposing hand choices. Its report SHA-256 is
`9cd9564636ba969f4a9ab7d7f483d33e00b9b5d0b5661139046573e5061313c7`.
The global child checkpoint SHA-256 is
`edaa0364def2cbac5e7562f1d791dbd3b9d6e016963075fae25caac1e0983ad6`;
the deck-baseline child's is
`741e33cc9304f85872e7d01b1036608ed8b25fa10283e475d4b607a5bc7bb78b`.

On unseen Chaos Control and Chaos Return Main Decks, 16 fresh seeds with both
deck assignments and both agent seats gave the deck-baseline child **31–31–2**
directly against the global child (report SHA-256
`51b50cd298b2012ad1c08869558ecdfd3a8dacb32bfcaff4b94953d142cf9bb2`).
On another 16-seed held-out schedule, **both** children scored **35–28–1**
against the parent, with identical winners and duel lengths in all 64 paired
games. Their paired 95% score interval was 49.2–61.7%, including 50%.
The deck-baseline child's assigned-deck scores were 12–19–1 as Chaos Control
and 23–9 as Chaos Return. The parent-comparison report SHA-256 values are
`f9a57e77d85c7c554fd3d76834e4f54e0e639d873cc4b9b523c7fe3bfba2e941`
for deck baseline and
`b0b17034ea5f734665d0b1a3a230773d6af5bd0e367716be9ad656e3dc5c21dc`
for global baseline. This pilot does not show a gain from per-deck reward
centering or meet the M4 self-play exit gate. The opt-in switch remains for
further controlled experiments; neither child replaces the parent.

Reproduce each training run by setting `scope` to `global` and `learner_deck`
in turn:

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_self_play.py \
  checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/goat_control_lolmarcus_2020.ydk \
  --matchup examples/decks/warrior_montague_clash.ydk examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/bazoo_return_weirdchamp_worlds.ydk examples/decks/warrior_montague_clash.ydk \
  --seed 19700 --games 32 --learning-rate 0.001 --learner-temperature 2 \
  --entropy-coefficient 0.001 --max-decisions 3000 \
  --baseline-scope "$scope" \
  --record-dir ".cache/goat-ai/combat_baseline_${scope}_19700" \
  --output "checkpoints/combat_baseline_${scope}_19700.pt"
```

The direct and parent comparisons used `scripts/evaluate_policy.py` with
`--engine experimental`, `--both-deck-assignments`,
`--require-unseen-main-decks`, `--workers 4`, `--seeds 16`, and
`--max-decisions 3000`, the Chaos Control/Chaos Return
matchup, and seeds 19800 and 19850 respectively. Both checkpoints passed the
Main Deck composition exclusion gate. The reported score intervals and
throughput apply only to those schedules and pinned assets.

## Self-play demonstration-seat correction (2026-10-25)

The saved `self_play_rl` trajectories used `skill_metadata.learner_seat`,
whereas the behavioral-cloning selector previously recognized only
`demonstrator_seat`. If those files had been reused for cloning, it would
have labeled both the learner and the opponent's moves as demonstrations.
The selector now uses the learner seat for legacy `self_play_rl` files,
requires valid seat metadata, and rejects conflicting seat fields. New
self-play recordings carry both fields. The policy-agreement audit and cloning
checkpoint provenance use the same resolved seat.

Across the two 32-game baseline-pilot recording directories above, the
corrected selector returned **21,604 learner decisions** from **42,544**
replay-verified total decisions and excluded **20,940 opponent decisions**.
The old selector would have returned all 42,544. A fresh native self-play
smoke duel recorded `learner_seat=demonstrator_seat=0`, replay-verified all
1,063 decisions, and selected 578 learner labels. A cloning CLI smoke run on
one legacy file replay-verified 1,261 decisions and fitted only its 669
learner decisions; the saved checkpoint recorded demonstrator seat 0.
Inspection of saved checkpoints found no behavioral-cloning checkpoint whose
training-game provenance lists `self_play_rl`; existing RL continuations
already updated from their in-memory learner-only decision records. This
corrects a future data-ingestion hazard and does not itself change any
previous competitive result.

## Local retrospective decision-label pipeline (2026-10-25)

The offline replay viewer now lets a reviewer select one of the displayed
legal actions and download an authorized label file tied to the source JSON's
byte SHA-256. The behavioral-cloning CLI accepts one annotation file per
trajectory, replay-verifies the complete source, audits visible choices, and
trains only the selected legal labels. It rejects altered source bytes,
invalid indexes, duplicates, and missing self-recorded authorization.
Generated standalone HTML embeds the source SHA-256; opening a JSON file in
the viewer hashes it locally in the browser. No replay or label is uploaded.
A headless Chromium check clicked a legal action in rendered
`replays/scapegoat_3.json` and exported a schema-v1 label with the exact
source hash `5bdcca3951f9b9cf6f80d96344fcf7be9ed2aa747e0dbee12646fa8b109ec2a6`.

A native integration smoke used the existing seed-19700 competitive-deck
self-play trajectory (1,261 replay-verified decisions). A locally generated
test label chose an offered Breaker Normal Summon at decision index 2 instead
of the recorded action. The CLI trained exactly **one** decision, marked its
source `human_annotation`, and saved the test reviewer, authorization, and
annotation SHA-256 in the ignored checkpoint. The label file SHA-256 was
`079a3704ba8e8daa8def43de5005300dcceb38e18e07f50c0d7bee83226ff483`;
the smoke checkpoint SHA-256 was
`69def39fa5b705a3f63808d9178bf944018a17d4e2962fbb4b03678817150dd2`.
This is a pipeline test with a synthetic label, not an authorized expert
dataset or a measured policy gain.

## Contemporary 2005 deck protocol check

The [Matt Peddle SJC Indianapolis 2005 deck](../examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk) transcribes the published 40-card Main Deck and 16-card Fusion Deck with pinned GOAT/pre-errata variant IDs; the published Side Deck is omitted. The [source transcription and event link](card_priorities.md) remain separate from the six later-GOAT tournament decks. A source-name and whitelist test covers the full playable fixture. One seed-2070 random-agent duel against the 2020 Goat Control example reaches terminal, serializes, replay-verifies, and passes the trajectory visibility audit.

The experimental adapter also ran the two deck assignments, seeds 20050–20051, and both seats: **8/8 terminal duels**, 9,368 decisions, maximum 1,355 decisions in a duel. Sequential wall time was **10.90 seconds** on Linux x86_64 (**0.73 duels/s**, **859 decisions/s**). Both agents were RandomAgent; the 4–4 agent-A split measures neither deck strength nor historical correctness of every effect. The ignored report `artifacts/indianapolis_2005_vs_2020_random_20050_20051.json` contains individual results and asset/deck hashes. Reproduce it with:

```bash
PYTHONPATH=src:. .venv/bin/python -m scripts.evaluate_native \
  --engine experimental \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
            examples/decks/goat_control_lolmarcus_2020.ydk \
  --both-deck-assignments --seed 20050 --seeds 2 --max-decisions 3000 \
  --output artifacts/indianapolis_2005_vs_2020_random_20050_20051.json
```

The second exact published fixture, [Michael Fukuyama's 2005 deck](../examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk), has a 40-card Main Deck and 19-card Fusion Deck with source-name and whitelist tests. It contains D.D. Designator, whose native name prompt uses `NOT ISTYPE(TYPE_EXTRA)`. The adapter now offers pinned historical card names other than Fusion and other Extra Deck names; an integration test checks that Book of Moon and D.D. Designator are choices while Thousand-Eyes Restrict is not. The seeded complete duel that first exposed this prompt now replay-verifies and passes the visibility audit. Controlled correct-name and wrong-name duels additionally test the subsequent recipient-scoped hand reveal and banishment outcomes. The catalog remains bounded by the pinned GOAT whitelist and does not prove every historically declarable printed name.

The two 2005 decks then played both assignments, both seats, and seeds 2072–2073 under RandomAgent: **8/8 terminal duels**, 8,332 decisions, maximum 1,377 decisions. Sequential wall time was **9.84 seconds** on Linux x86_64 (**0.81 duels/s**, **847 decisions/s**). Agent A split 4–4; this is protocol coverage, not a deck-strength estimate. The ignored report `artifacts/indianapolis_2005_peddle_fukuyama_random_2072_2073.json` stores game outcomes and pinned hashes. Reproduce it with:

```bash
PYTHONPATH=src:. .venv/bin/python -m scripts.evaluate_native \
  --engine experimental \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
            examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --both-deck-assignments --seed 2072 --seeds 2 --max-decisions 3000 \
  --output artifacts/indianapolis_2005_peddle_fukuyama_random_2072_2073.json
```

The [Daryl Gessler Gravekeeper fixture](../examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk) preserves its published 42-card Main Deck and three-card Fusion Deck. Forty-two Main Deck cards are legal; no padding or trimming was applied. Source-name and whitelist tests cover every ID, and a seeded duel against Matt Peddle's deck reaches terminal, replay-verifies, and passes the visibility audit.

One seed (2080), all three unordered 2005 deck pairings, both deck assignments, and both seats yielded **12/12 terminal random-agent duels** under the 3,000-decision cap. They used 13,102 decisions, at most 1,327 in a duel. Sequential wall time was **15.60 seconds** on Linux x86_64 (**0.77 duels/s**, **840 decisions/s**). Agent A split 6–6 by symmetric design; this measures protocol reach, not card-specific correctness or deck strength. The ignored report `artifacts/indianapolis_2005_three_decks_random_2080.json` stores all games and hashes. Reproduce it with:

```bash
PYTHONPATH=src:. .venv/bin/python -m scripts.evaluate_native \
  --engine experimental \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
            examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
            examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --matchup examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
            examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --both-deck-assignments --seed 2080 --seeds 1 --max-decisions 3000 \
  --output artifacts/indianapolis_2005_three_decks_random_2080.json
```

The [Jesse Twohig 2005 deck](../examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk) preserves the published 42-card Main Deck and 23-card Fusion Deck. The historical Main Deck minimum is satisfied without padding. Source-name and pinned whitelist tests cover every Main and Fusion ID; a seeded duel against Daryl Gessler's deck reaches terminal, serializes, replay-verifies, and passes the visibility audit. Juan Cardenas's printed list totals only 38 Main Deck cards and remains in the source corpus without an invented executable version.

With RandomAgent on both sides, Jesse's deck versus Matt Peddle's and Daryl Gessler's decks, seeds 2100–2102 in both seats, completed **12/12 terminal duels** under the 3,000-decision cap. They used **13,110 decisions**, with a maximum of **1,392** in one duel. Sequential wall time was **15.39 seconds** on Linux x86_64 (**0.780 duels/s**, **852 decisions/s**). Jesse's assigned random agent won 7 and lost 5; these outcomes measure protocol reach, not deck strength or full historical correctness. The ignored report `artifacts/jesse_2005_protocol_3seeds.json` stores game outcomes and pinned hashes. Reproduce it with:

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/python scripts/evaluate_native.py \
  --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --agent-a random --agent-b random --seed 2100 --seeds 3 \
  --max-decisions 3000 --output artifacts/jesse_2005_protocol_3seeds.json
```

The [Cas Stomphorst 2005 Flip Control deck](../examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk) preserves the published 40-card Main Deck and 51-card Fusion Deck. The large Fusion Deck is printed in the historical source and is legal under the project's pinned historical deck validator; no modern 15-card Extra Deck limit was imposed. Source-name and pinned whitelist tests cover every ID. A seeded full duel against Jesse Twohig's deck reaches terminal, serializes, replay-verifies, and passes the visibility audit.

With RandomAgent on both sides, Cas's deck versus Jesse Twohig's and Daryl Gessler's decks, seeds 2110–2112 in both seats, completed **12/12 terminal duels** under the 3,000-decision cap. They used **10,983 decisions**, with a maximum of **1,400** in one duel. Sequential wall time was **14.85 seconds** on Linux x86_64 (**0.808 duels/s**, **740 decisions/s**). Cas's assigned random agent won 3 and lost 9; this is protocol coverage, not a deck-strength or historical-rules estimate. The ignored report `artifacts/cas_2005_protocol_3seeds.json` stores outcomes and pinned hashes. Reproduce it with:

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/python scripts/evaluate_native.py \
  --engine experimental \
  --matchup examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk \
            examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
  --matchup examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk \
            examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --agent-a random --agent-b random --seed 2110 --seeds 3 \
  --max-decisions 3000 --output artifacts/cas_2005_protocol_3seeds.json
```

## Held-out policy check on contemporary 2005 decks

The feature-v17 CombatHeuristicAgent v3 clone `checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt` (SHA-256 `63f300c568a2270510210cf7bd919b94c4519480270caadd7d6890316b807023`) was evaluated on the published Jesse–Cas and Matt–Daryl 2005 pairings, both deck assignments, both seats, and seeds 2120–2123. The evaluator rejected overlaps with its training seeds, exact YDK bytes, and Main Deck compositions. On the pinned experimental GOAT native adapter, the policy scored **14–18** against CombatHeuristicAgent v3 (43.75%, paired 95% bootstrap interval **31.25–56.25%**) over 32 games and 24,695 decisions in 52.17 seconds. Its assigned-deck splits were Cas 2–6, Jesse 5–3, Matt 4–4, and Daryl 3–5. The ignored report is `artifacts/fv17_v3_vs_combat_2005_2120_2123.json`.

On the same deck/seed schedule, the ordinary HeuristicAgent scored **15–17** against CombatHeuristicAgent v3 (46.88%, paired interval **37.5–56.25%**). A direct feature-v17-versus-HeuristicAgent match scored **17–15** (53.13%, paired interval **37.5–68.75%**) over 32 games and 22,570 decisions in 55.30 seconds. The policy's direct assigned-deck splits were Cas 1–7, Jesse 7–1, Matt 4–4, and Daryl 5–3. All three intervals include 50%, and the small deck-specific samples cannot establish a competitive gain or satisfy M4. Identical agents playing Cas against Jesse on seeds 2120–2123 scored **1–7** for Cas, so the policy's Cas split alone is weak evidence of a policy-specific defect.

Four fresh Cas-versus-Jesse CombatHeuristicAgent v3 demonstration duels on held-out seeds 2130–2131 recorded 5,316 decisions, of which 2,808 belonged to the teacher. All four trajectories replay-verified before the policy-agreement audit. The policy matched **843/916** teacher decisions with more than one legal option. On source-card decisions selected by the teacher it matched Wave-Motion Cannon **15/18**, Magician of Faith **26/27**, Tsukuyomi **39/39**, Metamorphosis **11/11**, Scapegoat **5/5**, and Book of Moon **8/8**. This is synthetic teacher agreement, not expert imitation or a causal account of match outcomes. The ignored trajectories and report are under `artifacts/cas_jesse_teacher_2130_2131/` and `artifacts/cas_jesse_fv17_v3_agreement_2130_2131.json`.

Reproduce the two direct policy schedules after [native setup](native_setup.md):

```bash
for opponent in combat_heuristic heuristic; do
  GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/python \
    scripts/evaluate_policy.py checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt \
    --engine experimental \
    --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
              examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk \
    --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
              examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
    --both-deck-assignments --opponent "$opponent" --seed 2120 --seeds 4 \
    --max-decisions 3000 --reject-training-deck-hashes --require-unseen-main-decks \
    --output "artifacts/fv17_v3_vs_${opponent}_2005_2120_2123.json"
done
```

Reproduce the ordinary-heuristic baseline and the Cas-versus-Jesse mirror:

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/python \
  scripts/evaluate_native.py --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
            examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --both-deck-assignments --agent-a heuristic --agent-b combat_heuristic \
  --seed 2120 --seeds 4 --max-decisions 3000 \
  --output artifacts/heuristic_vs_combat_2005_2120_2123.json

GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/python \
  scripts/evaluate_native.py --engine experimental \
  --matchup examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk \
            examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
  --agent-a heuristic --agent-b heuristic --seed 2120 --seeds 4 \
  --max-decisions 3000 \
  --output artifacts/cas_jesse_heuristic_mirror_2120_2123.json
```

The saved checkpoint is ignored by Git; its recorded hash identifies the exact local model used here. The CLI validates training provenance and seed separation for new evaluations.

## Warm-start imitation on sourced 2005 decks (2026-10-25)

`train_behavioral_clone.py --init-checkpoint` now loads compatible policy weights and carries forward the parent checkpoint's training seeds, deck hashes, Main Deck composition hashes, and trajectory hashes. It rejects an architecture or vocabulary mismatch and a parent lacking held-out provenance. Continued fitting starts a **new Adam optimizer**; optimizer moments are not restored. The saved child records the parent checkpoint SHA-256 and both cumulative and newly added source counts. This makes the existing evaluation gates apply to all games used in either training stage.

An opt-in feature-v17, width-32 experiment started from `checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt` (SHA-256 `63f300c568a2270510210cf7bd919b94c4519480270caadd7d6890316b807023`). Four replay-verified Cas-versus-Jesse trajectories from seeds 2130–2131 supplied **2,808 CombatHeuristicAgent v3 decisions**. One CPU epoch at learning rate 0.0001, batch size 16, and seed 2140 returned mean cross-entropy 0.09228. The ignored child `checkpoints/combat_2005_warm_cas_jesse_2140.pt` has SHA-256 `5c821318aaf6311af221a54a7d8c447e3835783fe5cba7591f53713dd371592e`, 36 cumulative training games, and 12,972 cumulative synthetic-teacher decisions. It is not a human-demonstration model.

Matt Peddle's Goat Control and Daryl Gessler's Gravekeeper Main Decks were held out by exact file hash and Main Deck composition, with seeds 2145–2148 also absent from both checkpoints. Against CombatHeuristicAgent v3, both parent and child scored **6–9–1** over the same 16-game schedule (40.625% score, paired 95% bootstrap interval 31.25–50%). The parent used 10,609 decisions in 14.27 tournament seconds; the child used 10,714 decisions in 15.87 seconds, each with two workers. In a separate 32-game direct match on those decks and seeds 2150–2157, the child scored **15–17** against the parent (46.875%, paired interval 40.625–50%). It scored 2–14 with Matt's deck and 13–3 with Daryl's, a large deck-assignment effect. None of these data establish an improvement. The child provenance gate rejected a parent training seed, a new training seed, and a Cas training Main Deck while accepting Matt/Daryl.

The ignored evaluation reports are `artifacts/fv17_parent_matt_daryl_2145_2148.json` (SHA-256 `19cc9fab029da2177f1a406510ab26270c93d1f8587b3cc31a273b6516b7e90e`), `artifacts/fv17_warm_matt_daryl_2145_2148.json` (`fdca27229eb5c689b0597fc2a6d25800bc0ab4e97068b1c260c516035ce88c9a`), and `artifacts/fv17_warm_vs_parent_matt_daryl_2150_2157.json` (`494b1be8e210b195c931e14ffe751f11c96adff5f3dcd9da6897444282c2fde8`). Reproduce after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  artifacts/cas_jesse_teacher_2130_2131/*.json \
  --engine experimental --feature-version 17 --width 32 --epochs 1 \
  --batch-size 16 --learning-rate 0.0001 --seed 2140 \
  --init-checkpoint checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt \
  --output checkpoints/combat_2005_warm_cas_jesse_2140.pt

for candidate in combat_fourdeck_fv17_v3_17000_17003 \
                 combat_2005_warm_cas_jesse_2140; do
  OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/evaluate_policy.py \
    "checkpoints/${candidate}.pt" --engine experimental \
    --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
              examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
    --both-deck-assignments --opponent combat_heuristic \
    --seed 2145 --seeds 4 --max-decisions 3000 --workers 2 \
    --reject-training-deck-hashes --require-unseen-main-decks \
    --output "artifacts/${candidate}_matt_daryl_2145_2148.json"
done

OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/evaluate_policy.py \
  checkpoints/combat_2005_warm_cas_jesse_2140.pt --engine experimental \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
            examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --both-deck-assignments \
  --opponent-checkpoint checkpoints/combat_fourdeck_fv17_v3_17000_17003.pt \
  --seed 2150 --seeds 8 --max-decisions 3000 --workers 2 \
  --reject-training-deck-hashes --require-unseen-main-decks \
  --output artifacts/fv17_warm_vs_parent_matt_daryl_2150_2157.json
```

## Five 2005 Main Deck holdout, seeds 2200–2201

The feature-17 v3 behavioral-cloning checkpoint scored **37 wins, 42 losses,
1 draw** against CombatHeuristicAgent v3 over 80 games on all ordered pairs
of five sourced 2005 tournament Main Decks, both seats, and seeds 2200–2201.
Its score rate was 46.875% (paired bootstrap 95% interval 40.0–53.75%).
It scored 15–25 from the first seat and 22–17–1 from the second. The evaluator
rejected training deck file hashes and required unseen Main Deck compositions.
This result does not establish an advantage over the heuristic.

The four-worker experimental native run took 37.63 tournament seconds for
63,268 decisions: **2.13 duels/s** and **1,681 decisions/s** on the recorded
Linux x86-64 machine. The ignored report is
`artifacts/fv17_v3_2005_top5_2200_2201.json` (SHA-256
`91bcd000e261b247de145441f09904e76cfd27e700bff19e13fdee1d712dd8aa`).
The checkpoint and native assets are fingerprinted inside the report.

## Visible-state tactical guard ablation, seeds 2210–2213

The unchanged feature-17 v3 checkpoint with the opt-in tactical guard played
the same checkpoint without the guard across all ordered pairs of five sourced
2005 Main Decks, both player seats, and four evaluation seeds. The 160 games
were split into two independently recorded 80-game runs:

| Seeds | Guard wins | Guard losses | Draws | Score rate | Paired bootstrap 95% interval |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2210–2211 | 52 | 28 | 0 | 65.0% | 58.75–72.5% |
| 2212–2213 | 47 | 32 | 1 | 59.375% | 50.625–67.5% |

Combined score: **99 wins, 60 losses, 1 draw, 62.19% of available points**.
The two recorded tournament wall times were 42.76 and 46.66 seconds on four
workers. The ignored reports are
`artifacts/guard_v2_vs_plain_top5_2210_2211.json` (SHA-256
`35e29c652dbad7c06de72567ee8dfe38ad1225890f3be7f24b78eb8e44078626`)
and `artifacts/guard_v2_vs_plain_top5_2212_2213.json` (SHA-256
`3d4db745aec4e20f136ecf46acebfa0df56c46ddf97f75427fd0813c7d5860d5`).
Both reject training deck hashes and require unseen Main Deck compositions.

This is evidence that the guard helps against the same checkpoint on this deck
set. It is not a claim of superiority to strong humans or to another baseline.
The guard remains opt-in pending broader matchups and training changes. See
[replay audit](replay_audit.md) for the particular
decisions that motivated it.

## TacticalHeuristicAgent v2 versus CombatHeuristicAgent v3

The experimental tactical baseline scored **74 wins, 46 losses** over 120
paired duels on all ordered pairs of the six sourced tournament Main Decks,
both seats, and seeds 2300–2301. Its 61.67% score rate had a paired bootstrap
95% interval of 55.0–68.33%. The four-worker tournament took 15.26 seconds.
The ignored report is `artifacts/tactical_v2_vs_combat_v3_2300_2301.json`
(SHA-256 `22a2f75ad5e0c5458b912ca382210833db8cc7b06d1a457ad5e852398e9be4f6`).
The comparator is a weak hand-built baseline; this result does not establish
competitive strength.

The guarded feature-17 v3 policy then scored **36 wins, 44 losses** against
TacticalHeuristicAgent v2 across all ordered pairs of the five sourced 2005
Main Decks, both seats, and seeds 2310–2311. Its 45.0% score rate had a paired
bootstrap 95% interval of 36.25–53.75%; it scored 16–24 in the first seat and
20–20 in the second. The four-worker tournament took 43.57 seconds. The ignored
report is `artifacts/policy_guard_v2_vs_tactical_v2_top5_2310_2311.json`
(SHA-256 `39516838fbc8dfeaa675db57e91a22608be83f146d4366472ae433bc79086125`).
The evaluation rejected training deck file hashes and required unseen Main
Deck compositions. These results do not support calling the guarded policy
the strongest local agent yet.

## Schema-v23 / feature-v19 pipeline smoke test

The native adapter now records the public turn player separately from the
acting player. Two TacticalHeuristicAgent v3 versus RandomAgent duels at seed
2400 generated 1,695 total schema-v23 decisions, of which 903 belonged to the
teacher. Both were replay-verified by the behavioral-cloning command before
training. A one-epoch feature-v19, width-16 clone used exactly those 903
teacher decisions and reported training loss 0.5401. The loaded checkpoint
then completed and replay-verified a 1,232-decision native duel against
RandomAgent at seed 2410, winning from seat 0. This is a pipeline check, not a
playing-strength estimate or a held-out model comparison.
The teacher records include Scapegoat Set on its own Main Phase, activated at
the opponent's Battle Start in one duel, and activated during the opponent's
End Phase in the other. Each decision records the turn owner separately from
the responding player.

Reproduce with `scripts/collect_heuristic_demos.py --teacher tactical
--engine experimental --seed 2400 --seeds 1`, using the Cas Flip Control and
Daryl Gravekeepers decks, then `scripts/train_behavioral_clone.py` with
`--feature-version 19 --width 16 --epochs 1 --batch-size 32
--learning-rate 0.001 --seed 19`. The ignored local checkpoint is
`checkpoints/schema23_v19_v3_smoke_2400.pt` (SHA-256
`59562962062d6847f9b484f431d2d26ac6c1a9f1a1faab15940515847e750c2e`).
The two trajectory SHA-256 values are
`727ce29d5f07cd17c8af585cbf0672720b6d26387b083347053cca800e7b26bc`
and `a1d6a7c9e20e736f9352c573a1b14fe3a0ede649b465e67c2659fc87af1278ae`;
the evaluation replay hash is
`8f9eaeb58fa4f2880e610265cb6e173063aa95886c618e7ca1495e6cda4ac2f0`.

The turn-aware tactical guard (policy inference v5) scored **27–13** against
the same feature-v17 checkpoint without a guard over 40 duels on two ordered
2005 deck pairings, both deck assignments, both seats, and seeds 2410–2414.
Its paired bootstrap 95% interval was 52.5–82.5%. This small ablation checks
that the new timing condition did not erase the earlier gain; it does not
replace the broader 160-game v4 guard evaluation above. The ignored report is
`artifacts/guard_v5_vs_plain_two_pairs_2410_2414.json` (SHA-256
`ab5b4f600eb9fbea63daef92b783f85bd60298721e957bb74461f795d26aa173`).

## Turn-owner feature ablation, seeds 2500–2537

To isolate the turn-owner observation feature, TacticalHeuristicAgent v3
played CombatHeuristicAgent v3 on Cas Flip Control versus Daryl Gravekeepers
and Matt Peddle versus Jesse Twohig Main Decks. Seeds 2500–2503 and both
teacher seats produced 16 full schema-v23 duels and **6,014 teacher
decisions**. The collector now accepts `--opponent combat_heuristic` and
records the opponent version. Both clones used the same verified trajectories,
seed 19, width 16, two epochs, batch size 32, and learning rate 0.001. Only
the feature version differed: 18 omitted explicit turn ownership and 19
included it. Their checkpoint SHA-256 values are respectively
`3bd3fcd7212cc8f587ed1cc40c963018348396474913a5457708ddfa9b457201`
and `fe197724523b33a8d555e90ab9f7b669dab2081b000346b9b31d1788d7e07fc2`.
The final training losses were 0.2629 and 0.2894; training loss is not a
strength estimate.

Eight replay-verified teacher duels on unseen Michael Fukuyama, Chaos Control,
Warrior, and Chaos Return Main Decks at seeds 2520–2521 supplied 2,039
held-out teacher decisions, including 631 with multiple legal actions. The
feature-18 and feature-19 models respectively matched **1,903/2,039** and
**1,899/2,039** exact actions, or **495/631** and **491/631** when more than
one action was legal. For 20 decisions where Scapegoat was offered, they
matched **17/20** and **19/20**. The teacher actually chose Scapegoat only
twice; feature 19 matched one Set, while neither model matched one chain.
Among all decisions, 1,290 were on the acting player's own turn and 749 on
the opponent's turn; only eight were in an End Phase and **none offered
Scapegoat there**. The Scapegoat timing hypothesis therefore remains
untested by this holdout. The ignored agreement report is
`artifacts/fv18_fv19_tactical_holdout_2520_2521.json` (SHA-256
`6a57e00e6d9e39fae45b8b5005adcd4a3afde149e6117e636d349a7fbad9437f`).

In a direct 64-game match on the same unseen Main Deck families, seeds
2530–2537, both deck assignments, and both player seats, raw feature 19
scored **30 wins, 33 losses, 1 draw** against raw feature 18: **47.66%** of
available points, paired bootstrap 95% interval **38.28–57.81%**. The
evaluator rejected training deck hashes and required unseen Main Deck
compositions. Four workers completed 41,590 decisions in 36.26 seconds
(1.77 duels/s, 1,147 decisions/s) on the recorded Linux x86-64 machine.
The ignored report is
`artifacts/fv19_vs_fv18_tactical_unseen_2530_2537.json` (SHA-256
`6186604ab9ca943516b73c51f61381120ab92492f47c50a399f292157a0a48ac`).
These data show no competitive gain from the feature on this schedule. Keep
feature 19 opt-in and collect replay-verified own-turn and opponent-turn End
Phase Scapegoat choices before making a timing-specific learning claim.

A subsequent [scripted timing probe](replay_audit.md) now supplies a
replay-verified native End Phase diagnostic on both turn owners. Both matched
checkpoints pass when the script activates Scapegoat at the opponent's later
End Phase, so this targeted case confirms the timing gap left by the holdout
sample. It is one synthetic scenario, not an independent strength estimate.

## Three-label synthetic Scapegoat timing fit

The timing probe now emits `replays/scapegoat_end_timing_probe_seed52.labels.json`
(SHA-256 `f14bcb731cf3b0755be735926e52cd4588383384097251bded6431d88ce80e23`).
It names only replayed choices at decision indexes 20, 28, and 35, with
`scripted_scenario` authorization tied to the exact trajectory hash. The
trainer verifies the full 711-decision duel and its visible information,
then records exactly **three `synthetic_annotation` decisions** separately
from the parent's 6,014 tactical-teacher decisions. This is synthetic
curriculum data, not human gameplay.

Warm-starting the feature-19 width-16 parent with five epochs at learning
rate 0.0001 did not change its `pass/pass/pass` choices on the probe. A
100-epoch fit at learning rate 0.001 also left the last choice as `pass`.
A **500-epoch fit** at learning rate 0.001 made the choices
`pass/pass/chain` (final training loss 0.0107). The resulting checkpoint is
`checkpoints/tactical_v3_fv19_scapegoat_timing_fit500_52.pt` (SHA-256
`894261f8cc5c5eb57016aaac80c0f3932a0149aa5e5b1e63ed1a6e0d9125720f`).
This is an overfit check on the three labeled states, not a held-out result.

Four separate shuffled versions of the same synthetic duel (seeds 56, 64,
69, and 70) all replay-verified. The parent passed at the later opponent End
Phase on all four; the child activated at all four and passed at its own End
Phase on all four. On seed 64 it also activated at the earlier opponent End
Phase, which may be sensible; that scripted earlier `pass` exists to keep the
card for the later probe. These variants retain the same fixture deck
composition and do not establish transfer to competitive decks.

On unseen Michael Fukuyama, Chaos Control, Warrior, and Chaos Return Main
Decks, the child scored **69 wins, 59 losses** directly against its parent
across 128 paired games at seeds 2540–2555, both deck assignments and both
seats. Its score rate was **53.91%**, paired bootstrap 95% interval
**44.53–62.50%**. The assigned-deck splits were Michael 23–9, Warrior
25–7, Chaos Control 10–22, and Chaos Return 11–21. The evaluator rejected
all training deck hashes and required unseen Main Deck compositions. This
does **not** establish a competitive gain and shows substantial deck
dependence. The two ignored 64-game reports are
`artifacts/scapegoat_timing_fit500_vs_parent_2540_2547.json` (SHA-256
`ff8af0277b3b9852e23fdf38a65a96a2147ba39a9c6898157f95f2b81e81cb64`)
and `artifacts/scapegoat_timing_fit500_vs_parent_2548_2555.json` (SHA-256
`0ada91370bca07fbc1dbf77f4a6d5bf0dd15a88079b903fe1013f17a163c60a6`).
The four-worker tournament times were 33.26 and 35.71 seconds respectively.
The next experiment needs independent timing decisions from competitive
decks and a training method that preserves broader play while learning them.

## Mixed rehearsal and restricted warm-start ablations

The trainer now accepts `--annotation-for TRAJECTORY=LABELS` so the three
synthetic timing labels can be mixed with the original 16 replay-verified
tactical-teacher duels. It refuses an unannotated `scripted_` replay. A
`--source-weight` option samples rare sources more often while keeping the
number of optimizer decisions per epoch fixed. Both mixed runs started from
the feature-19 parent, presented 6,014 tactical decisions plus three
synthetic ones, and used batch size 32 and seed 19:

| Synthetic weight | Epochs | Learning rate | Probe choices, turns 3/4/5 |
| ---: | ---: | ---: | --- |
| 200 | 2 | 0.0001 | pass / pass / pass |
| 1,000 | 3 | 0.0001 | pass / pass / pass |

These settings raised Scapegoat's chain score at all three probe decisions
but did not rank `chain` above `pass` at the intended turn-5 activation.
Neither checkpoint was promoted or subjected to a strength claim.
The ignored checkpoints are
`checkpoints/tactical_v3_fv19_rehearsal_s200_52.pt` (SHA-256
`944fd556f5346b078d25bbd5d979d475d04f63940e012675c5ee708cc381903f`)
and `checkpoints/tactical_v3_fv19_rehearsal_s1000_52.pt` (SHA-256
`e9bb505001c8702978f0efd8a6e741b0c5c17b965222bd24d424cfc01c4ea0e3`).

A separate 500-epoch, three-label warm-start updated only the existing
`state_numbers` and `score` modules. It fit `pass/pass/chain` on seed 52 and
chose `pass` on its own End Phase and `chain` on the later opponent End Phase
on all four separate shuffle seeds 56, 64, 69, and 70. The checkpoint is
`checkpoints/tactical_v3_fv19_timing_state_score_52.pt` (SHA-256
`c1e3a2027df944bf04bcd9ecc27d8c00e2647a7d722c3aa34d87c5107ba7f3db`).

In a 64-game paired match against its unchanged parent on unseen Michael
Fukuyama, Chaos Control, Warrior, and Chaos Return Main Decks, both deck
assignments and both seats at seeds 2560–2567, this restricted child scored
**8 wins and 56 losses**. Its score rate was 12.5%, paired bootstrap 95%
interval **4.69–21.88%**; assigned-deck wins were 4/16, 3/16, 1/16, and
0/16 respectively. The evaluator rejected training deck hashes and required
unseen Main Deck compositions. The four-worker tournament took 32.54
seconds. The ignored report is
`artifacts/timing_state_score_vs_parent_2560_2567.json` (SHA-256
`d90142a0ba784dd997d41cb8740bfbc37cd8b54a6d7993638577e98a1324780d`).
The local timing fit badly damaged general play. Neither rehearsal nor
module restriction is sufficient evidence of a safe competitive update.

## Parent-policy KL preservation for timing labels

A frozen-parent KL trainer now fits selected labels while matching parent
action distributions on separately selected, player-visible decisions.
The replay-verified run used the same three Scapegoat timing labels at seed
52 and sampled 32 multi-option decisions from each of the 16 original
tactical-teacher replays (512 preservation states total). At each of 500
optimizer steps it used all three labeled decisions and eight preservation
states, KL weight 1, learning rate 0.001, and seed 19. It rejected any
preservation replay whose byte hash was absent from the parent checkpoint.
The productized run reproduced the earlier contained prototype's model
weights **exactly**; its own checkpoint is
`checkpoints/tactical_v3_fv19_timing_parent_kl_52.pt` (SHA-256
`0cdcca4569e1d4d781d876d90bd9e4dfb0563db13c3e5bbd4ebb53949ef3254a`).
Final selected-label cross-entropy was 0.01465 and sampled preservation KL
was 0.00293. These training losses are diagnostics, not strength estimates.

The child selected `pass/pass/chain` on the training probe and activated at
the later opponent End Phase while passing on its own End Phase on all four
separate shuffle seeds 56, 64, 69, and 70. It activated at the earlier
opponent End Phase on seeds 64 and 69, a choice the probe's scripted pass
does not establish as wrong. Those seeds use the same fixture deck
composition. On eight replay-verified teacher holdout games from other
Main Decks, exact agreement changed from **1,899/2,039** for the parent to
**1,889/2,039** for the child, and from **491/631** to **481/631** on
multi-option decisions. Where Scapegoat was offered, agreement fell from
**19/20** to **13/20**, although agreement on the two teacher-selected
Scapegoat plays rose from **1/2** to **2/2**. The child therefore appears
more willing to activate Scapegoat, including where this synthetic teacher
passed. The ignored audit report is
`artifacts/timing_parent_kl_teacher_agreement_2520_2521.json` (SHA-256
`f332b00d1d16dbdcefdd1c04fc9f45ebcd6ed2b1442ba46f8150dc00a5779190`).

In 128 paired games against the same parent on unseen Michael Fukuyama,
Chaos Control, Warrior, and Chaos Return Main Decks, both assignments and
seats, seeds 2570–2585, the identical-weight prototype/productized child
scored **66 wins, 61 losses, 1 draw**: 51.95% of available points, paired
bootstrap 95% interval **46.48–57.03%**. The assigned-deck splits were
Michael 24–8, Warrior 25–7, Chaos Control 8–23–1, and Chaos Return 9–23.
The evaluator rejected training deck hashes and required unseen Main Deck
compositions. The two four-worker tournament times were 33.15 and 30.86
seconds. The ignored reports are
`artifacts/timing_kl_prototype_vs_parent_2570_2577.json` (SHA-256
`da4dfc9761688976ca1e0434f0e37b6b340003fb7f4f48af6bdbdca360135`)
and `artifacts/timing_parent_kl_vs_parent_2578_2585.json` (SHA-256
`b696eeaddd6253d79a9c7d01b7761956acf98f7ea5891765ceb8210453adfe54`).
The interval includes 50%, and the large assigned-deck differences remain.
This method did not establish a competitive gain or close M4.

## Published-deck Scapegoat timing curriculum

The native timing generator was repeated with the published Daryl
Gravekeepers deck against Cas Flip Control at seed 2601, Matt Goat Control
at seed 2604, and Jesse Goat Control at seed 2610. The complete duels
replay-verified at **1,119**, **1,255**, and **872** decisions. In each,
Scapegoat was Set on its controller's turn 2, held through an opponent End
Phase and its own End Phase, then activated at the next opponent End Phase.
The three timing labels occur at decision indexes 20, 28, and 35. A second
synthetic label file per duel includes **19** early Scapegoat opportunities:
Draw, Standby, Main Phase, the Set choice, and the End Phase windows. These
are scripted curriculum choices, not skilled-player demonstrations. The
Cas, Matt, and Jesse replay SHA-256 values are respectively
`3d4fcdd12fbc81301dca7f267a14f298c88f44f1f9e24ec990356fa3fbdd4cce`,
`2904c3fe05e1593c4a29eb4e26c9fa8ab71452b4676cb6293776c9390d098879`,
and `30961ace581fda3e6e0a0077de173bb982fc2b79587586240de72c78be09ec48`.

The feature-19 parent and the earlier three-label parent-KL child both
passed at the final opponent End Phase in all three published-deck probes.
A parent-KL run trained on Cas and Matt's **six** End Phase labels chose
`pass/pass/chain` on the two updated timing replays and the separate Jesse
timing replay. Jesse's Main Deck already appeared in the parent checkpoint's
Matt-versus-Jesse training games, so this tests a new decision context, not
an unseen Main Deck. Its
checkpoint is `checkpoints/tactical_v3_fv19_timing_cas_matt_parent_kl.pt`
(SHA-256 `5351809b267317a717c32755cd20faab83954ac1b0f29c5adc167e13dcdf597c`).
On the separate eight-game teacher holdout, however, its exact agreement
fell from the parent's 1,899/2,039 to **1,883/2,039** and Scapegoat-offered
agreement fell from 19/20 to **12/20**. It scored **33–31** directly against
the parent in 64 unseen-Main-Deck paired games at seeds 2590–2597, 51.56%
of points with paired 95% interval **42.19–62.50%**. The assigned-deck
splits were Michael 13–3, Warrior 12–4, Chaos Control 3–13, and Chaos
Return 5–11. The ignored reports are
`artifacts/timing_cas_matt_teacher_agreement_2520_2521.json` (SHA-256
`8e0b9668877653246849c9b99930c4cafc35e703c7aa602f2b22af11862085da`)
and `artifacts/timing_cas_matt_parent_kl_vs_parent_2590_2597.json` (SHA-256
`1cb75a51742dd9323e5f30d671b5548519388ca29cdf17480fe9f53f8386179c`).

Training on all **38** Cas and Matt curriculum choices without action-kind
weight learned the Set choice and early passes but still passed at the final
opponent End Phase on Cas, Matt, and Jesse. Giving selected `chain` actions
ten times the ordinary label loss weight learned the final activation while
retaining the early Draw, Standby, and Main Phase passes on Jesse. On Cas,
Matt, and Jesse it activated at the *earlier* opponent End Phase, which the
script passes only to expose the later window and which may be reasonable.
The weighted checkpoint is
`checkpoints/tactical_v3_fv19_timing_curriculum_chain10_kl.pt` (SHA-256
`07baac3ef5ef212fb75188c76e26c39c655bf067c43948e1f6ec1104a777b7a8`).
The unweighted checkpoint is
`checkpoints/tactical_v3_fv19_timing_curriculum_cas_matt_kl.pt` (SHA-256
`a270b586b655d22c643ff13c9ef4d21dad11674f3983efb338335d56013e4d99`).

On the eight-game teacher holdout, the weighted child matched
**1,893/2,039** decisions, **485/631** multi-option decisions, **15/20**
Scapegoat-offered decisions, and **2/2** teacher-selected Scapegoat plays.
Four of its five Scapegoat-offered mismatches were premature activations in
one opponent Main Phase; the fifth was setting Scapegoat instead of a normal
summon. In 64 paired games against its parent on unseen Michael, Chaos
Control, Warrior, and Chaos Return Main Decks, both deck assignments and
seats, seeds 2620–2627, it scored **29 wins, 35 losses**: 45.31%, paired
95% interval **37.50–54.69%**. The assigned-deck splits were Michael 12–4,
Warrior 11–5, Chaos Control 4–12, and Chaos Return 2–14. The evaluator
rejected training deck hashes and required unseen Main Deck compositions.
The four-worker tournament took 31.37 seconds. The ignored reports are
`artifacts/timing_curriculum_chain10_agreement_2520_2521.json` (SHA-256
`6311514196f434fe6b5ac25b17aafc0ac9902c08db4f3852d905801a82614bc2`)
and `artifacts/timing_curriculum_chain10_vs_parent_2620_2627.json` (SHA-256
`7643e5c087fcfbdb68a5236262651a46e468eef8f13dc1351204fc3c7dace95d`).
The choice transfer is real in these scripted replays; competitive strength
has not improved in the measured sample, and M4 remains open.

### Replay-audit Royal Decree guard check

The [seed-2612 replay audit](replay_audit.md) found the feature-19 policy
activating Sakuretsu Armor under its own face-up Royal Decree. The opt-in
visible-state tactical guard now defers that Sakuretsu activation when `pass`
is legal. On the saved player-visible observation at viewer frame 181, the
selected Sakuretsu action is removed; the Book of Moon and missed Scapegoat
choices elsewhere in that duel remain. The complete recorded duel separately
replay-verified for **534 decisions**. This is an action-level correction,
not a re-run of the same duel after changing its earlier choices.

For a small competitive check, the unchanged feature-19 parent checkpoint
`tactical_v3_fv19_2500_2503.pt` (SHA-256
`fe197724523b33a8d555e90ab9f7b669dab2081b000346b9b31d1788d7e07fc2`)
played TacticalHeuristicAgent v3 on Chaos Return/Warrior and Chaos
Control/Warrior, both deck assignments and both seats, seeds 2620–2623.
The evaluator required Main Deck compositions unseen in the checkpoint's
training games. Without the optional guard it scored **13–19**; with the
*full* guard it scored **15–17**. Two of 32 matched schedule slots changed
from loss to win, none changed the other way. The guarded score was 46.88%,
with its evaluator's paired-bootstrap 95% interval 31.25–62.50%.
The guard contains earlier filters as well as the new Decree rule, so this
comparison cannot attribute the two wins to the Decree change. The small
sample does not establish a strength gain or close M4.

Ignored local reports: `artifacts/decree_guard_parent_unguarded_2620.json`
(SHA-256 `6c3d836cc7b0b9f646fe86f056d7ee65cc9d05f3ba0c76669a5ca86c9cd9b8b5`)
and `artifacts/decree_guard_parent_guarded_2620.json` (SHA-256
`2fcd0beea46f3c66bb4524607e2bd7084f9d49c2c61c3a0df950165a2b03eb6b`).

### Five-label policy replay review probe

The review pipeline now accepts `policy_review` annotations only for the
checkpoint-attributed policy seat of a replay-verified `policy_evaluation`
duel. The five choices in
`examples/annotations/feature19_seed2612.review.json` refer to the 534-decision
seed-2612 replay: pass rather than use Sakuretsu under Decree at frame 181,
then activate Scapegoat at four opponent-turn defensive or End Phase windows.
The labels are hindsight judgments by a project reviewer, **not** human match
demonstrations. The trainer separately records them as
`policy_review_annotation` and checks the exact replay hash, legal choices,
policy seat, visible-information audit, and full native replay before training.

A 200-step parent-KL fit of these five labels, weighted tenfold for selected
`chain` actions, preserved 64 multi-option states sampled from four verified
parent-training games. The experimental child
`checkpoints/tactical_v3_fv19_policy_review_2612_kl.pt` has SHA-256
`47a29b5f31f16daa1e6e8bba9e55bda2003bc568960cdc4fdd4ff42d04ab18f2`.
On the saved seed-2612 observations, it selected all four reviewed Scapegoat
activations and chose Scapegoat instead of Sakuretsu at frame 181; the latter
does not match the review's preferred `pass` exactly. On the separate Jesse
Scapegoat timing probe, it activated at both earlier opponent End Phases and
the final one, whereas the parent passed at all three. Earlier activation
may be sound; these fixed-state checks do not measure game strength.

In **64 direct paired duels** versus the parent on unseen Chaos Control,
Chaos Return, and Warrior Main Decks, both deck assignments and seats,
seeds 2630–2637, the child scored **31 wins, 32 losses, one draw**:
49.22% of points, paired-bootstrap 95% interval **40.63–57.03%**. Its assigned
Chaos Control score was 2–14, Chaos Return 4–12, and Warrior 25–6–1.
The evaluator enforced unseen Main Deck composition. The ignored report is
`artifacts/policy_review_2612_child_vs_parent_2630_2637.json` (SHA-256
`ea14ed3c65c252edff48e7f29ee91eace376eb6c0c7bb7092cbec3b3eb1678a4`).
This probe shows label transfer to related decisions but no measured
competitive gain. It remains an experiment, not a promoted policy; M4 stays
open. Reproduce the source replay with the command in [the replay audit](replay_audit.md).
The fit used `--engine experimental --width 16 --feature-version 19
--seed 2612 --parent-kl-steps 200 --preserve-per-trajectory 16
--preserve-batch 16 --parent-kl-weight 1.0 --label-kind-weight chain=10`, with
`--init-checkpoint checkpoints/tactical_v3_fv19_2500_2503.pt` and
`--preserve-trajectories` set to both seat files at seed 2500 in each of
`replays/tactical_v3_cas_daryl_2500_2503/` and
`replays/tactical_v3_matt_jesse_2500_2503/`.

## Native worker memory pilot

At project commit `30d9889`, `scripts/benchmark_parallel_native.py` ran
RandomAgent against RandomAgent on the sourced Goat Control and Chaos Turbo
decks, seeds 9700–9703 with both seat assignments, two spawned workers, and a
3,000-decision cap. All **8/8 duels** reached a native terminal result after
**8,069 decisions**. On Linux 6.8.0 x86-64 with an Intel i7-10700K and
`OMP_NUM_THREADS=1`, wall time including worker spawn was **5.36 seconds**:
**1.49 duels/s** and **1,506 decisions/s**. Mean reset time was **0.0903
seconds per duel**. These are protocol throughput measurements, not an agent
strength or full GOAT correctness result.

The parent process's Linux `VmHWM` was **25,840 KB**. The two workers' final
`VmHWM` values were **67,140 KB** and **64,304 KB**, with **131,444 KB** as
their sum. Each is a process high-water mark; the sum is **not** an
instantaneous machine-wide peak, and this eight-game pilot does not establish
memory scaling at larger worker counts. The ignored report
`artifacts/parallel_memory_9700_9703.json` records each game, worker PID,
deck and native asset hashes, and timing (SHA-256
`9389d549bad43c4b30d163c670c3635e4f220c5ed4de3ab8010b65b185954c8f`).
Reproduce with:

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/benchmark_parallel_native.py \
  --native-root .cache/goat-ai --games 8 --workers 2 \
  --output artifacts/parallel_memory_9700_9703.json
```

## Feature-19 tactical guard and weak Flip Set experiment

The unchanged `tactical_v3_fv19_2500_2503.pt` checkpoint was evaluated on
Chaos Control, Chaos Return, and Warrior Main Decks whose compositions were
excluded from training. Seeds 2670–2673, all three pairings, both deck
assignments, and both seats gave **48 direct duels** per comparison. The
existing visible-state guard v3 scored **26–22** against the same checkpoint
without a guard: **54.17%** of points, paired-bootstrap 95% interval
**50.0–60.42%**. The 21.00-second four-worker report is
`artifacts/fv19_guard_vs_plain_holdout_2670_2673.json` (SHA-256
`5b85d44f3f079e445824b67a86e94d252ace1032e3424317aebe2dbe2a517255`).
This schedule alone does not establish a reliable gain.

An opt-in guard v4 uses printed Flip type and ATK from the pinned card databases.
If the guarded policy's preferred legal action is a Normal Summon of a Flip
monster with at most 500 printed ATK, it chooses the Set of that same card
when available. It leaves a face-up summon available if an unobstructed
Battle Phase and visible ATK show a plausible direct lethal attack. This is a
general play preference, not a simulator legality change or a trained policy.
On the six saved mistake snapshots, v4 chose Set for all three Magician of
Faith summons; its inherited v3 guard passed before two wasteful Tribe
activations and named Beast instead of Spellcaster in the third Tribe case.
These fixed-state choices do not prove better duel outcomes.

Against guard v3 on the same checkpoint and held-out schedule, guard v4 scored
**23–25**, or **47.92%** of points, with paired-bootstrap 95% interval
**43.75–50.0%**. The four-worker tournament took **21.33 seconds**. Its ignored
report is `artifacts/fv19_guard_v4_vs_v3_holdout_2670_2673.json` (SHA-256
`62bc2697f0e6bdaad14d8017612d08ec7f7a593a760c3cc0c0b8c9ef0068c356`).
Guard v4 is retained only as an experiment; the result does **not** support
promoting it over v3. A full guard-v4 duel against TacticalHeuristicAgent v3
on Daryl/Cas seed 2647 reached a native terminal result in 399 decisions and
replay-verified. The corresponding audit matched all 224 policy choices to
the saved checkpoint and found one Scapegoat timing prompt, with no weak Flip
or Tribe prompt. The ignored trajectory and audit SHA-256 values are
`2ff2409512362fcae4980f7d9ff3ba504eb3bbefdc6e80abe042f8bb838b40ee`
and `67d9eaa6000724d401e03d9cef2b0573b76cba1f03277b8178540a8f932db48b`.

Reproduce the direct ablation with `scripts/evaluate_policy.py` using the
checkpoint above for both sides, `--engine experimental --tactical-guard
--weak-flip-guard --opponent-checkpoint` set to that checkpoint,
`--opponent-tactical-guard --both-deck-assignments --seed 2670 --seeds 4
--max-decisions 3000 --require-unseen-main-decks --workers 4`, and the three
matchups named above. The report includes the card databases used for printed
metadata in its asset hashes. The v3-versus-plain run omits
`--weak-flip-guard --opponent-tactical-guard`.

## Experimental self-target guard v5

Replay review found two saved feature-19 policy decisions where Black Luster
Soldier selected an own monster for its banish effect despite an offered enemy
target, and one where Mystical Space Typhoon selected the policy's own Set
Solemn Judgment despite an offered opposing Set card. The opt-in v5 guard
extends v3 only at those target prompts: if an opposing target is legal, it
removes own targets from the scored set. It reads the public chain source and
legal-action target controllers. It does not decide whether activating either
effect was useful. Guard v4 remains a separate, non-combinable experiment.

On the three original player-visible snapshots, v3 selected the same own
targets as the replay; v5 selected the offered opposing Set monster, opposing
Set Spell/Trap, and opposing face-up Sinister Serpent respectively. These are
off-policy fixed-state checks. A complete v5 duel on Daryl/Cas seed 2647
reached terminal and replay-verified all **422 decisions**. The audit matched
its **233 policy choices** to the saved feature-19 checkpoint and found no
BLS/MST self-target candidate. It still flagged one Scapegoat pass and two
weak Flip summons, so the guard addresses only the named target mistakes.

Against v3 on the unchanged checkpoint and the same held-out Chaos Control,
Chaos Return, and Warrior schedule as the v4 comparison above, v5 scored
**25–23** across **48 direct duels** (52.08% of points; paired-bootstrap 95%
interval **50.0–56.25%**). All games reached terminal under the 3,000-decision
cap. The four-worker tournament took **21.58 seconds** on the reported x86_64
machine. The ignored report is
`artifacts/fv19_guard_v5_vs_v3_holdout_2670_2673.json` (SHA-256
`0872db2bebb2817e98cbe84e57d87cbf59360f75f1b867257b19dad35f60782c`).
The interval includes 50%; this experiment does not establish a competitive
gain or justify promoting v5 as the default. It may also suppress deliberate
own-card targets in unusual positions.

Reproduce with `scripts/evaluate_policy.py` using the same three matchups and
options above, replacing `--weak-flip-guard` with `--self-target-guard`.
Record and audit the complete duel with `scripts/record_policy_match.py
--tactical-guard --self-target-guard` and then
`scripts/audit_policy_replays.py` on the resulting trajectory.

## Eight-label replay-review parent-KL probe

The unchanged feature-19 checkpoint scored all eight SHA-256-bound
`policy_review` choices below its recorded action in the [replay scorecard](replay_audit.md).
To test whether these corrections transfer, one experimental child initialized
from `tactical_v3_fv19_2500_2503.pt` (SHA-256
`fe197724523b33a8d555e90ab9f7b669dab2081b000346b9b31d1788d7e07fc2`)
and used the five seed-2612 labels plus the three BLS/MST target labels.
All four full trajectories replay-verified and passed the visibility audit.
The trainer recorded them as **eight `policy_review_annotation` decisions**, not
human demonstrations. It preserved 64 multi-option parent-training states,
sampled 16 each from four pinned tactical-v3 games at seed 2500, while fitting
for 200 parent-KL steps at learning rate 0.0001, KL weight 1.0, and seed 2700.
The final labeled loss was **0.67434** and preservation KL **0.01582**.

The ignored child `checkpoints/tactical_v3_fv19_review8_parent_kl_2700.pt`
has SHA-256 `5d77876dada4966ca39f5c0198d048fc8ed361875518d78b77849642a24720a7`.
On its **training** annotations, it ranks six of eight reviewed alternatives
first; frame 181 selects a different action and frame 209 still prefers the
recorded pass. Its scorecard correctly marks all four source trajectories and
seeds as training overlap. The ignored scorecard is
`artifacts/feature19_review8_child_scorecard.json` (SHA-256
`fad63d6f32b96fcde0dd8fe2d3d3edfc6abdcea97a224c4ce05403db755f7939`).
This label fit is not held-out evidence.

For direct competitive evaluation, the child played its unchanged parent on
Chaos Return, Bazoo Return, Goat Control, and Chaos Turbo Main Decks. The
evaluator rejected Main Deck compositions present in either checkpoint's
training games. All six pairings, both deck assignments, both policy seats,
and seeds 2720–2727 produced **192 terminal duels** and **106,268 decisions**.
The child scored **99 wins, 91 losses, and two draws**: **52.08%** of points,
paired-bootstrap 95% interval **45.57–58.59%**. Assigned-deck scores were
Bazoo Return **36–11–1**, Chaos Return **24–23–1**, Chaos Turbo **17–31**, and
Goat Control **22–26**. The four-worker tournament took **82.79 seconds** on
the recorded x86_64 machine. Its ignored report is
`artifacts/feature19_review8_child_vs_parent_2720_2727.json` (SHA-256
`9b22bafe8a18cb3d2ec2d21b9a7955f59305221b37ce2ec8fbb0f8a11e0ae474`).
The overall interval includes 50% and deck results are uneven. This child is
not a promoted strength improvement. More independent target and timing
examples, including negative cases where an own target is useful, are needed
before another training attempt can support a general policy claim.

The fit is reproducible with `scripts/train_behavioral_clone.py` using
`--engine experimental --width 16 --feature-version 19 --seed 2700
--parent-kl-steps 200 --preserve-per-trajectory 16 --preserve-batch 16
--parent-kl-weight 1.0 --learning-rate 0.0001`, the parent checkpoint above,
the four reviewer-labeled trajectories named in the [replay audit](replay_audit.md),
and the four seed-2500 preservation files in
`replays/tactical_v3_cas_daryl_2500_2503/` and
`replays/tactical_v3_matt_jesse_2500_2503/`. The tournament used
`scripts/evaluate_policy.py --engine experimental --opponent-checkpoint` set
to the parent, six `--matchup` pairs from the four decks above,
`--both-deck-assignments --seed 2720 --seeds 8 --max-decisions 3000
--require-unseen-main-decks --workers 4`.

## Four-role self-play schedule smoke test

The original `paired_seats` schedule assigns the learner the first deck of
each listed matchup in both seats. Earlier balanced two-deck runs therefore
listed both `(A, B)` and `(B, A)`. The opt-in `four_roles` schedule assigns
the learner each deck in each seat over four games per matchup, and the CLI
requires complete cycles. It preserves the old default and records the mode
in the child checkpoint.

Starting from the unchanged feature-19 tactical-v3 checkpoint, seeds 2800–2803
used one Goat Control/Chaos Turbo matchup with `--schedule-mode four_roles`,
the experimental native adapter, the default episodic policy-gradient
settings, and a 3,000-decision cap. All **four games terminated**; the learner
played Goat Control in seats 0 and 1, then Chaos Turbo in seats 0 and 1.
The sampled learner won two and lost two against its snapshot/RandomAgent
mixture; this is not a strength estimate. All **5,110 decisions** from the
four recorded trajectories replay-verified against fresh pinned engines.
The separate visibility audit passed, including 60 opponent hidden-field
choices and 13 opponent-hand choices. The child checkpoint and trajectories
are ignored local artifacts:
`checkpoints/selfplay_fourroles_smoke_2800.pt` and
`replays/selfplay_fourroles_2800/`. No held-out direct evaluation or policy
promotion follows from this schedule smoke test.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_self_play.py \
  checkpoints/tactical_v3_fv19_2500_2503.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/chaos_turbo_riclar_2020.ydk \
  --schedule-mode four_roles --seed 2800 --games 4 \
  --max-decisions 3000 --record-dir replays/selfplay_fourroles_2800 \
  --output checkpoints/selfplay_fourroles_smoke_2800.pt
```

## Four-deck feature-19 self-play continuation

To test the current terminal-reward method with broader deck and seat coverage,
one predefined run initialized from the unchanged
`tactical_v3_fv19_2500_2503.pt` checkpoint and used the `four_roles` schedule
over Goat Control versus Chaos Turbo and Bazoo Return versus Chaos Return.
Seeds 2820–2883 gave each of the four training decks eight learner games in
each seat. The experiment used the experimental native adapter, 64 games,
learning rate 0.0003, sampling temperature 2.0, entropy coefficient 0.01,
a moving baseline per learner deck, and a 75% historical-snapshot opponent
mix with an eight-game snapshot interval. The learner won 28, lost 33, and
drew three against its **training** opponents. No game hit the 3,000-decision
cap. The resulting checkpoint recorded **8,335 learner decisions** and has
SHA-256 `c4a7b389d24b270256ca1553f20f8699fed9631811850bbb5e97e084f2ecaed0`.
All **64 complete trajectories and 49,581 decisions** replay-verified with
fresh pinned native engines. Their separate visibility audit passed, including
480 hidden opponent-field choices and 117 opponent-hand choices. The ignored
checkpoint and replay directory are
`checkpoints/fv19_fourroles_selfplay_2820_2883.pt` and
`replays/selfplay_fourroles_2820_2883/`.

A direct child-versus-parent evaluation used Chaos Control, Warrior, and a
Flip Control guide list, whose exact Main Deck compositions were absent from
both checkpoints' training records. All three pairings, both deck assignments,
both seats, and seeds 2900–2907 produced **96 terminal duels** and **48,168
decisions**. The child scored **42–54** (43.75% of points; paired-bootstrap
95% interval **37.5–48.96%**). Assigned-deck results were Chaos Control
**9–23**, Flip Control **7–25**, and Warrior **26–6**; the seat split was
21–27 in either seat. The four-worker tournament took **39.37 seconds** on
the reported x86_64 machine. Its ignored report is
`artifacts/fv19_fourroles_selfplay_vs_parent_2900_2907.json` (SHA-256
`abb3a47079dd08eac5a8ed58c87aa8d771cb6bc1798166f698455bca5797956c`).
This run is evidence against promoting the child on the tested deck schedule;
it does not establish that every self-play algorithm or hyperparameter fails.

An off-policy scorecard on eight independently reviewed, non-training
decisions retained the parent's ranks: the five seed-2612 alternatives still
ranked 2nd, and the three BLS/MST corrections still ranked 2nd, 3rd, and
4th. Its ignored report is
`artifacts/fv19_fourroles_selfplay_review_scorecard.json` (SHA-256
`054f0d8d427a5eece26bc8f063d9b0a4089f8d632ba9c6339f9ca1731936285a`).
This diagnostic does not explain the match loss by itself, but it shows the
64-game update did not correct those replay errors. The next RL experiment
should address high-variance terminal returns and deck-specific transfer,
with a value baseline or another justified algorithm compared on the same
held-out families before promotion.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_self_play.py \
  checkpoints/tactical_v3_fv19_2500_2503.pt --engine experimental \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/bazoo_return_weirdchamp_worlds.ydk \
            examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --schedule-mode four_roles --baseline-scope learner_deck \
  --seed 2820 --games 64 --learning-rate 0.0003 \
  --learner-temperature 2.0 --entropy-coefficient 0.01 \
  --snapshot-every 8 --max-snapshots 8 --max-decisions 3000 \
  --record-dir replays/selfplay_fourroles_2820_2883 \
  --output checkpoints/fv19_fourroles_selfplay_2820_2883.pt
```

## Visible-state value baseline smoke test

An opt-in Monte Carlo critic was initialized alongside the unchanged
feature-19 parent and trained for one four-role cycle on Goat Control versus
Chaos Turbo, seeds 3000–3003. All four native duels terminated under the
3,000-decision cap (three learner wins and one loss against the training
opponent mixture). The run recorded 574 learner decisions. The four saved
trajectories replay-verified for **4,145 total decisions** with fresh pinned
native engines; the visibility audit passed, including 122 opponent-field,
38 hidden-field, and nine opponent-hand choices. The checkpoint contains the
critic architecture and weights; the ignored local artifacts are
`checkpoints/fv19_value_smoke_3000.pt` and
`replays/selfplay_value_smoke_3000/`. This checks integration and replay
determinism only. A matched held-out comparison with the existing per-deck
moving baseline is still needed before any playing-strength claim.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_self_play.py \
  checkpoints/tactical_v3_fv19_2500_2503.pt --engine experimental \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/chaos_turbo_riclar_2020.ydk \
  --schedule-mode four_roles --baseline-scope state_value \
  --value-width 32 --value-learning-rate 0.001 \
  --seed 3000 --games 4 --max-decisions 3000 \
  --record-dir replays/selfplay_value_smoke_3000 \
  --output checkpoints/fv19_value_smoke_3000.pt
```

## Matched visible-state value-baseline comparison

The visible-state Monte Carlo critic was tested against the earlier per-deck
moving-baseline self-play run. Both children started from the same unchanged
feature-19 checkpoint and used the same four training decks, seeds 2820–2883,
four-role deck/seat schedule, learning rate 0.0003, sampling temperature 2.0,
entropy coefficient 0.01, eight-game snapshot interval, and 75% historical
opponent probability. The only intended training change was the baseline:
the new child fitted a width-32 critic to terminal returns at learning rate
0.001. All **64 native games terminated** within 3,000 decisions, with 7,948
learner decisions, 36 wins, 28 losses, and no draws against its own changing
training-opponent mixture. These training wins cannot be compared directly
with the scalar child's 28–33–3 result because their policies and snapshot
pools diverged during training. All **64 complete trajectories and 49,531
decisions** replay-verified with fresh pinned engines and passed the separate
visibility audit. The ignored checkpoint is
`checkpoints/fv19_fourroles_value_2820_2883.pt` (SHA-256
`29e4c43938044c286ac4f6b312fdcca669de3b30db84089b952bd549037c2ea8`);
the ignored recordings are in `replays/selfplay_fourroles_value_2820_2883/`.
They now record the parent checkpoint hash, episode index, temperature, and
sampled-action method for replay review.

The two children then played each other on the same held-out Chaos Control,
Warrior, and Flip Control pairings used for the earlier child-versus-parent
check: both deck assignments, both seats, and seeds 2900–2907. The evaluator
rejected any Main Deck composition present in either checkpoint's training
games. Across **96 terminal duels**, the value child scored **49 wins, 46
losses, and one draw**, or **51.56%** of points; its paired-bootstrap 95%
interval was **46.35–56.77%**. By assigned deck it scored Chaos Control
12–20, Flip Control 9–22–1, and Warrior 28–4. The four-worker tournament took
**41.84 seconds** and averaged 523.04 decisions per duel. The ignored report
is `artifacts/fv19_value_vs_scalar_2900_2907.json` (SHA-256
`4f6d2c6fccb19aab1c67a188577c779a013ad533b7c3896dfff420d94254993d`).

On the same held-out schedule against the unchanged parent, the value child
scored **44–52** (**45.83%** of points; paired-bootstrap 95% interval
**40.63–50.00%**), with assigned-deck results of Chaos Control 10–22,
Flip Control 9–23, and Warrior 25–7. The four-worker tournament took
**42.58 seconds**. Its ignored report is
`artifacts/fv19_value_vs_parent_2900_2907.json` (SHA-256
`6f90d3df22952061507ed76a3b1bd6191bc335b2fca66a64b12e50eba2e5a3af`).
The parent remains the stronger evidence-backed choice on this schedule.
The critic reduced neither the known transfer loss nor the observed weakness
on Chaos Control and Flip Control enough to justify promotion.

Eight separately reviewed, non-training decisions were scored without
changing weights: the value child ranked one reviewed alternative first,
six second, and one fourth. This is a narrow fixed-state diagnostic, not a
playing-strength estimate. Its ignored report is
`artifacts/fv19_value_review_scorecard.json` (SHA-256
`d4053c8f839bbda2619f722a530b68a1168cb42f23b23472bd24615be44ed2f9`).
Further RL changes should address action and target valuation with
player-visible context and use a fresh held-out deck and seed schedule for
checkpoint selection. Do not relabel sampled self-play mistakes as expert
actions or infer success from training-opponent wins.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_self_play.py \
  checkpoints/tactical_v3_fv19_2500_2503.pt --engine experimental \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/bazoo_return_weirdchamp_worlds.ydk \
            examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --schedule-mode four_roles --baseline-scope state_value \
  --value-width 32 --value-learning-rate 0.001 --seed 2820 --games 64 \
  --learning-rate 0.0003 --learner-temperature 2.0 \
  --entropy-coefficient 0.01 --snapshot-every 8 --max-snapshots 8 \
  --max-decisions 3000 --record-dir replays/selfplay_fourroles_value_2820_2883 \
  --output checkpoints/fv19_fourroles_value_2820_2883.pt
```

## Four-review preference update against a frozen parent

An opt-in preference experiment started from the unchanged feature-19 parent
(`checkpoints/tactical_v3_fv19_2500_2503.pt`, SHA-256
`fe197724523b33a8d555e90ab9f7b669dab2081b000346b9b31d1788d7e07fc2`).
Four self-play review files compared acceptable and disfavored legal-action
sets at the Magician of Faith, Heavy Storm, Breaker, and Mystical Space
Typhoon decisions documented in [replay audit](replay_audit.md). Each complete
source duel replay-verified with the pinned native engine and passed the
visibility audit. None of the four source seeds or exact replays trained the
parent. The learner used 200 optimizer steps, learning rate 0.0001, and
pairwise logistic preference loss plus weight-1 frozen-parent KL. It sampled
64 multi-option preservation decisions from four replay-verified trajectories
already in the parent's training provenance, drawing 16 per step. The
preference loss fell from 1.1160 to 0.5113; final sampled preservation KL was
0.00537. These are optimization diagnostics, not playing-strength results.

On the **four training decisions**, preferred-minus-disfavored log-mean-exp
margins moved from −2.253 to −1.125 (Faith), +0.583 to +1.932 (Heavy Storm),
+0.019 to +1.439 (Breaker), and −0.515 to +1.116 (MST). The child's greedy
choice belonged to a preferred set for Heavy Storm and Breaker only. In
particular, setting Magician of Faith still ranked fifth in that state.
The ignored checkpoint is
`checkpoints/tactical_v3_fv19_preference4_parent_kl_3100.pt` (SHA-256
`b9dbd7fced686f719bcef24eea070e2167d726d302fd3d475da25b525098d28e`);
the ignored corrected-state report is
`artifacts/feature19_preference4_child_scorecard.json` (SHA-256
`c0f309b02e1896eefd8c7bdba1146b9faa88f9e745c93517a5c095edf319b24b`).

The child then played its unchanged parent on held-out Chaos Control, Warrior,
and Flip Control Main Deck compositions, all three deck pairings in both
assignments and both seats, seeds 3200–3207. The evaluator enforced unseen
Main Deck compositions against both checkpoint provenances. All **96 duels
terminated** within 3,000 decisions. The child scored **49–47**, or **51.04%**;
its paired-bootstrap 95% score interval was **44.79–57.29%**. As the assigned
deck it scored Chaos Control 11–21, Flip Control 9–23, and Warrior 29–3. This
large deck dependence and an interval spanning 50% do not justify promoting
the child. The four-worker tournament took **51.05 seconds** and averaged
673.35 decisions per duel. The ignored report is
`artifacts/feature19_preference4_vs_parent_3200_3207.json` (SHA-256
`f843043fa7699336ab6eddafe6693b3d4ec8f3ef5d65a9bfdfc375b0554a01d3`).
The current parent remains the reference checkpoint. More independently
reviewed, varied decisions and a separate held-out tournament are needed
before preference learning can claim a competitive gain.

## Exact Type-bit action representation and five-review fit

The verified Tribe-Infecting Virus replay at viewer frame 115 exposed a
representation fault: feature version 19 encoded Spellcaster (`2`), Aqua
(`64`), and Beast (`16384`) Type masks as approximately 0.0000000005,
0.000000015, and 0.000003815. Its three action logits were effectively tied;
the greedy first action named Spellcaster, destroying two own Spies instead
of four opposing Sheep Tokens. The replay-bound Beast-over-Spellcaster
preference and the player-visible evidence are in [replay audit](replay_audit.md).
Feature version 20 replaces the two scaled-mask numbers with 64 exact bit
features. It does not change legal actions, rules, or hidden information.
Feature-19 checkpoints keep their earlier encoder and remain loadable.

A width-16, one-epoch feature-20 clone trained on the **same 6,014 tactical
teacher decisions** as the feature-19 parent, from the same 16 replay-verified
seed-2500–2503 trajectories (batch size 32, learning rate 0.001, seed 19).
Its epoch loss was 0.3258. The ignored checkpoint is
`checkpoints/tactical_v3_fv20_typebits_2500_2503.pt` (SHA-256
`1d9073e2b8cfb2ccef6591a8787ab59b074f3ad8b737b3cd72848ca9f4e4938d`).
Only eight teacher choices announced a Type, none chose Beast, so this data
cannot teach the reviewed four-Token line by direct imitation. On the
reviewed state, the new clone distinguished the actions but still selected
Spellcaster; Beast ranked second. The scored report is
`artifacts/feature20_tribe_spies_tokens_preference_scorecard.json` (SHA-256
`b8f0564436dda284b99713eeba7325ea3563a47e5d3e7a8b51feaa9048910566`).

On three held-out Main Deck pairings (Chaos Control, Warrior, Flip Control),
both assignments and seats, seeds 3300–3307, the feature-20 clone scored
**42–53–1** in **96 terminal duels** against the unchanged feature-19 clone:
**44.27%** of points, paired-bootstrap 95% interval **37.50–51.04%**. Its
assigned-deck splits were Chaos Control 11–21, Flip Control 6–26, and Warrior
25–6–1. The evaluator enforced Main Deck compositions unseen in either
checkpoint. The four-worker tournament took **40.95 seconds**. This does not
show a generalization or playing-strength gain; widening the action layer
also changes model capacity, so this is not an isolated Type-encoding
ablation. The ignored report is
`artifacts/feature20_typebits_vs_feature19_3300_3307.json` (SHA-256
`57e62fdfcd3836c7762bedac714aa16af7455631ff5a3afb52b01d2f5aaddbb1`).

A separate opt-in preference update used the new Tribe review plus the four
earlier Faith, Heavy Storm, Breaker, and MST reviews, with 200 steps, learning
rate 0.0001, weight-1 frozen-parent KL, and 64 sampled preservation states
from four parent-provenance trajectories. All five source duels and all four
preservation duels replay-verified and passed visibility audits. Preference
loss fell from 0.9058 to 0.4753; final sampled KL was 0.00443. On the **five
training decisions**, the child ranked the preferred action/set first for
Tribe, Heavy Storm, Breaker, and MST; Faith Set still ranked fourth. Its
ignored checkpoint is `checkpoints/tactical_v3_fv20_preference5_parent_kl_3100.pt`
(SHA-256 `98c646227574dbd0b7cf09b1713b09ce3fa752566d39385b654c6a382afc51a3`),
and its fixed-state scorecard is
`artifacts/feature20_preference5_child_scorecard.json` (SHA-256
`c473344db2d58b48123078f827bd990c1bd334686bcc807821290dc5eaef4f3a`).

Against the unchanged feature-20 parent on the same three unseen deck
families, both assignments and seats, fresh seeds 3400–3407, the updated
child scored **49–47** over **96 terminal duels**: **51.04%** of points,
paired-bootstrap 95% interval **46.88–55.21%**. Its assigned-deck splits
were Chaos Control 13–19, Flip Control 5–27, and Warrior 31–1. The
four-worker tournament took **41.63 seconds** and averaged 545.01 decisions
per duel. The ignored report is
`artifacts/feature20_preference5_vs_base_3400_3407.json` (SHA-256
`4eb31bcc083efa67cb78509f0a487446e5fd711957aff0574c78062de284fb8e`).
The tiny review set corrected a concrete state, but neither held-out
comparison supports promoting a new checkpoint. Broader player-visible
Type/context examples and independently reviewed decisions are needed.

## Current public Type and Tribe / DNA Surgery compatibility

Schema v24 now carries ocgcore's current Type mask for each face-up field
monster, including changes made by DNA Surgery. Both player-scoped views
agree on that public field value; face-down field cards have no Type value.
The native query decoder checks the full unsigned 64-bit mask. Older replay
schemas omit the new field when replay-verified, so saved schema-v23 policy
and self-play games remain usable. As a compatibility check after the change,
`policy_batch_v19_jesse_daryl_2644_p1.json` replay-verified **801** decisions
and `selfplay_value_smoke_3000/episode_00001_seed_3001.json` verified **629**.
The older Tribe preference scorecard reproduced its original byte hash
`2fbd3e4c5de5c61a009c5f3399ef81bb581bdd56fb16f01da36edacafe5a74cb`
after the schema change.

The sourced [historical Tribe ruling](https://beta.goatformat.com/cards/tribe-infecting-virus)
and [DNA Surgery card text](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=4951&ope=2&request_locale=en)
motivate a paired seed-18 native fixture. Tribe discards Sinister Serpent and
declares Reptile against face-up Gagagigo. Passing DNA Surgery destroys
Gagagigo; chaining DNA and declaring Aqua changes both face-up monsters to
Aqua before Tribe resolves, so Gagagigo survives. Both branches ran to
terminal, serialized, and replay-verified. `tests/test_historical_tribe_dna_surgery.py`
passed **2/2** with the pinned native assets. This checks a documented
interaction and the observation boundary; it is not a duel-throughput
benchmark or evidence of policy strength. TacticalHeuristicAgent is now
version 4 because its Tribe choices use current public Type when available;
older schema-v23 demonstrations retain their recorded version-3 provenance.

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai OMP_NUM_THREADS=1 \
  .venv/bin/python -m pytest -q tests/test_historical_tribe_dna_surgery.py
```

A new feature-20 checkpoint versus TacticalHeuristicAgent v4 smoke duel on
Chaos Control/Warrior, seed 3500, completed in **287 decisions**. All 287
schema-v24 decisions replay-verified, including face-up current-Type values;
the policy replay auditor reproduced **143/143** recorded policy choices and
passed its visibility audit. The policy lost this single duel, which is a
pipeline check rather than a strength estimate. The ignored recording is
`replays/schema24_fv20_smoke_3500.json` (SHA-256
`3550b241f12dbcf282023693647f40c8292f3f005f4208ca3c15e177bdae0635`);
its ignored audit report is `artifacts/schema24_fv20_smoke_audit_3500.json`
(SHA-256 `5b398fe6b2a96678fa851edf3dd331e08f3684c08c9304a1581c986e7630e1e7`).

## Current-Type action relation smoke test

Feature version 21 adds four public action features to `announce_race`:
matching opponent and own face-up monster counts and their current ATK sums.
The relation uses ocgcore's current Type mask, so DNA Surgery changes the
feature without changing a monster's printed card identity. A contract test
swaps public Types between two otherwise identical field states: feature 20
gives the same Type-action numeric features in both, while feature 21 changes
them and keeps a face-down card excluded.

The schema-v23 greedy-policy replay
`replays/policy_batch_v19_daryl_cas_2647_p1.json` was verified and replayed
into a separate schema-v24 file. The upgraded replay again verified all
**1,212** decisions; the policy auditor reproduced **632/632** recorded
choices. At the self-destructive Tribe decisions, viewer frames **252** and
**358**, the new features correctly show zero matching opposing monsters and
one matching own monster. The generated file is ignored at
`replays/schema24_upgraded_daryl_cas_2647_p1.json` (SHA-256
`153030750f1099a91a9817181daf7c309569edeedc3a03c03013ba1aed52e9db`).

Using this **same single policy-generated game** as imitation data, width 16,
seed 21, one epoch, batch size 16, feature 20 ended at mean training loss
**0.3137398898**, while feature 21 ended at **0.3253146349**. Both trained on
**632** policy-seat decisions and both saved loadable checkpoints. The loss
numbers do not compare playing strength: the source policy itself made the
Tribe mistakes, there is no held-out game here, and model dimensions differ.
The ignored checkpoint SHA-256 values are
`eb6d27e0762b1d1b529612a25e09f20c402fc443b8e0029f198e404b4b324d55`
for feature 20 and
`5c516784c1b8b88b55e91feb8eb469f6efb1514040f62c5e0083489e39131724`
for feature 21.
Feature 21 remains an experiment until independently reviewed Type choices
and held-out, seat-swapped cross-deck results support promotion.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/upgrade_trajectory_schema.py \
  replays/policy_batch_v19_daryl_cas_2647_p1.json \
  --engine experimental --native-root .cache/goat-ai \
  --output replays/schema24_upgraded_daryl_cas_2647_p1.json
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_behavioral_clone.py \
  replays/schema24_upgraded_daryl_cas_2647_p1.json \
  --engine experimental --native-root .cache/goat-ai \
  --feature-version 21 --epochs 1 --width 16 --batch-size 16 --seed 21 \
  --output .cache/goat-ai/fv21_smoke_2647.pt
```

## Same-data current-Type relation comparison

Eight schema-v23 TacticalHeuristicAgent v3 versus CombatHeuristicAgent v3
games on Cas Stomphorst Flip Control and Daryl Gessler Gravekeepers were
independently replay-verified and upgraded to schema v24. Their original
files were left unchanged. Both models trained on the same **2,459** teacher
decisions, two epochs, width 32, batch size 16, seed 21, using the pinned
experimental engine. Feature 20 ended with mean training loss **0.2396365**;
feature 21 ended at **0.2360020**. These training losses are not a strength
comparison.

The existing policy-review preference at viewer frame 115 of the separate
Jesse/Daryl seed-2644 game was transferred to its verified schema-v24 replay.
The preferred Beast choice and disfavored recorded Spellcaster choice kept
their legal indices. Neither the exact replay nor its seed was in either
checkpoint's training provenance. Feature 20 ranked Beast **2nd of 3** and
chose Spellcaster (preference margin **−1.011**); feature 21 ranked Beast
**1st of 3** (margin **+0.127**). Both models chose the visibly favorable
opponent Type in two further seed-2647 fixed-state probes. This is one
independently reviewed decision, not a playing-strength estimate.

The direct held-out match used seeds **3600–3607**, two published matchup
pairs (Chaos Control/Warrior and Flip Control/Chaos Return), both deck
assignments, and both seats. The evaluator rejected any Main Deck composition
seen in either checkpoint's training games. All **64** duels terminated below
the 3,000-decision cap. Feature 21 scored **33–31** against feature 20, a
**51.56%** score rate with a paired 95% bootstrap interval of
**43.75%–59.38%**. By feature-21 deck, the splits were Chaos Control **5–11**,
Warrior **11–5**, Flip Control **7–9**, and Chaos Return **10–6**. This does
not establish a competitive improvement or justify promoting feature 21;
the deck dependence and limited independent review coverage call for more
examples and a fresh evaluation schedule.

The ignored checkpoints are
`.cache/goat-ai/fv20_casdaryl_schema24_control.pt` (SHA-256
`504ff955c6c5876e2e55863193003697cbcc4b3b81d03a302b0587751c23e1fc`)
and `.cache/goat-ai/fv21_casdaryl_schema24_experiment.pt` (SHA-256
`c6cc59780d665edf2c83b143d1b371e9aa05fcfff5ac988edfc48613ccd21011`).
The ignored tournament report is
`artifacts/fv21_vs_fv20_type_relation_3600_3607.json` (SHA-256
`6ea4a5da9be88eb3af9e7fb964f9d0525041d1ccb6664d273cc47d0124cca3b5`).
Reproduce the competition after upgrading the teacher replays with
`scripts/upgrade_trajectory_schema.py` and training both feature versions:

```bash
mkdir -p replays/tactical_v3_cas_daryl_schema24_2500_2503
for replay_file in replays/tactical_v3_cas_daryl_2500_2503/*.json; do
  OMP_NUM_THREADS=1 .venv/bin/python scripts/upgrade_trajectory_schema.py \
    "$replay_file" --engine experimental --native-root .cache/goat-ai \
    --output "replays/tactical_v3_cas_daryl_schema24_2500_2503/$(basename "$replay_file")"
done
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_behavioral_clone.py \
  replays/tactical_v3_cas_daryl_schema24_2500_2503/*.json \
  --engine experimental --native-root .cache/goat-ai \
  --feature-version 20 --epochs 2 --width 32 --batch-size 16 --seed 21 \
  --output .cache/goat-ai/fv20_casdaryl_schema24_control.pt
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_behavioral_clone.py \
  replays/tactical_v3_cas_daryl_schema24_2500_2503/*.json \
  --engine experimental --native-root .cache/goat-ai \
  --feature-version 21 --epochs 2 --width 32 --batch-size 16 --seed 21 \
  --output .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --opponent-checkpoint .cache/goat-ai/fv20_casdaryl_schema24_control.pt \
  --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk \
  --matchup examples/decks/flip_control_goatformat_guide.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 3600 --seeds 8 --max-decisions 3000 --workers 2 \
  --output artifacts/fv21_vs_fv20_type_relation_3600_3607.json
```

## Feature-21 Magician of Faith review update

A fresh feature-21 policy game against TacticalHeuristicAgent v4 on Chaos
Control/Warrior, seed **3700**, policy seat 0, completed in **358** decisions
and replay-verified. The policy auditor reproduced **177/177** policy
decisions. At viewer frame **22**, the policy Normal Summoned Magician of
Faith in 300 ATK with no monsters on either side; Set of the same card was
legal and useful Spells were already in its Graveyard. The policy lost this
duel. This is a concrete replay review, not a strength estimate.

A SHA-256-bound `policy_review` preference labels Set over the recorded
Summon. The unchanged feature-21 parent ranked Set **4th of 10** with a
Set-minus-Summon logit margin of **−0.405**. A 200-step parent-KL update
using this one label and **128** sampled preservation states from all eight
parent-training trajectories moved Set to **1st** with margin **+1.595**;
last preservation KL was **0.0371**. The child checkpoint is ignored at
`.cache/goat-ai/fv21_faith_review_child_3700.pt` (SHA-256
`b05ae2b3e7f77f4f9ebbaf94394286e1d584faf1a4ee8cb4d0717628d184ba95`).

A direct held-out comparison against the frozen feature-21 parent used seeds
**3800–3807**, both seats, both deck assignments, and two matchup pairs:
Flip Control/Chaos Return and Goat Control/Chaos Turbo. The evaluator
confirmed all four Main Deck compositions were absent from both checkpoints'
training games. All **64** games completed below 3,000 decisions. The child
went **31–29–4**, scoring **51.56%** with paired 95% bootstrap interval
**41.41%–60.94%**. By child deck, its decisive splits were Chaos Return
**8–5**, Chaos Turbo **6–10**, Flip Control **5–10**, and Goat Control
**12–4**. This wide, deck-dependent result does **not** establish improved
playing strength. Keep the parent as the reference; gather independent
Faith contexts and test a fresh schedule before trying to promote a child.
The ignored tournament report is
`artifacts/fv21_faith_child_vs_parent_3800_3807.json` (SHA-256
`893641fe18ee50998e01f58b0f61a777b9dcfd7608c7fcf55ad34ac3cd2189b8`).

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/record_policy_match.py \
  .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --deck1 examples/decks/chaos_control_insids_worlds_2022.ydk \
  --deck2 examples/decks/warrior_montague_clash.ydk \
  --seed 3700 --policy-seat 0 --opponent tactical --max-decisions 3000 \
  --output replays/fv21_vs_tactical_3700_p0.json
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv21_faith_review_child_3700.pt \
  --opponent-checkpoint .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/flip_control_goatformat_guide.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 3800 --seeds 8 --max-decisions 3000 --workers 2 \
  --output artifacts/fv21_faith_child_vs_parent_3800_3807.json
```

## Ring / Rush historical rule fixture

The pinned pre-errata Ring (`511000824`) and GOAT Rush Recklessly
(`504700114`) scripts were exercised in three seed-316 complete duels.
Ring's unmodified 1900-ATK target caused **1900** damage to each player;
chaining Rush raised it to 2600 ATK before Ring resolved and caused
**2600** damage to each player. In the reverse chain order, Ring destroyed
the target before Rush resolved and dealt **1900** instead. All three
trajectories passed the player-visible audit and replay-verified against
fresh native engines. The native pytest command below passed **3/3** cases
in **12.71 seconds**. This is a sourced rules regression, not a duel-throughput
benchmark.

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai OMP_NUM_THREADS=1 \
  .venv/bin/python -m pytest -q tests/test_historical_ring_rush_recklessly.py
```

## Four-review Faith and Ring policy update

Four new complete feature-21 policy games against TacticalHeuristicAgent v4
used different policy decks at seeds **3900–3903**; all replay-verified and
passed the player-visible audit. Two games exposed another Magician of Faith
Normal Summon despite a legal Set, and one exposed Ring targeting the
policy's own Faith while an opposing 2300-ATK Chaos Sorcerer was legal and
safe by the acting player's 5800 LP. Three SHA-256-bound `policy_review`
files cover those decisions plus the seed-3700 Faith decision. None of the
three source replays or their seeds were in the unchanged parent's training
provenance. The parent ranked the preferred actions **4th, 2nd, 2nd, and
5th** at those four frames.

A 200-step parent-KL update used all **4** reviewed preferences and **128**
sampled preservation decisions across the eight parent-training games.
Its preference loss went from **1.1465** to **0.1952**, with last preservation
KL **0.0381**. It ranked all four preferred actions **1st** at their training
frames. The ignored child checkpoint is
`.cache/goat-ai/fv21_faith_ring_four_review_child.pt` (SHA-256
`77f34e1cc722542cb746053fd27c247c6a8b0c21cc0ddfc0c8b862f1539421e0`).

On fresh seeds **4000–4007**, two unseen-composition matchup pairs (Flip
Control/Chaos Return and Matt Peddle Goat Control/Dimension Fusion Turbo),
both deck assignments, and both seats, the child scored **31–32–1** in **64**
completed duels against its frozen parent. Its score rate was **49.22%**,
with a paired 95% bootstrap interval of **39.06%–58.59%**. By child deck,
the decisive splits were Chaos Return **11–4**, Dimension Fusion Turbo
**9–7**, Flip Control **5–11**, and Goat Control **6–10**. The result is
inconclusive overall and poor on two deck roles, so the child is **not
promoted**. The ignored tournament report is
`artifacts/fv21_four_review_child_vs_parent_4000_4007.json` (SHA-256
`bb5e8477286dc65d1757aaefa2a60d1c9b5054fd3a44e599384637dd6749cb79`).
The fixed-state correction did not establish a general Faith strategy; a
future representation should expose Flip-effect and Graveyard Spell context
to the action scorer, then use a new held-out comparison.

```bash
preserve_args=()
for replay_file in replays/tactical_v3_cas_daryl_schema24_2500_2503/*.json; do
  preserve_args+=(--preserve-trajectory "$replay_file")
done
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_review_preferences.py \
  .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --case replays/fv21_vs_tactical_3700_p0.json examples/preferences/feature21_faith_set_3700_p0.preference.json \
  --case replays/fv21_review_scan_3900_3903/seed_3900_seat_0.json examples/preferences/feature21_faith_set_3900_p0.preference.json \
  --case replays/fv21_review_scan_3900_3903/seed_3903_seat_0.json examples/preferences/feature21_faith_ring_3903_p0.preference.json \
  "${preserve_args[@]}" --native-root .cache/goat-ai \
  --steps 200 --preserve-per-trajectory 16 --preserve-batch 16 \
  --parent-kl-weight 1 --learning-rate 0.0001 --seed 21 \
  --output .cache/goat-ai/fv21_faith_ring_four_review_child.pt
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv21_faith_ring_four_review_child.pt \
  --opponent-checkpoint .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/flip_control_goatformat_guide.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk examples/decks/dimension_fusion_turbo_goatformat_guide.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 4000 --seeds 8 --max-decisions 3000 --workers 2 \
  --output artifacts/fv21_four_review_child_vs_parent_4000_4007.json
```

## Printed Flip and public resource relation experiment

Opt-in feature version **22** adds eight action inputs from the acting
player's observation: printed Flip Type, printed ATK, own Graveyard Spell
count, each side's visible backrow and monster counts, and a selected
face-up target's current ATK. Printed properties for the **1,685** allowed
card IDs come from the pinned CDBs and are saved in the checkpoint so
inference does not depend on querying a live simulator database. Unknown
opponent cards have no identity-derived feature. Older checkpoints and the
default feature version retain their previous encodings.

Training used the same eight schema-v24 Tactical v3 demonstrations and
configuration as the feature-21 reference: **2,459** teacher decisions,
two epochs, width 32, batch size 16, seed 21. The two epoch losses were
**0.3108** and **0.2355**. These training losses do not compare playing
strength. The ignored checkpoint is
`.cache/goat-ai/fv22_casdaryl_schema24_experiment.pt` (SHA-256
`4d86762f705913beb4438c3356a9be6bf4ac877a7f8ccb6244ccd63985496d6f`).
The reviewed replay decisions were absent from its training data. On four
earlier Faith/Ring decisions, the feature-22 clone ranked the preferred
alternatives **2nd, 1st,
2nd, and 4th**, compared with **4th, 2nd, 2nd, and 5th** for the feature-21
reference. It chose a preferred action at only **one** of the four. The
ignored scorecard is `artifacts/fv22_four_review_scorecard.json` (SHA-256
`327e7c39dd0aaf4141be81896317f7e8b981e5f9067213380b9779f8bf85905b`).
On two newly reviewed Thunder decisions, feature 22 ranked Thunder-before-
Pot **4th** and taking both search copies **2nd**; feature 21 ranked them
**3rd** and **2nd**. The additional representation did not fix these choices.

Against the frozen feature-21 reference, feature 22 scored **36–27–1**
on 64 complete unseen-composition duels at seeds **4100–4107**, both seats
and deck assignments. Its point score was **57.03%**, paired 95% bootstrap
interval **47.66%–65.63%**. A second, different unseen-composition schedule
at seeds **4200–4207** scored **28–34–2** over 64 complete duels, point score
**45.31%**, interval **33.59%–57.03%**. Across the two schedules the raw
count was **64–61–3**; no pooled confidence interval was computed. Flip
Control went **3–13** on the first schedule; Chaos Control and Chaos Turbo
each went **5–11** on the second. These intervals and deck splits do not
establish a general improvement, so feature 22 remains experimental and
feature 21 remains the reference. The ignored reports are
`artifacts/fv22_vs_fv21_4100_4107.json` (SHA-256
`1859517839722c28637f867effa46817b97b60ab42a23e1795cdb134dda28c57`)
and `artifacts/fv22_vs_fv21_4200_4207.json` (SHA-256
`9a0d36214303aac18fb522e25e2033eb324c59d8173efd4b521655aa658d69c8`).
The tournament wall times were **65.58** and **95.14** seconds on two
workers; these are measured run times, not a general throughput claim.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_behavioral_clone.py \
  replays/tactical_v3_cas_daryl_schema24_2500_2503/*.json \
  --engine experimental --native-root .cache/goat-ai \
  --feature-version 22 --epochs 2 --width 32 --batch-size 16 --seed 21 \
  --output .cache/goat-ai/fv22_casdaryl_schema24_experiment.pt
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv22_casdaryl_schema24_experiment.pt \
  --opponent-checkpoint .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/flip_control_goatformat_guide.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk examples/decks/dimension_fusion_turbo_goatformat_guide.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 4100 --seeds 8 --max-decisions 3000 --workers 2 \
  --output artifacts/fv22_vs_fv21_4100_4107.json
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv22_casdaryl_schema24_experiment.pt \
  --opponent-checkpoint .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk \
  --matchup examples/decks/chaos_turbo_riclar_2020.ydk examples/decks/goat_control_lolmarcus_2020.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 4200 --seeds 8 --max-decisions 3000 --workers 2 \
  --output artifacts/fv22_vs_fv21_4200_4207.json
```

## Sheep Token position-guard ablation

The feature-21 checkpoint was compared against an identical copy with the
optional `--position-guard` at inference, using unseen Main Deck compositions,
two sourced matchups, both deck assignments, both seats, seeds 4300–4307, and
a 3,000-decision cap. All **64** native duels terminated. The guarded seat
scored **31–33** (48.44%); its Wilson 95% decisive-win interval was
**36.63%–60.42%**. It scored **17–15** as first player and **14–18** as second.
The two-worker tournament took **104.18 s**, or **0.614 duels/s** and **632.68
decisions/s** on the recorded Linux x86_64 host. The ignored report is
`artifacts/fv21_position_guard_vs_plain_4300_4307.json`. These results do not
support promoting the guard as an overall playing-strength improvement. It
remains a targeted, optional fix for an observed Sheep Token blunder.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --opponent-checkpoint .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --position-guard --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 4300 --seeds 8 --max-decisions 3000 --workers 2 \
  --output artifacts/fv21_position_guard_vs_plain_4300_4307.json
```

## Experimental position-action feature version 23

The same eight replay-verified Tactical-v3 demonstration trajectories used by
the feature-21 reference trained a width-32 feature-v23 policy for two epochs,
seed 21, batch size 16, learning rate 0.001. It saw **2,459** teacher
choices, of which only **23** selected `change_position`. Mean training
cross-entropy was **0.30092** then **0.21869**. The ignored checkpoint is
`.cache/goat-ai/fv23_casdaryl_schema24_position_experiment.pt`.

On the *old* feature-21 seed-3901 decision states, v21 chose the recorded
0-ATK Sheep Token position change at all **12** flagged frames; v23 still
chose it at **9**. Across all 47 seat-0 decision states that offered a position
change in that replay, v21 selected one 33 times and v23 28 times. These are
counterfactual choices on fixed replay states, not a fresh game result. The
new action representation makes visible current monster stats available to
position-change scoring, but the small teacher set may not teach a reliable
position strategy.

Against the frozen feature-21 checkpoint on unseen Main Deck compositions,
feature 23 scored **33–30–1** over **64** native duels, seeds 4400–4407,
both seats and deck assignments, with a 3,000-decision cap. Its point score
was **52.34%** and the paired 95% bootstrap interval was **45.31%–59.38%**.
It went 16–16 as first player and 17–14–1 as second. Deck splits were
3–13 as Chaos Control, 11–5 as Chaos Turbo, 6–9–1 as Goat Control, and
13–3 as Warrior. All games terminated; the largest decision count was
1,987. The two-worker tournament took **105.61 s** (0.606 duels/s,
618.58 decisions/s on the recorded Linux x86_64 host). The ignored report is
`artifacts/fv23_vs_fv21_4400_4407.json`. This sample does not establish an
overall gain, and version 21 remains the reference.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_behavioral_clone.py \
  replays/tactical_v3_cas_daryl_schema24_2500_2503/*.json \
  --engine experimental --native-root .cache/goat-ai \
  --feature-version 23 --epochs 2 --width 32 --batch-size 16 --seed 21 \
  --output .cache/goat-ai/fv23_casdaryl_schema24_position_experiment.pt
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv23_casdaryl_schema24_position_experiment.pt \
  --opponent-checkpoint .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 4400 --seeds 8 --max-decisions 3000 --workers 2 \
  --output artifacts/fv23_vs_fv21_4400_4407.json
```

## Sheep Token replay-preference pilot

A 12-decision retrospective annotation of the feature-21 seed-3901 replay
compares legal alternatives that preserve defending 0-ATK Sheep Tokens with
all legal changes of those tokens into attack. It is bound to the exact
replay hash and is an action preference, not a human gameplay recording.
`scripts/train_review_preferences.py` independently replay-verified and
visibility-audited the full source duel, then fit a width-32 feature-21 child
of the frozen reference with 150 pairwise parent-KL steps, 64 sampled
preservation states from four parent demonstration games, seed 23, learning
rate 0.0001, and KL weight 1.0. Preference loss moved from **1.23937** to
**0.08782**; the final sampled preservation KL was **0.04563**. On the 12
*training* decision states, the unchanged parent chose a disfavored token
switch at 12/12, while the child chose one at 0/12. This is evidence of fit
on the annotated replay, not generalization or stronger play. The ignored
checkpoint is `.cache/goat-ai/fv21_sheep_preference_3901_child.pt`; the
annotation is tracked under `examples/preferences/`.

The first planned tournament was correctly rejected by
`--require-unseen-main-decks` because its Matt Peddle Goat Control and Chaos
Turbo decks also appear in the preference replay. The held-out evaluation
uses Flip Control, Chaos Return, Chaos Control, and Warrior Main Decks instead.

The preference child scored **41–23** against its frozen parent on seeds
4500–4507 and **35–25–4** on fresh seeds 4600–4607, each a 64-duel,
seat-swapped, both-deck-assignment schedule on the four unseen Main Decks.
The paired-bootstrap 95% score intervals were **53.13%–75.00%** and
**46.09%–68.75%**, respectively. Pooling all 128 games gives **76–48–4**
(60.94% score; paired-bootstrap interval **52.73%–68.75%**), but these are
two schedules of the same deck families, not independent archetype coverage.
The pooled splits are **25–6–1 Chaos Return**, **25–7 Warrior**,
**14–17–1 Chaos Control**, and **12–18–2 Flip Control**. The favorable
aggregate is not a uniform cross-deck gain. Both tournaments terminated
within the decision cap (maximum 1,611 and 1,674 decisions); their two-worker
wall times were **78.98 s** and **71.91 s**. Ignored reports are
`artifacts/fv21_sheep_pref_vs_parent_4500_4507.json` and
`artifacts/fv21_sheep_pref_vs_parent_4600_4607.json`.

A read-only audit of three other old feature-21 replay state sequences found
**28 changed choices** across **319** multi-option policy decisions. Some
changes were into Battle Phase, and some chose `cancel` at card-selection
prompts. Three evaluation Main Decks contain no Scapegoat (Flip Control, Chaos
Return, and Warrior); Chaos Control has two copies, so the match result
cannot be attributed specifically to better Sheep Token defense. Parent-KL
regularization limited but did not localize the update. A matched comparison
against TacticalHeuristicAgent is needed before considering any checkpoint
promotion.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_review_preferences.py \
  .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --case replays/fv21_review_scan_3900_3903/seed_3901_seat_0.json examples/preferences/feature21_sheep_token_defense_3901_p0.preference.json \
  --preserve-trajectory replays/tactical_v3_cas_daryl_schema24_2500_2503/seed_2500_seat_0.json \
  --preserve-trajectory replays/tactical_v3_cas_daryl_schema24_2500_2503/seed_2500_seat_1.json \
  --preserve-trajectory replays/tactical_v3_cas_daryl_schema24_2500_2503/seed_2501_seat_0.json \
  --preserve-trajectory replays/tactical_v3_cas_daryl_schema24_2500_2503/seed_2501_seat_1.json \
  --steps 150 --preserve-per-trajectory 16 --preserve-batch 16 \
  --parent-kl-weight 1.0 --learning-rate 0.0001 --seed 23 \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/fv21_sheep_preference_3901_child.pt
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv21_sheep_preference_3901_child.pt \
  --opponent-checkpoint .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/flip_control_goatformat_guide.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 4500 --seeds 8 --max-decisions 3000 --workers 2 \
  --output artifacts/fv21_sheep_pref_vs_parent_4500_4507.json
# Repeat with --seed 4600 and the matching output path.
```

On a third held-out schedule, seeds 4700–4707 and the same four deck
compositions, the preference child scored **18–46** against
TacticalHeuristicAgent v6. The unchanged parent scored **15–47–2** against
that same opponent and game schedule. Their matched score difference was
**+3.13 percentage points**, with a paired-bootstrap 95% interval of
**−9.38 to +13.28 points**. The child's absolute score was **28.13%**
(paired interval **18.75%–35.94%**); it went **0–16** with Chaos Control.
All 128 baseline games terminated below 3,000 decisions. The two local
wall times were **36.92 s** and **35.64 s** on two workers. The ignored
reports are `artifacts/fv21_sheep_pref_vs_tactical_4700_4707.json` and
`artifacts/fv21_parent_vs_tactical_4700_4707.json`. Despite the favorable
child-versus-parent aggregate, this does not meet M4's absolute baseline
strength or cross-deck gate. Keep the child experimental.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv21_sheep_preference_3901_child.pt \
  --opponent tactical --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/flip_control_goatformat_guide.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 4700 --seeds 8 --max-decisions 3000 --workers 2 \
  --output artifacts/fv21_sheep_pref_vs_tactical_4700_4707.json
# Repeat with the parent checkpoint and matching parent report path.
```

For artifact identity, the child checkpoint SHA-256 is
`3c3040d0fd353f0289f68c54188a3f514d718d7d0424b388119879e764369a2c`.
The four report hashes in order (seeds 4500, 4600, child versus Tactical,
parent versus Tactical) are
`4e060a586d4c41305a56e7883ce998028615e0619e509f672040511042d14cbe`,
`1c91f924b4b60b8c757e68f7103cccaec4c49dfc19555001c8158e898e5f546f`,
`28ba40c736321ce59bbd363ae74ed94a163f382814ae0fe0853316aca255f10c`,
and
`fc1f4ec8521d0f3d37be494bdbca1664bc3dc162762cbb8b444565621dea7516`.

## Four-deck Tactical-v6 imitation pilot

To test whether broader, more recent tactical demonstrations help, the native
collector ran TacticalHeuristicAgent v6 against CombatHeuristicAgent v3 on
Matt Peddle Goat Control versus Riclar Chaos Turbo (seeds 4800–4803) and Cas
Stomphorst Flip Control versus Daryl Gessler Gravekeepers (seeds 4810–4813).
Both deck assignments were played through the teacher's two seats. All
**16** duels terminated below the 3,000-decision cap: **10,590** total
and **5,445** labeled teacher decisions. Tactical won **7/8** in the first
pair and **4/8** in the second. The 16 schema-v25 trajectory files are ignored
local artifacts under `replays/tactical_v6_matt_chaos_4800_4803/` and
`replays/tactical_v6_cas_daryl_4810_4813/`; they were independently replay-
verified and visibility-audited by the training command.

A feature-v23, width-32 policy trained on those **5,445** decisions for two
epochs, batch size 16, learning rate 0.001, seed 27. Mean training losses
were **0.28298** and **0.16654**. The ignored checkpoint
`.cache/goat-ai/fv23_tactical_v6_four_decks_4800_4813.pt` has SHA-256
`1f0b57d517fc7e2475b7d81b072ac0fda47ff1d744ef5855dd767e355586e090`.
Its checkpoint contains input trajectory, deck-composition, model-version,
and native-asset provenance. Training loss and teacher win rate do not prove
that the clone itself is strong; evaluate on other Main Decks.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/collect_heuristic_demos.py \
  --engine experimental --native-root .cache/goat-ai \
  --teacher tactical --opponent combat_heuristic \
  --deck-a examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
  --deck-b examples/decks/chaos_turbo_riclar_2020.ydk \
  --seed 4800 --seeds 4 --max-decisions 3000 \
  --output-dir replays/tactical_v6_matt_chaos_4800_4803
OMP_NUM_THREADS=1 .venv/bin/python scripts/collect_heuristic_demos.py \
  --engine experimental --native-root .cache/goat-ai \
  --teacher tactical --opponent combat_heuristic \
  --deck-a examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk \
  --deck-b examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --seed 4810 --seeds 4 --max-decisions 3000 \
  --output-dir replays/tactical_v6_cas_daryl_4810_4813
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_behavioral_clone.py \
  replays/tactical_v6_matt_chaos_4800_4803/*.json \
  replays/tactical_v6_cas_daryl_4810_4813/*.json \
  --engine experimental --native-root .cache/goat-ai \
  --feature-version 23 --epochs 2 --width 32 --batch-size 16 --seed 27 \
  --output .cache/goat-ai/fv23_tactical_v6_four_decks_4800_4813.pt
```

On four held-out schema-v25 Tactical-v6 versus Combat-v3 trajectories from
Flip Control/Chaos Return (seed 5000) and Chaos Control/Warrior (seed 5010),
both teacher seats, the trajectories replay-verified before scoring. The
broader feature-v23 clone matched the teacher on **221/267** multi-option
choices versus the old feature-v21 reference's **199/267**. This agreement
improves without establishing playing strength. Of the **11** held-out
`set_monster` choices, the unweighted clone matched **0**; nine misses were
face-up Normal Summons in place of the teacher's Sets for Dekoichi, Mask of
Darkness, or Magician of Faith. The ignored audit report is
`artifacts/fv23_tactical_v6_heldout_agreement_5000_5010.json`.

The unweighted feature-v23 clone scored **48–16** directly against the old
feature-v21 learned reference over 64 complete, seat-swapped, both-deck-
assignment games on unseen Flip Control, Chaos Return, Chaos Control, and
Warrior Main Deck compositions (seeds 4900–4907). Its paired-bootstrap 95%
score interval was **65.63%–82.81%**. Deck splits were **9–7** Flip Control,
**16–0** Chaos Return, **8–8** Chaos Control, and **15–1** Warrior. Both seats
went 24–8. The two-worker tournament took **63.15 s** locally; the maximum
game was 1,445 decisions. The ignored report is
`artifacts/fv23_tactical_v6_vs_fv21_4900_4907.json`.

Against Tactical-v6 on that exact schedule, the clone scored **14–48–2**
(23.44% score, paired interval **14.84%–32.03%**) while the old learned
reference scored **11–53** (17.19%). Their matched difference was
**+6.25 percentage points**, paired interval **−1.56 to +14.84**. The clone
went **4–27–1** as first player and **10–21–1** as second. The tactical
opponent remains substantially stronger; the direct learned-policy result
must not be read as a superhuman or even baseline-beating claim. The ignored
reports are `artifacts/fv23_tactical_v6_vs_tactical_4900_4907.json` and
`artifacts/fv21_vs_tactical_4900_4907.json`.

## Set-monster sampling ablation

In the four-deck Tactical-v6 data, only **34 of 5,445** selected teacher
choices were `set_monster`; **21** occurred at a multi-option opportunity
involving Dekoichi, Mask of Darkness, or Magician of Faith. The unweighted
clone chose none of the teacher's **11** held-out Set actions across four
verified evaluation trajectories, including nine face-up Normal Summons of
those Flip monsters instead. The cloning CLI now permits an opt-in selected-
action-kind sampling factor. A matched feature-v23 model used the same 16
source trajectories, architecture, two epochs, batch size, and seed as the
unweighted clone, but `--label-kind-weight set_monster=12`. It used weighted
sampling with replacement without increasing the number of optimizer
examples per epoch. Mean training losses were **0.30568** and **0.17738**;
these differ in sampling distribution and should not be compared directly
to the unweighted losses.

On the same four held-out teacher trajectories, the weighted model matched
**9/11** Set choices and **232/267** multi-option choices overall, versus
**0/11** and **221/267** for the unweighted model. This is an off-policy
imitation diagnostic, not competitive evidence. The ignored checkpoint
`.cache/goat-ai/fv23_tactical_v6_set12_4800_4813.pt` has SHA-256
`b32e5e91bba4fe75ccadfbbfa2de1992d20230020e8042d4533cf12658b602bd`
and explicitly records `label_kind_weights={set_monster: 12.0}`.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_behavioral_clone.py \
  replays/tactical_v6_matt_chaos_4800_4803/*.json \
  replays/tactical_v6_cas_daryl_4810_4813/*.json \
  --engine experimental --native-root .cache/goat-ai \
  --feature-version 23 --epochs 2 --width 32 --batch-size 16 --seed 27 \
  --label-kind-weight set_monster=12 \
  --output .cache/goat-ai/fv23_tactical_v6_set12_4800_4813.pt
```

The weighted model split **32–32** directly against the unweighted clone
on 64 complete native duels, seeds 5100–5107, both seats and deck assignments
on the same four unseen Main Deck compositions. The paired-bootstrap 95%
score interval was **43.75%–56.25%**. By assigned deck it went **4–12** Chaos
Control, **12–4** Chaos Return, **6–10** Flip Control, and **10–6** Warrior.
All games terminated under the cap (maximum 1,317 decisions); the two-worker
local run took **61.43 s**. The ignored report is
`artifacts/fv23_set12_vs_unweighted_5100_5107.json`. Improved Set-action
agreement did not translate into a measured overall competitive gain, so
weighting remains opt-in. This also reinforces why action imitation alone is
not M4's exit criterion.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv23_tactical_v6_set12_4800_4813.pt \
  --opponent-checkpoint .cache/goat-ai/fv23_tactical_v6_four_decks_4800_4813.pt \
  --engine experimental --native-root .cache/goat-ai \
  --matchup examples/decks/flip_control_goatformat_guide.ydk examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 5100 --seeds 8 --max-decisions 3000 --workers 2 \
  --output artifacts/fv23_set12_vs_unweighted_5100_5107.json
```

The five ignored report SHA-256 values, in the order the reports are named
above (new versus old, new versus Tactical, old versus Tactical, held-out
agreement, weighted versus unweighted), are
`793e6c87b268b42b8aca069d2070f9adc4c6ecd477ece87240f516146a49df16`,
`8be3cbce9ea5da157b4cf78186ad9c27730199c0b1f33e332c140ec681dae3d2`,
`e1180b280845881ea5b491e15afd46a2ef28adaa9826f684f04ff434c2aa94c2`,
`1f927478b735f9fa9130ce4cc73b054e88392bfce1249db5fbef9dc4694f8d9b`,
and `70c4d807a226e94b0331586ac5ba6d49b67155ec9b6f1680dbcd692bee4bc1f7`.

## Position guard v2: same-checkpoint ablation

The optional inference guard now preserves defending 0-ATK Sheep Tokens and
rejects attack-to-defense moves when the opponent has no monsters and the
moving monster's visible ATK is at least its DEF. This experiment compares
the **same feature-v21 checkpoint** (`c6cc59780d665edf2c83b143d1b371e9aa05fcfff5ac988edfc48613ccd21011`)
with and without that guard. Training used seeds 2500–2503 on Cas Stomphorst
and Daryl Gessler Main Decks. Evaluation required distinct Main Deck
compositions and used Chaos Control, Warrior, Chaos Return, and the Flip
Control guide list in two pairings, both deck assignments, and both agent
seats. The pinned native experimental adapter and four workers completed all
games below the 5,000-decision cap.

| Held-out seeds | Guard wins–losses–draws | Score | 95% paired-bootstrap score interval |
| --- | ---: | ---: | ---: |
| 4000–4007 | 35–26–3 | 57.0% | 52.3%–62.5% |
| 4100–4107 | 34–29–1 | 53.9% | 47.7%–61.7% |
| Combined | 69–55–4 | 55.5% | 51.2%–60.2% |

The combined first-seat score was 32–32; the second-seat score was 37–23
with four draws. By assigned deck, the guard scored 10–21–1 Chaos Control,
25–5–2 Chaos Return, 10–22 Flip Control, and 24–7–1 Warrior. The aggregate
advantage therefore depends strongly on deck and seat. A separate 64-duel
schedule against TacticalHeuristicAgent v7 on fresh seeds 4200–4207 scored
**14–49–1** (22.7% score; paired-bootstrap 95% interval 14.8%–30.5%).
This does not establish a competitive policy or close M4. Keep the guard
opt-in and collect stronger policy training evidence across deck families.

The ignored detailed reports are
`.cache/goat-ai/position_guard_v2_vs_unguarded_4000_4007.json`,
`.cache/goat-ai/position_guard_v2_vs_unguarded_4100_4107.json`, and
`.cache/goat-ai/position_guard_v2_vs_tactical_v7_4200_4207.json`, with
SHA-256 values `e4569381cb5604396178db877a458f47457b125e9471250e1a7fa9445630da71`,
`add644bf7a800b4df60d65ed79a0716779535ca8cb5f0cb14be7f3459d9541a1`,
and `57ce0be692cae38644f16e422d2e47f6e79c236818855f12a1b7d4ce1fb74113`.
The first eight games reproduced exactly, including winner and decision count,
between one and four workers (6,676 total decisions). The 64-game wall times
were 41.01 s, 39.98 s, and 19.13 s respectively on Linux
6.8.0-146-generic; these are measurements for those runs, not a general
throughput claim.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --native-root .cache/goat-ai --engine experimental \
  --opponent-checkpoint .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --position-guard \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk examples/decks/warrior_montague_clash.ydk \
  --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/flip_control_goatformat_guide.ydk \
  --both-deck-assignments --reject-training-deck-hashes \
  --require-unseen-main-decks --seed 4000 --seeds 8 --workers 4 \
  --output .cache/goat-ai/position_guard_v2_vs_unguarded_4000_4007.json
```

Repeat with `--seed 4100` and the matching output name for the second
direct schedule. For the tactical comparison, replace
`--opponent-checkpoint ...` with `--opponent tactical`, use `--seed 4200`,
and write to the matching tactical report path. The `--opponent-position-guard`
option allows a same-checkpoint reverse-role ablation.

## Self-play policy-gradient reduction pilot

The previous episodic update summed one policy-gradient loss per learner
decision before clipping the gradient. A new opt-in `mean` reduction divides
each decision loss by that episode's number of learner decisions. The legacy
`sum` behavior remains the default and both modes are recorded in checkpoint
configuration. A unit test confirms that duplicating the same decision leaves
the mean update unchanged under SGD, whereas the sum update doubles it.

Starting from the same feature-v23 Tactical-v6 clone checkpoint
(`1f0b57d517fc7e2475b7d81b072ac0fda47ff1d744ef5855dd767e355586e090`),
both modes trained on seeds 6000–6007 with the same two four-role matchups:
Cas Stomphorst Flip Control versus Daryl Gessler Gravekeepers, and Matt Peddle
Goat Control versus Riclar Chaos Turbo. Each run finished 8/8 duels with
5 wins and 3 losses for the learner, 6,993 total decisions and 1,406
multi-option learner decisions. All 16 saved trajectories replay-verified
and passed the player-visible information audit. This matched result says
nothing about strength; the model weights diverged after their updates.

On unseen Chaos Control, Warrior, Chaos Return, and Flip Control Main Deck
compositions, with both deck assignments and agent seats, the mean child
split **32–32** directly against the sum child over seeds 6300–6307.
Its paired-bootstrap 95% score interval was **45.3%–54.7%**. Against the
unchanged parent on fresh seeds 6400–6407 it scored **33–30–1**; the paired
interval was **50.0%–56.3%**, and the decisive-win Wilson interval was
**40.3%–64.2%**. Assigned-deck parent-match results ranged from 1–15
on Flip Control to 15–1 on Chaos Return. These pilots do not demonstrate
a cross-deck strength gain or satisfy M4's self-play exit criterion.

The ignored checkpoint SHA-256 values are
`f31d4abf8a5b5db72f242bcb47250fd2fe97d2f15b4fdb39c09558bab6740937`
for sum and `664e8553a377e83b95611ed3e51314fe6ed9cd418ee774d8d65afb06843`
for mean. The ignored detailed evaluation reports
`.cache/goat-ai/fv23_selfplay_mean_vs_sum_6300_6307.json` and
`.cache/goat-ai/fv23_selfplay_mean_vs_parent_6400_6407.json` have SHA-256
`9fd6bbee7d40db887b6517767da068ba6e7b6aefe42ea8d013b41486ff0fe7da`
and `4ec1ff926830cd6d384f6a05d38590f9398e6a3dee6b9616ef5e86ea2fc40461`.
The four-worker evaluation wall times were 32.75 s and 33.37 s on Linux
6.8.0-146-generic. All games terminated below the 5,000-decision cap.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v6_four_decks_4800_4813.pt \
  --output .cache/goat-ai/fv23_selfplay_mean_6000_6007.pt \
  --native-root .cache/goat-ai --engine experimental \
  --matchup examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk examples/decks/chaos_turbo_riclar_2020.ydk \
  --schedule-mode four_roles --seed 6000 --games 8 \
  --policy-gradient-reduction mean \
  --record-dir .cache/goat-ai/fv23_selfplay_mean_6000_6007_replays
```

Omit `--policy-gradient-reduction mean` and change the output paths for the
sum control. Replay and visibility checks use `scripts/audit_selfplay_replays.py`
on each recorded directory. The evaluation command follows the preceding
same-checkpoint example, substituting the two child paths, seeds 6300–6307,
and then the parent path with seeds 6400–6407.
## Indianapolis 2005 corpus protocol sweep (2026-10-26)

The evaluator now has a separate `--indianapolis-2005` schedule for the five
legal, fully transcribed Main Decks from the [published 2005 Top 8](https://www.goatformat.com/home/top-8-decklists7022761).
It pairs each unordered deck combination once, then swaps RandomAgent seats
for seeds 5100 and 5101: 10 pairings, 40 duels total. All 40 reached terminal
under 3,000 decisions; the largest used 1,539 decisions. One-worker and
four-worker runs had identical ordered winners and decision counts, 39,057
decisions in total. Five separate full-duel fixtures using these deck files
already pass exact replay and visibility checks in
`tests/test_2005_indianapolis_deck.py`; this wider 40-duel sweep tests
completion and deterministic scheduling, not every replay's full snapshot
equality or every historical card ruling.

On an Intel Core i7-10700K under Linux 6.8.0-146-generic, the one-worker
wall time was 52.761 s (0.758 duels/s, 740.3 decisions/s) and the
four-worker wall time was 13.571 s (2.947 duels/s, 2,877.9 decisions/s).
These are single runs including the tournament worker lifecycle; they do not
measure neural inference or establish a general scaling curve. The ignored
report SHA-256 values are
`f90526a3eb86e4bf4e01b254b456c7588bf7e6500760ea9c8191c89e72c749a9`
for one worker and
`ce54ecca821b08672fbf67115eeebda2a37c72eb16a488102093121ce648c6a9`
for four. Both reports record source-code hash
`1a7314b5b785e4332e57d9621fe0e41865dd37fedb54d02fdb07306a397dd506`
and card-script hash
`f886f54c419d3792fd69888d74190c070992609caad8f5737e3f563bd736b71c`.
The agent-vs-agent win rate is not a playing-strength result because both
agents are RandomAgent and their Deck assignments are fixed by each pairing.

Reproduce after [native setup](native_setup.md):

```bash
for workers in 1 4; do
  OMP_NUM_THREADS=1 .venv/bin/python scripts/evaluate_native.py \
    --engine experimental --indianapolis-2005 \
    --agent-a random --agent-b random --seed 5100 --seeds 2 \
    --workers "$workers" --max-decisions 3000 --native-root .cache/goat-ai \
    --output ".cache/goat-ai/indianapolis_2005_random_5100_5101_${workers}.json" \
    > ".cache/goat-ai/indianapolis_2005_random_5100_5101_${workers}.stdout"
done
```

## Feature-v23 policy on unseen 2005 and later tournament decks

The feature-v23 clone of TacticalHeuristicAgent v6, checkpoint SHA-256
`1f0b57d517fc7e2475b7d81b072ac0fda47ff1d744ef5855dd767e355586e090`,
was evaluated against TacticalHeuristicAgent v7. Three pairings used Jesse
Twohig versus Michael Fukuyama, Jesse versus the sourced Warrior deck, and
Michael versus Chaos Return. All four Main Deck compositions passed the
checkpoint's strict unseen-Main-Deck gate. Seeds 6600–6603, both deck
assignments, and both agent seats produced 48 complete duels per mode under
the 5,000-decision cap. The opponent is a revised version of the policy's
training teacher, so this is a useful baseline rather than an independent
human-strength benchmark.

| Candidate inference | Wins–losses | Score | Paired-bootstrap 95% score interval |
| --- | ---: | ---: | ---: |
| Greedy checkpoint | 16–32 | 33.3% | 20.8%–45.8% |
| Greedy with tactical v3 and weak-Flip guard | 18–30 | 37.5% | 25.0%–50.0% |

The guarded-minus-unguarded score difference on the matched schedule was
**+4.2 percentage points** with a paired-bootstrap 95% interval of
**−8.3 to +16.7 points**. It is not a demonstrated gain. Guarded assigned-deck
scores were 4–4 on Chaos Return, 5–11 on Jesse Goat Control, 6–10 on Michael
Goat Control, and 3–5 on Warrior. The one-run four-worker wall times were
24.84 s unguarded and 19.77 s guarded on Linux 6.8.0-146-generic; inference
mode changes game lengths, so these times do not isolate model speed.

In a separate seed-6600 Jesse-versus-Warrior recording, the unguarded policy
Normal Summoned Magician of Faith in 300 ATK while an opposing Set monster and
Set back row were present. Setting Faith was legal at viewer frame 90. The
408-decision complete duel replay-verified; the replay audit reproduced all
196 policy choices and shortlisted that weak-Flip summon. This is a specific
visible decision candidate for review, not proof that setting would have won
that duel. The ignored report SHA-256 values are
`dc5a655cdcf66e7499602de4a687f2ef0cfe50a2536395ce5614978c243754d9`
and `8c30b65c505447960cb83b99f6c3587a4de4d8a8392787c3383f7632ba92f652`.
The ignored trajectory SHA-256 is
`d6eafe847bd8cfbdc07b205655ceccef5d7079f29b9772b3f1e5654c8579f87a`.

Reproduce by invoking `scripts/evaluate_policy.py` with the checkpoint above,
`--engine experimental --opponent tactical --require-unseen-main-decks`,
`--both-deck-assignments --seed 6600 --seeds 4 --workers 4`, and the three
`--matchup` pairs listed above. Add `--tactical-guard --weak-flip-guard` for
the second mode. The next training step needs independent, reviewed examples
across decks and a held-out result against opponents not used as teachers.

## Current-asset Magician of Faith preference probe (2026-10-26)

The previous feature-v23 checkpoint's 16 demonstration replays no longer
replay-verify under the current native adapter. Their observations and legal
choices still reproduce, but the loaded Book of Moon script hash differs
because the adapter now applies the historical target patch. The verifier
correctly rejects this asset drift. It now names differing asset paths in the
error to make such failures diagnosable. No old replay was relabeled or
silently accepted for training.

Fresh TacticalHeuristicAgent v7 demonstrations on the current assets used
Matt Peddle versus Chaos Turbo (seeds 4800–4803) and Cas Stomphorst versus
Daryl Gessler (seeds 4810–4813), both teacher seats. All 16 full duels were
replay-verified and visibility-audited while training a width-32,
feature-v23 clone for two epochs (seed 27, batch size 16, learning rate
0.001). Its 4,958 teacher decisions produced checkpoint SHA-256
`93ca70795e2c5316ab349a4e5c61ebd553915e49abdbe469d0976d3bebe3d9b2`.
This is a refreshed experimental parent, not the earlier 5,445-decision
checkpoint and not a strength improvement claim.

Against TacticalHeuristicAgent v7 on Jesse Twohig versus Warrior, seed 6600,
the refreshed clone Normal Summoned 300-ATK Magician of Faith into a visible
1800-ATK opposing monster on turn 5, viewer frame 168. Setting the same Faith
was legal. The complete 401-decision duel replay-verified and the preference
file at `examples/preferences/fv23_jesse_warrior_6600_faith_set.preference.json`
binds **Set Faith over Normal Summon Faith** to its SHA-256. This is a
retrospective project review derived from the player's general Faith guidance,
not a claim that the player reviewed this exact frame or that Set wins the
game. The opponent's hidden cards are absent from the policy observation.

A 150-step pairwise update with parent KL weight 1.0 and 64 preservation
states from four current-asset parent demonstrations moved the labeled
Set-minus-Summon score margin from **−0.623** to **+1.567**. The child now
ranks Set first on that *training* state; final sampled preservation KL was
0.00242. Its checkpoint SHA-256 is
`2d627cca1733a758cc570ce6b33f488ab15f9b60cc70178c6257da2570bfbfbf`.

On fresh seeds 6700–6707, Michael Fukuyama versus Chaos Return, both deck
assignments and both seats, the child scored **13–17–2** (43.75%) against its
frozen parent. Both Main Deck compositions were excluded from all parent and
preference training; every duel terminated below the 5,000-decision cap.
The paired-bootstrap 95% score interval was **34.38%–50.00%**. The four-worker
tournament ran 16,634 decisions in 18.02 s (1.78 duels/s on the recorded
machine). A single corrected training choice therefore did **not** establish
better competitive play; the child stays experimental. The ignored report
SHA-256 is
`03fcdabe1d3e6b778350a1d41983bdbc6eb844834f2d9b04c31db17f5ee7766b`.

Reproduce with the pinned native setup, `OMP_NUM_THREADS=1`, and these scripts
in order: `collect_heuristic_demos.py` twice with `--engine experimental
--teacher tactical --opponent combat_heuristic`, the deck pairs and seeds
above, `--seeds 4`; `train_behavioral_clone.py` on all 16 resulting JSON
files with the hyperparameters above; `record_policy_match.py` on Jesse versus
Warrior, seed 6600, policy seat 0, opponent tactical; then
`score_reviewed_preferences.py` and `train_review_preferences.py` with the
tracked preference file and four preservation trajectories (both seats for
seed 4800 and seed 4810), `--steps 150 --preserve-per-trajectory 16
--preserve-batch 16 --parent-kl-weight 1 --learning-rate 0.0001 --seed 28`.
Use `evaluate_policy.py` with `--opponent-checkpoint` set to the refreshed
parent, `--require-unseen-main-decks --both-deck-assignments --seed 6700
--seeds 8 --workers 4` and the Michael/Chaos Return matchup. Generated
replays, checkpoints, and reports remain outside Git.

## Larger current-asset Tactical-v7 clone (2026-10-26)

To test whether the preceding 16-duel parent was limited by imitation data,
the same width-32 feature-v23 architecture, seed 27, two epochs, batch size
16, and learning rate 0.001 were trained from scratch on **64** newly recorded
TacticalHeuristicAgent v7 duels. The four training Main Decks were Matt Peddle
Goat Control, Chaos Turbo, Cas Stomphorst Flip Control, and Daryl Gessler
Gravekeepers. Each of the two matchups used 16 seeds and both teacher seats,
against CombatHeuristicAgent v3. All 64 complete trajectories replay-verified
and passed the visibility audit in the cloning command. They yielded **21,394**
teacher decisions; the two epoch losses were 0.17811 and 0.08716. The ignored
checkpoint SHA-256 is
`9806d1a9b7830d527c81de959236c5143fd5d0d4afc0c06d13159cb6991b6ceb`.
The comparison checkpoint is the 4,958-decision current-asset Tactical-v7
clone above. Its local filename contains `v6` from the older experiment, but
its replay metadata identifies teacher version **7**.

Two independent held-out schedules used Main Deck compositions absent from
both checkpoints, swapped deck assignments and agent seats, and terminated
every duel below 5,000 decisions. On seeds 7000–7003, Jesse Twohig versus
Michael Fukuyama, Jesse versus Warrior, and Michael versus Chaos Return, the
large clone scored **32–16** against the small clone (66.7%; paired-bootstrap
95% interval 56.3%–77.1%). Its assigned-deck scores were 13–3 Jesse, 10–6
Michael, 5–3 Chaos Return, and 4–4 Warrior. On fresh seeds 7200–7203,
Chaos Control versus Bazoo Return, Goat Control versus Flip Control guide,
and Warrior versus Chaos Control, it scored **27–21** (56.3%; interval
43.8%–70.8%). Its assigned-deck scores were 7–9 Chaos Control, 5–3 Bazoo
Return, 1–7 Flip Control, 8–0 Goat Control, and 6–2 Warrior. Pooling the
96 games gives **59–37** (61.5%; paired-bootstrap interval 53.1%–69.8%),
but the uneven deck splits prevent a uniform cross-archetype claim.

On the first 48-game schedule against TacticalHeuristicAgent v7, the large
clone scored **17–31** (35.4%; paired-bootstrap interval 25.0%–45.8%) and
the small clone scored **9–39** (18.8%; interval 10.4%–27.1%). Their matched
score difference was +16.7 percentage points, with a paired-bootstrap
interval of **0.0 to +31.3** points. The larger data set improved this
learned policy relative to the smaller clone, yet the policy still loses
decisively to its tactical teacher; M4's baseline-strength gate remains open.
The four-worker wall times for large-versus-small schedules were 32.30 s and
26.44 s, with 34,830 and 29,070 decisions respectively. The corresponding
large- and small-versus-teacher runs took 21.72 s and 19.50 s. Training wall
time was not recorded, so no training-throughput claim is made. The cloning
command now prints `run_wall_seconds` for future runs, including replay
verification and checkpoint writing; a one-replay timer smoke run completed
99 teacher decisions and reported 1.715 s on this host. That smoke timing is
not the 64-duel training time.

The four ignored report SHA-256 values (first large-versus-small, large-
versus-teacher, small-versus-teacher, second large-versus-small) are
`c5ad10cdfc78a0b9ae2b1a0f060f84c045e7a92d073d5ed523686d7399a460e3`,
`43a72502a8ec655722cb33e09d1981bb437512206d95509ca829ca55e42e251a`,
`77c7191f16bafd15c306c9e5c94fff99537e627a4130d7696626354385ac5431`,
and `7531c5976bc939e421c95968920395aab297853f146a77df3bd979b85af406d8`.

Reproduce with `OMP_NUM_THREADS=1` and the pinned native setup. Run
`scripts/collect_heuristic_demos.py --engine experimental --teacher tactical
--opponent combat_heuristic --seeds 16` twice: Matt/Chaos Turbo at seed 6800
and Cas/Daryl at seed 6830, each with its own output directory. Train all
64 JSON files with `scripts/train_behavioral_clone.py --engine experimental
--feature-version 23 --width 32 --epochs 2 --batch-size 16
--learning-rate 0.001 --seed 27`. Evaluate with `scripts/evaluate_policy.py
--engine experimental --both-deck-assignments --require-unseen-main-decks
--max-decisions 5000 --workers 4`, using the matchups, seeds, and opponent
checkpoint or `--opponent tactical` specified above. Generated data remain
ignored by Git.

## Frozen-parent KL during self-play (2026-10-26)

The self-play trainer now has an opt-in `--parent-kl-weight`. At each sampled
learner decision it adds the KL divergence from the frozen starting policy's
legal-action distribution to the current policy's distribution. Both policies
receive the same player-visible observation and legal actions; the opponent's
hidden state is never an input. The parent is frozen before the first duel,
and weight zero preserves the existing update. This tests policy preservation
under sparse terminal rewards; it is not a search method or a claim of
competitive improvement.

Two children started from the 21,394-decision feature-v23 Tactical-v7 clone
above. Both used the same Matt/Chaos Turbo and Cas/Daryl training matchups,
four-role schedule, seeds 7300–7331, per-learner-deck moving reward baseline,
learning rate 0.0003, learner temperature 1.5, entropy coefficient 0.001,
historical opponent probability 0.75, and snapshot interval eight. The only
change was parent KL weight **0** versus **0.1**. All 32 duels in each run
terminated below 5,000 decisions. The control recorded 23,340 replay-verified
decisions and 3,499 multi-option learner decisions; the KL child recorded
23,006 and 3,479. All 64 complete trajectories also passed the separate
player-visible information audit. Training-pool results were 20–12 and
19–13 respectively, which are not strength estimates because opponent pools
and policies evolve.

On the first unseen-composition schedule (Jesse/Michael, Jesse/Warrior,
Michael/Chaos Return; both deck assignments and seats, seeds 7400–7403),
the KL child scored **28–20** directly against the control (58.3%; paired
bootstrap 95% interval 52.1%–64.6%). On a second, different deck-family
schedule (Chaos Control/Bazoo Return, Goat Control/Flip Control guide,
Warrior/Chaos Control; seeds 7500–7503), it scored **21–27** (43.8%; interval
33.3%–52.1%). The two schedules pooled to **49–47** (51.0%; interval
43.8%–57.3%). In the second schedule it went 2–14 as Chaos Control and
0–8 as Flip Control, so the first direct result did not transfer uniformly.

Against the unchanged frozen starting checkpoint on the first schedule,
**both** children scored **25–23** (52.1%; interval 43.8%–60.4%). Their
matched score difference was zero, with a paired-bootstrap interval of
−8.3 to +8.3 percentage points. This experiment establishes that the KL
penalty changes direct play, but neither a cross-deck advantage nor a
self-play strength gain over the starting policy. Keep the default weight at
zero. The self-play command now prints `run_wall_seconds` for later runs;
these two training runs predated that timer, so no training-throughput figure
is reported. A separate one-duel timer smoke completed 136 multi-option
learner decisions and reported 4.399 s run wall time on this host; it does
not measure the 32-duel runs. The four-worker evaluation wall times were
34.82 s for the first direct match, 33.62 s for KL versus parent, 27.77 s
for control versus parent, and 24.60 s for the second direct match.

The ignored control and KL checkpoint SHA-256 values are
`6dd53eee851c92c980567f203fa8bb243e0b28c14fcbf2a32b8185832643ac02`
and `db6847072b21bfe99c2690b81762d307dbc6d150bd48e65afa5cc8efdc916614`.
The four report hashes in the evaluation order above are
`1f178755fcd6315786b3b0a1e008bdff165b1ce9e716ec08ddf08f34f94aa69d`,
`dd55b92aaebd215bcb4c38eae81fa111c8cd2db029aedfcf2fccf15cbf2d6dec`,
`71e91903a7c1921fda52b090899549ea81b594c65ed615ab01ba7922566449e8`,
and `0e912089262d04f04051a8316a2003f71ef44026d990b39aa84439e7480bc815`.

To reproduce, run `scripts/train_self_play.py` twice from the large clone
checkpoint with the training settings and matchups above, `--seed 7300
--games 32 --record-dir` set to distinct ignored directories, and
`--parent-kl-weight 0` or `0.1`. Verify each saved trajectory with
`verify_trajectory` and `audit_trajectory_visibility`. Evaluate each child
against the other and against the unchanged parent using
`scripts/evaluate_policy.py --engine experimental --both-deck-assignments
--require-unseen-main-decks --workers 4 --max-decisions 5000` and the stated
held-out matchups and seeds.

## Tactical heuristic v8 against v7

After the seed-6803 replay audit, Tactical v8 added player-visible guards for
the Delinquent Duo discard, Thunder Dragon search, Sinister Serpent Normal
Summon, Nobleman activation, Dust Tornado response to Book of Moon, and
Tribe-Infecting Virus activation when every visible Type trade loses value.
These are baseline heuristics, not a trained neural checkpoint.

A direct experimental-adapter tournament on Matt Peddle Goat Control versus
Riclar Chaos Turbo, seeds 7700–7715, both seats and both deck assignments,
gave v8 **38 wins, 25 losses, and 1 draw** against v7 in 64 duels. The recorded
paired-bootstrap score-rate interval was **52.3%–68.8%**. A separate 64-duel
four-matchup schedule using seeds 7700–7703 gave v8 **40–24**; the matchups
were Cas/Daryl, Matt/Chaos Turbo, Jesse/Michael, and Chaos Control/Warrior.
The same four-matchup schedule previously yielded **32–32** for v7 versus v7,
and an earlier v8 version containing only the Tribe guard also scored **32–32**
versus v7. Thus the new bundle changed outcomes, but these samples do not
identify which change helps most or establish broad competitive strength.
Both tournaments used four native worker processes and the pinned local
assets. The reports are under `.cache/goat-ai/tactical_v8_vs_v7_*` and are
ignored by Git.

The Matt/Chaos tournament can be reproduced with:

```bash
.venv/bin/python scripts/evaluate_native.py --engine experimental \
  --matchup examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
            examples/decks/chaos_turbo_riclar_2020.ydk \
  --both-deck-assignments --agent-a tactical --agent-b tactical_v7 \
  --seed 7700 --seeds 16 --workers 4 \
  --output .cache/goat-ai/tactical_v8_vs_v7_matt_chaos_7700_7715.json
```

### Seed-6803 baseline review as an opt-in policy preference experiment

Seven player-reviewed preferences from the verified Matt/Chaos seed-6803
trajectory were scored against the earlier feature-v23 Tactical-v6 clone
(`.cache/goat-ai/fv23_tactical_v6_current_assets.pt`, SHA-256
`93ca70795e2c5316ab349a4e5c61ebd553915e49abdbe469d0976d3bebe3d9b2`).
That parent was trained on seeds 4800–4803 and 4810–4813; neither the exact
replay nor seed 6803 appears in its training provenance. Its greedy action
fell in the preferred set at **0 of 7** reviewed states. This is a diagnostic
of those fixed decisions, not an estimate of whole-duel strength; at some
states its best action was unranked, rather than labeled bad.

An opt-in `baseline_review` input now lets the existing parent-KL preference
trainer use those explicit decisions while recording the reviewed agent and
seat. With 100 updates, learning rate `1e-4`, KL weight 1.0, and 64 sampled
preservation states from four parent-training trajectories, the preference
loss moved from **1.742 to 0.670** and final preservation KL was **0.0188**.
The child greedily chose a preferred action at **3 of 7** source states;
five of seven preferred-minus-disfavored pairwise margins were positive.
The ignored child checkpoint is
`.cache/goat-ai/fv23_seed6803_baseline_review_child.pt` (SHA-256
`d80b38e39aa08dc0d925ea7a504f66774ddb8da25f6c81aa3ebe2342b3ce1129`).

On held-out Jesse/Michael and Chaos Control/Warrior Main Decks, seeds
8200–8207 with both seats and deck assignments, the child scored **15–16–1**
and **18–13–1** directly against its parent: combined **33–29–2** over 64
duels. The outcomes do not establish a competitive improvement. Those reports
were recorded just before a metadata-only change that added reviewed seat and
agent fields to the child checkpoint; all model-state tensors in the reported
and final checkpoint were compared and were exactly equal. The ignored reports
are `.cache/goat-ai/fv23_seed6803_review_child_vs_parent_heldout_0.json` and
`..._1.json`. Neither the reviews nor this small experiment close M4.

Reproduce scoring with `scripts/score_reviewed_preferences.py --checkpoint`
and both `--case` pairs listed in [replay audit](replay_audit.md). Reproduce
training with `scripts/train_review_preferences.py`, the same cases, four
parent-provenance preservation trajectories at seeds 4800 and 4810, and the
settings above. Direct evaluation used `scripts/evaluate_policy.py
--engine experimental --both-deck-assignments --opponent-checkpoint
.cache/goat-ai/fv23_tactical_v6_current_assets.pt --require-unseen-main-decks
--seed 8200 --seeds 8 --workers 4` for each held-out pair.

### Tactical v9 review of both-seat seed 6803

The separate seed-6803 seat-0 replay has both players running Tactical v8.
The player's review identified repeated self-targeted removal, premature
Metamorphosis and Book of Moon, poor Creature Swap and Tsukuyomi targets, and
two Thunder Dragon discards after its remaining copies were already known
outside the Deck. Tactical v9 adds conservative visible-state resource and
target checks. The 879-decision v8 game and a new 445-decision v9-versus-v9
game both replay-verified and reproduced their versioned teacher choices;
see [replay audit](replay_audit.md) for exact decision indices. The historical
GOAT Netrep zero-search option remains legal in the simulator.

In a 64-duel direct v9-versus-v8 tournament with four native workers, seeds
8200–8203, both seats and deck assignments, v9 scored **34 wins, 29 losses,
one draw**. By matchup, Cas/Daryl was 7–9, Matt/Chaos Turbo 10–6,
Jesse/Michael 9–7, and Chaos Control/Warrior 8–7–1. These small samples do
not establish a general strength gain, and all four matchups use the same
experimental GOAT-mode adapter rather than an independently certified full
2005 rules implementation. The ignored, fingerprinted reports are
`.cache/goat-ai/tactical_v9_vs_v8_fourpair_0_8200_8203.json` through
`..._3_8200_8203.json`. Reproduce each pair with
`scripts/evaluate_native.py --engine experimental --both-deck-assignments
--agent-a tactical_v9 --agent-b tactical_v8 --seed 8200 --seeds 4 --workers 4`
and the corresponding two Main Deck paths above.

### Tactical v10 correction and review-data experiment

The v9 seed-6803 replay exposed open Main Phase checks that required a
`pass` action even though the engine offered only phase transitions. This
allowed Chaos Sorcerer to banish itself and Breaker to destroy its own Set
Trap. Tactical v10 makes those checks work without a `pass`, holds an
unmotivated own-turn Book of Moon during its Main Phase or when chaining to
its own Chaos Sorcerer effect, and
reduces position switches with no visible battle gain. Its same-seed Matt
versus Chaos Turbo replay is linked in [replay audit](replay_audit.md).

In a **32-duel** direct v10-versus-v9 tournament on Matt/Chaos Turbo and
Cas/Daryl, seeds 8500–8503, both seats and deck assignments, v10 scored
**18–14**. The paired bootstrap score interval was **0.438–0.719**, so this
small result does not establish a strength improvement. The fingerprinted
report is `.cache/goat-ai/tactical_v10_vs_v9_8500_8503.json`. Reproduce with
`scripts/evaluate_native.py --engine experimental --agent-a tactical
--agent-b tactical_v9 --both-deck-assignments --seed 8500 --seeds 4
--workers 4` and the two deck pairs above. Here `tactical_v9` preserves
the reviewed v9 decisions.

The 14 new seat-specific preferences from the v8 seed-6803 review were
combined with the earlier seven v7 preferences for a **21-comparison**
parent-KL training pilot. The child greedily chose a preferred action at
**16 of 21** reviewed source states. On held-out Jesse/Michael and Chaos
Control/Warrior matchups, seeds 8300–8307, both seats and deck assignments,
it scored **15–17** and **16–15–1** against the unchanged parent, or
**31–32–1** combined. That does not meet the competitive promotion gate.
The ignored child and reports are
`.cache/goat-ai/fv23_seed6803_combined_review21_child.pt` and
`.cache/goat-ai/fv23_seed6803_combined_review21_vs_parent_heldout_{0,1}.json`.

### Tactical v11 and v12 replay corrections

The v10 turn-13 replay review exposed a BLS guard that incorrectly required
an opposing face-up monster, and a missed opportunity to banish a Set
monster before resetting BLS with Tsukuyomi. Tactical v11 separates BLS
from Chaos Sorcerer's face-up-target restriction and prefers the legal BLS
activation before Tsukuyomi when BLS can still change position that turn.
The seeded v11 game follows that line. On a 32-duel direct v11-versus-v10
comparison across Matt/Chaos Turbo and Cas/Daryl, seeds 8600–8603 with both
seats and deck assignments, v11 scored **16–16**. Its report is
`.cache/goat-ai/tactical_v11_vs_v10_8600_8603.json`.

The next replay review found v11 spending Book of Moon on its own Chaos
Sorcerer in the opponent's Draw Phase, then chaining Raigeki Break to its
own Book and discarding a card to destroy a Sheep Token. Tactical v12
defers those early idle activations and prioritizes an opposing non-Token
card if the removal Trap is already committed. On a separate 32-duel direct
v12-versus-v11 comparison with the same two deck pairings, seeds 8700–8703,
both seats and assignments, v12 also scored **16–16**. Its report is
`.cache/goat-ai/tactical_v12_vs_v11_8700_8703.json`. Both versions fix
reviewed decisions, but these small direct comparisons show no competitive
gain. Neither is evidence for M4's trained-policy or self-play gate.

### Distinct whitelist-deck protocol probe

#### Magical Hats Type encoding and Rivalry event correction (27 October 2026)

A new 50-pair sweep of independently generated 40-card GOAT-whitelist decks,
seeds 10224–10273 with distinct opponent seed offset 1,000,000, initially
produced 48 terminal, replay-verified duels. Seed 10247 failed when Magical
Hats placed GOAT Energy Drain (`504700090`, a Trap) in a Monster Zone and an
attack flipped it face-up. Native `QUERY_RACE=0` is expected for a card with
no monster Type; the observation validator had incorrectly rejected it. The
adapter now emits `race=None`, and schema-v24+ trajectories require the
explicit `race` field while allowing its null value. A new regression covers
that exact 915-decision duel, serialization, full native replay, and the
visibility audit. [Historical Rivalry rulings](https://www.goatformat.com/rulings6.html)
explicitly state that the Spell/Trap cards summoned by Magical Hats have no
Type.

After the Magical Hats correction alone, **49/50 duels reached terminal** and
all **51,250 decisions in those 49 duels** replay-verified and passed the legal-choice
visibility audit. Before the Rivalry correction, seed 10227 stopped at
decision 369 when GOAT Rivalry of Warlords (`504700158`) asked its controller
to retain one of two face-up Types. Both legal Type choices reproduced the
native `recursive event trigger detected` error. Removing the pinned script's
explicit `Duel.Readjust()` in a temporary local experiment did not clear it.
Suppressing the active adjust effect during its `Duel.SendtoGrave` call did:
the core had been re-entering
that still-running effect. The retained correction is applied in memory only
after the original GOAT script passes an exact SHA-256 and marker check.
Paired native tests choose either Type, check that the other monster reaches
the Graveyard, and complete, replay-verify, and visibility-audit both duels.
The 49 successes before this correction did not establish arbitrary-deck
correctness. The ignored report is
`.cache/goat-ai/random-probe-distinct-10224-10273-fixed/report.json`
(SHA-256 `393a2d30218fcbcf549691999373527553db1407718089789a7223da3db21507`).
The pre-correction report requires the earlier code revision. Reproduce the
corrected sweep after [native setup](native_setup.md) with:

```bash
PYTHONPATH=src:. python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/random-probe-distinct-10224-10273-rivalry-fixed \
  --seed 10224 --seeds 50 --max-decisions 3000 \
  --distinct-opponents --verify-replays
```

Re-running the same 50 pairs with the guarded script produced **50/50 terminal
duels**, **52,275 replay-verified decisions**, and 50 complete legal-choice
visibility audits. Seed 10227 finished in 1,025 decisions; the other 49
results were unchanged. The ignored report is
`.cache/goat-ai/random-probe-distinct-10224-10273-rivalry-fixed/report.json`
(SHA-256 `4862fb58501560a63177c6b0598ad48c1110c9eef7544e1dd99f7914d6bb4198`).
Its loaded patched Rivalry script digest is
`4de623aa5d43d2ec7bae66b3d4d2db476c6f9efb99a5baca0365025463689702`.
This finite sweep checks protocol completion and replay consistency; it is
not an audit of every historical Rivalry interaction or legal GOAT deck.

`scripts/probe_random_decks.py --seed 10000 --seeds 24 --max-decisions 3000
--distinct-opponents --verify-replays` generated 48 different whitelist-legal
40-card decks and played 24 seeded random-agent duels. Before the adapter
corrections, **19/24** reached terminal: four stopped at card-name expression
prompts and one at an unrevealed opposing-hand choice. The original ignored
report is `.cache/goat-ai/random-probe-distinct-10000/report.json`.

After adding exact expression catalogs and a blind single-hand-card choice,
the same 24 seeds reached **24/24** terminal outcomes with **25,833** total
decisions and a maximum of 1,525 decisions in any game. Every full trajectory
replay-verified. The ignored corrected report is
`.cache/goat-ai/random-probe-distinct-10000-fixed/report.json` (SHA-256
`86576a1cf12a0836956348ee6a48735d1698e96295de1cc1f049654a038fd378`).
This exercises native protocol breadth; randomly assembled decks and random
agents do not establish 2005 ruling correctness or competitive strength.

### Tactical v13 and expanded protocol triage

Six user-reviewed v12 seed-6803 choices are stored as SHA-bound
`baseline_review` preferences and reproduced on the original player-visible
states. Tactical v13 changes those choices. A direct 64-duel v13-versus-v12
evaluation used Matt/Chaos Turbo and Cas/Daryl, both deck assignments and
seats, seeds 8800–8807. V13 scored **34–30**, with a paired bootstrap score
interval of **50.0%–57.8%**. Its assigned-deck split was 6–10 on Chaos Turbo,
7–9 on Cas, 10–6 on Matt, and 11–5 on Daryl. The ignored report is
`.cache/goat-ai/tactical_v13_vs_v12_8800_8807.json` (SHA-256
`57f757e522da00080f80ef3466dd75c480fa368d988a8f8f59d9ef561cc74c44`). This does not establish
a cross-deck strength gain or M4 promotion.

The distinct, full-whitelist random-deck sweep on seeds 10024–10123 reached
terminal in **93/100** duels before further adapter fixes, with every
terminal trajectory replay-verified. Three failures were a pinned GOAT
Firebird Lua callback passing `nil` as the controller during battle. A
SHA-guarded in-memory patch uses the effect handler's player; all three
original seeds (10030, 10062, 10122) now reach terminal and replay-verify
individually. Two more games stopped at undecoded native `MSG_SELECT_SUM`
prompts (10097, 10102), and two at opponent-hand choices lacking an addressed
reveal (10093, 10107). The original reports are under
`.cache/goat-ai/random-probe-distinct-10024-10123/` (report SHA-256
`08933bbbd10661ba48b632750ddc1078f1f4362dd017c14c5ae2955fcf0f350c`) and
`.cache/goat-ai/firebird-fixed-{10030,10062,10122}/`.

The adapter now enumerates bounded exact/exceed sum selections with native
response bytes for Puppet Magic's zero-mandatory-card form. A later parser
extension includes implicit mandatory cards in the sum check and visible
selected-card action while keeping native response indices scoped to optional
cards. Exact and exceed cases pass synthetic protocol tests; a GOAT native duel
with a mandatory sum card has not yet been observed. Large sum-choice sets
now use incremental legal-prefix selection, verified separately below. Double
Spell copying The Inexperienced Spy now offers blind
opposing-hand choices, with card codes and native hand positions redacted.
Dragged Down into the Grave uses its addressed hand reveal through the later
choice window. Focused native tests replay-verify those original four seeds
and check the visible-choice boundary. Re-running the same 100 independently
constructed deck pairs after all corrections yielded **100/100 terminal**,
**100/100 full-replay verified**, **113,037 verified decisions**, and a
maximum of **1,698** decisions. The ignored report is
`.cache/goat-ai/random-probe-distinct-10024-10123-fixed/report.json`
(SHA-256 `5b87f6c17c7c99058ce5fd3f12ed609267f8beec88f4f3a984ac373e88d6b075`).
This establishes protocol coverage for this finite random sweep, not
historical correctness or general protocol completeness.

### Tactical v14: preserving Raigeki Break and valuing Snatch targets

In the replay-verified v13 seed-6803 game, player 2 chained Raigeki Break to
the opponent's resolving Metamorphosis at decision 83, discarded Mystic
Tomato instead of an expendable Thunder Dragon at 84, and later selected a
Sheep Token for Snatch Steal over the opposing Breaker at 324. The three
player-reviewed alternatives are bound to the source replay SHA-256 in
`examples/preferences/tactical_v13_seed6803_player2_resource.preference.json`.
On those same visible states, v14 passes on the Raigeki chain, chooses Thunder
Dragon, and targets Breaker. Its Raigeki guard holds the card when the only
chain prompt is an unrelated resolving Normal Spell/Trap; a visible threat to
its own Set card or an incoming attack remains a valid response window.
Snatch is held when only opposing Sheep Tokens are available unless the
player has Metamorphosis in hand. These are tactical preferences, not rules
or hidden-information access.

Both v13 and both fresh v14 seed-6803 complete trajectories replay-verified,
passed the visibility audit, and reproduced their versioned teacher actions.
The v14 seat-0 viewer is `replays/tactical_v14_self_seed6803.html` (871
decisions); its seat-1 trajectory contains 953 decisions. A direct 64-duel
v14-versus-v13 tournament on Matt/Chaos and Cas/Daryl with both seats and
deck assignments, seeds 8900–8907, scored **34–30**. The paired-bootstrap 95%
score interval was **50.0%–57.8%**; the assigned Flip Control split was 5–11.
The ignored report is `.cache/goat-ai/tactical_v14_vs_v13_8900_8907.json`
(SHA-256 `f29ed64c7dd264d8127a0f2311f0eb14c302008abb42dfc79a5beb9e4a42dde2`).
This does not demonstrate a cross-deck strength gain or satisfy the M4 gate.

### Three-review neural update and a multi-card selection loop

The three v13 seed-6803 reviewed choices were replay-verified and visibility-
audited before scoring the feature-v23 Tactical-v6 policy trained on seeds
4800–4803 and 4810–4813. Neither the review replay nor its seed appears in
that parent's training provenance. At decisions 83, 84, and 324, the parent's
preferred-minus-disfavored log-mean-exp margins were **−2.608, −3.530,
+0.737**. A 100-step opt-in preference update with learning rate `1e-4`,
parent-KL weight 1.0, and 64 sampled preservation decisions from four
parent-provenance trajectories moved those margins to **+1.513, +0.328,
+2.658**. Its initial/final preference losses were 2.210/0.275 and final
preservation KL was 0.0100. The preferred action became greedy at only **one
of three** frames: the other two had an unreviewed action ranked above both
compared actions. This is a measured pairwise improvement, not a claim that
the full decision is now correct. The ignored child is
`.cache/goat-ai/fv23_v13_review3_child.pt` (SHA-256
`ffb1682c374b272dd5d2d1ebd9af984436fb33b76d5931303258107816a57ece`).

An initial held-out tournament on four unseen Main Deck compositions,
seeds 9000–9007, scored 36–28 against the unchanged parent. A second
different-deck schedule initially exceeded both 5,000 and 10,000 decisions
on Bazoo Return versus Flip Control, seed 9011, candidate in seat 1. Direct
reproduction found a native `MSG_SELECT_UNSELECT_CARD` prompt on turn 9 at
which the parent alternated between selecting and unselecting two cards for
over 9,700 decisions. The policy already preferred `finish_selection` over
unselecting when offered, but its one-card repeat check did not catch a
two-card cycle. Inference version 6 adds a legal card whenever the selection
is unfinished and at least one add action is available. The exact four-game
seed-9011 pairing then terminated in 330–699 decisions. This is a progress
rule for policy inference, not a simulator ruling or evidence of stronger play.

Both schedules were rerun with inference version 6, 64 duels each, with
both deck assignments, both agent seats, held-out seeds, and Main Deck
composition rejection. The first scored **36–28** with a paired-bootstrap
95% score interval of **50.0%–62.5%**. The second scored **32–31–1** with an
interval of **42.2%–60.2%**. Combined across the 128 duels, the child scored
**68–59–1** with a paired matchup/seed bootstrap interval of **48.0%–59.4%**.
The assigned-deck results varied sharply, including 1–15 on Chaos Control
in the first schedule and 1–15 on Flip Control in the second. The ignored
reports are `.cache/goat-ai/fv23_v13_review3_vs_parent_9000_9007_fixed.json`
(SHA-256 `c1be00ca3d8b5232dbeb9c76196b397664344796671ec8ac3a7170ca43d80bc5`)
and `.cache/goat-ai/fv23_v13_review3_vs_parent_9010_9017_fixed.json`
(SHA-256 `c55a7e114bf0c66e8739604cf4b24e69ed3d78ce1de857be6d556a7a04a5e071`).
The interval includes 50%, so this child is not promoted and M4 remains
open. The turn-9 selection loop illustrates why full-duel evaluation is
necessary even when fixed-state preference scores improve.

### Second distinct-whitelist native protocol sweep

Another 100 independently generated whitelist deck pairs, seeds
10124–10223, ran with RandomAgent through the experimental native adapter
and a 3,000-decision limit. **100/100** reached terminal; all **103,185**
decisions replay-verified, with a maximum of **1,663** decisions in one duel.
There were no recorded adapter errors. The ignored report is
`.cache/goat-ai/random-probe-distinct-10124-10223/report.json` (SHA-256
`c087a1ade37f65df7f8877fee33598d5eb4a02422a3eb5ac890c378016b8bd31`).
The deck generator chose 40 distinct canonical Main Deck cards for each
player, so this expands protocol breadth but does not sample realistic
deck construction, prove every native prompt is supported, or validate
historical rulings. The sweep process loaded the initial mandatory-sum
decoder; the later wire-length bound change was checked by focused parser
and Puppet Magic native tests, not by repeating this full sweep.

A further 20 distinct whitelist deck pairs, seeds 20000–20019, ran against
the current adapter with RandomAgent and a 5,000-decision cap. All **20/20**
reached terminal and all **19,968** decisions replay-verified; the longest
duel had **1,481** decisions. There were no recorded adapter errors. The
ignored report is
`.cache/goat-ai/random_whitelist_20000_20019_distinct/report.json`
(SHA-256 `89148d79451862cdd771e134caa4b89ed0ff6dc7820a5060b08fdda2f1826b67`).
This adds protocol coverage after the sum-choice decoder changes. It does
not validate the historical rulings of those randomly selected cards.

### Fresh distinct-deck protocol sweeps (27 October 2026)

With the current pinned native assets, a third 50-pair sweep drew two
independent whitelist-legal 40-card Main Decks per seed, 10274–10323. All
**50/50** games reached terminal under 3,000 decisions, with **54,273**
decisions fully replay-verified and visibility-audited; the longest game
took 1,616 decisions. The process loaded 1,213 distinct native assets and
recorded 4,146 source-card/action-kind pairs. The ignored report is
`.cache/goat-ai/whitelist_distinct_10274_10323/report.json` (SHA-256
`a7f8fdcb0c6738db66f65f8087838becd47c530bcb0ec78d9e320690ad4000f1`).
A separate repeat of seeds 10274–10275 matched their original deck hashes,
opponent hashes, winners, decision counts, action-kind sets, replay-verified
counts, and pinned asset hashes.

A separate 50-pair sweep drew legal 40-card Main Decks from copies in six
sourced tournament lists, again with independently generated opponents,
seeds 30000–30049. All **50/50** games reached terminal, and **46,227**
decisions fully replay-verified and visibility-audited; the longest took
1,440 decisions. This run observed 200 opponent-hand choices and 596
hidden-field choices in the visibility audit, and 86 distinct selected
chain-response/source pairs. Its ignored report is
`.cache/goat-ai/tournament_mix_distinct_30000_30049/report.json` (SHA-256
`c394a381ec6fb6fedde03a9b7e8d764a3a0ea469e1af6c51ee849c7cb3c8fbf4`).
These are random-agent protocol and information-boundary checks, not
historical ruling audits or claims about competitive deck construction.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai --output .cache/goat-ai/whitelist_distinct_10274_10323 \
  --seed 10274 --seeds 50 --max-decisions 3000 \
  --verify-replays --distinct-opponents --count-card-actions
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai --output .cache/goat-ai/tournament_mix_distinct_30000_30049 \
  --seed 30000 --seeds 50 --max-decisions 3000 --card-pool tournament \
  --verify-replays --distinct-opponents --count-card-actions
```

### Further independent whitelist probe (27 October 2026)

Fresh seeds 10324–10355 used independently generated legal 40-card decks
against distinct opponents, RandomAgent decisions, a 3,000-decision cap,
full native replay verification, the player-visible trajectory audit, and
source-card action counts. All **32/32** games reached terminal; all
**33,664** decisions replay-verified and passed the visibility audit. The
longest duel took 1,607 decisions. The run loaded 1,037 distinct native
assets, including 10 assets absent from the earlier 10148–10247 sweep, and
observed 3,167 source-card/action-kind pairs. There were no protocol errors.
This measures coverage of the sampled native paths, not historical ruling
correctness or agent strength.

The ignored report is
`.cache/goat-ai/whitelist_distinct_10324_10355/report.json` (SHA-256
`555399d95530dcfcb5060b6d0cdfb36b7deadffd52ce6f9c6acfee20ed5ae816`).
Reproduce with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/whitelist_distinct_10324_10355 \
  --seed 10324 --seeds 32 --max-decisions 3000 \
  --verify-replays --distinct-opponents --count-card-actions
```

### Incremental native sum choices

`MSG_SELECT_SUM` previously failed explicitly when the number of possible
subsets exceeded 4,096, even if few subsets met the required Level total.
The adapter now presents one optional card at a time, filtering out prefixes
that cannot complete legally. It offers a finish action only for a complete
native-valid subset. Mandatory cards appear in the selected-card action but
are not included in the native response indices. Exact and greater-sum
feasibility use the pinned core's `playerop.cpp` acceptance conditions.
A synthetic 32-card exact-sum prompt, whose raw subsets far exceed 4,096,
is decoded without flattening its choices. Synthetic greater-sum and
mandatory-card tests cover the other parsed forms; those do not substitute
for a real GOAT duel using them.

On random-deck seed 10097, forcing incremental selection for The Puppet
Magic of Dark Ruler and choosing the same card as the flat response produced
identical next observations and legal actions. Both resulting complete duels
replay-verified and passed the player-visible trajectory audit. This validates
the staged response and privacy boundary for that exact GOAT card prompt;
other sum cards and very large worst-case search spaces remain unaudited.

### Tactical-v14 imitation continuation on four new training decks

Sixteen native Tactical-v14-versus-Combat-v3 demonstrations used both seats on
Jesse Twohig GOAT Control versus Montague Warrior (seeds 9100–9103) and
Dingosig Chaos Return versus GOAT Guide Flip Control (9110–9113). All games
reached terminal, replay-verified, and passed the player-visible audit before
training. The Tactical teacher won 14/16 and supplied 3,786 decisions. Starting
from the feature-v23 Tactical-v7 64-game clone, a two-epoch width-32
continuation with seed 31, minibatch 16, and learning rate 0.0003 reduced
training loss from 0.221115 to 0.155757 in 42.08 seconds. The ignored child is
`.cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt` (SHA-256
`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`).
The unchanged parent SHA-256 is
`9806d1a9b7830d527c81de959236c5143fd5d0d4afc0c06d13159cb6991b6ceb`.

After [native setup](native_setup.md), reproduce the ignored inputs and child:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher tactical --opponent combat_heuristic \
  --deck-a examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
  --deck-b examples/decks/warrior_montague_clash.ydk \
  --seed 9100 --seeds 4 --output-dir .cache/goat-ai/tactical_v14_jesse_warrior_9100_9103
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher tactical --opponent combat_heuristic \
  --deck-a examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --deck-b examples/decks/flip_control_goatformat_guide.ydk \
  --seed 9110 --seeds 4 --output-dir .cache/goat-ai/tactical_v14_return_flip_9110_9113
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/train_behavioral_clone.py \
  .cache/goat-ai/tactical_v14_jesse_warrior_9100_9103/seed_*.json \
  .cache/goat-ai/tactical_v14_return_flip_9110_9113/seed_*.json \
  --engine experimental --feature-version 23 --width 32 --epochs 2 \
  --batch-size 16 --learning-rate 0.0003 --seed 31 \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v7_64games_6800_6845.pt \
  --output .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt
```

The child and unchanged parent played two independent held-out schedules,
each using unseen Main Deck compositions, both deck assignments, and both
agent seats. Chaos Control/Bazoo Return and Lolmarcus/Michael GOAT Control,
seeds 9300–9307, scored **39–23–2** for the child over 64 duels, with a
paired-bootstrap 95% score interval of **52.3%–72.7%**. Dimension Fusion Turbo
against Bazoo Return and Chaos Control, seeds 9400–9407, scored **40–24**
over 64 duels, interval **50.0%–75.0%**. Combined, the child scored
**79–47–2**, or 62.5%, with a matchup/seed paired interval of
**53.9%–70.7%**. Assigned-deck results still ranged from 8–7–1 to 22–10;
this is evidence of improvement over this parent across the measured schedules,
not a general playing-strength claim. The ignored reports are
`.cache/goat-ai/fv23_tactical_v14_continuation_vs_parent_9300_9307.json`
(SHA-256 `97b4f3123b7b2e99f8ccfb192625ea3db0a1c9a974911b070c4f235a318a8d6d`)
and `.cache/goat-ai/fv23_tactical_v14_continuation_vs_parent_9400_9407.json`
(SHA-256 `dbfe70d45931228416bb020f951efb28d5e562a71b488f7436fd6944c2d9eba4`).

Against Tactical-v14 itself on the first deck pairings with fresh seeds
9500–9507, the child scored only **12–52** over 64 duels, paired interval
**12.5%–25.0%**. The ignored report is
`.cache/goat-ai/fv23_tactical_v14_continuation_vs_teacher_9500_9507.json`
(SHA-256 `24c06cc748801e0fd2a6de19e0f96261714a93a14a09982ef505508d10cc3dc2`).
All three tournaments used the experimental native adapter, four workers,
and inference version 6, without optional tactical guards on the neural
policy. The two parent comparisons took 45.29 and 33.48 seconds; the teacher
comparison took 29.81 seconds. Synthetic teacher quality, small deck coverage,
and unaudited historical card interactions limit the result. The child is a
stronger *neural* checkpoint than this parent under the measured schedules,
but Tactical-v14 remains far stronger and M4's competitive and self-play gates
remain open.

### Snapshot-pool continuation from the stronger neural clone

The neural child above was the frozen parent for 32 native self-play duels on
the four demonstration Main Decks, seeds 9600–9631, with each deck in both
seats (`four_roles`). The learner sampled at temperature 1.5 against 75%
historical snapshots and 25% RandomAgent, with learning rate 0.0003,
entropy coefficient 0.001, per-learner-deck return baseline, frozen-parent
KL weight 0.1, and snapshots every eight games. All **32/32** duels reached
terminal below 5,000 decisions; all **17,103** saved decisions replay-verified
and passed the visibility audit. Training produced 2,941 multi-option learner
decisions, 18 training wins and 14 losses, in 74.15 seconds. These outcomes
reflect a changing training pool, not held-out strength. The ignored child is
`.cache/goat-ai/fv23_tactical_v14_selfplay_9600_9631.pt` (SHA-256
`e51909a2fa2b4e1ecf0dbe5e5edf184d0a9fe88284594f533f9675f866ba368f`).

Two fresh held-out comparisons used both deck assignments and seats, with
Main Deck composition overlap rejected for both checkpoints. On Chaos
Control/Bazoo Return and Lolmarcus/Michael GOAT Control, seeds 9700–9707,
the RL child scored **33–31** directly against its unchanged parent; the
paired-bootstrap score interval was **40.6%–60.9%**. On Dimension Fusion
Turbo against Bazoo Return and Chaos Control, seeds 9800–9807, it again
scored **33–31**, interval **40.6%–60.9%**. Combined: **66–62** over 128 duels,
interval **43.8%–59.4%**. The ignored reports are
`.cache/goat-ai/fv23_tactical_v14_selfplay_vs_parent_9700_9707.json`
(SHA-256 `be9843139cbdb3da7c055d34352fcb78a341447d000d7ccc48d30b5b2ac242f5`)
and `.cache/goat-ai/fv23_tactical_v14_selfplay_vs_parent_9800_9807.json`
(SHA-256 `3d165f6d5801506a184614d94077df12ca8e16eb0d9ea925c863f45d7a490a22`).
The tournaments took 49.97 and 34.54 seconds with four workers. No
cross-deck self-play strength gain is established; keep the RL child
experimental and the imitation parent as the current neural reference.

### Policy-visited synthetic teacher labels

The opt-in cloning path now labels decisions from checkpoint-attributed
`policy_evaluation` trajectories with Tactical-v14, after exact native replay
verification and the player-visible audit. It uses only the recorded policy
seat's multi-option decisions and rejects a source checkpoint hash mismatch.
These are synthetic labels on policy-visited states, not executed teacher
actions or human demonstrations. Eight native duels of the feature-v23
imitation parent against Tactical-v14 used Jesse/Warrior and Return/Flip,
seeds 9900–9901, with the policy in both seats. They all reached terminal
and yielded **626** policy decisions with multiple choices. The teacher
disagreed with the executed choice on **69**. A two-epoch continuation
(width 32, batch 16, learning rate 0.0001, seed 37) reduced training loss
from 0.317407 to 0.289099 in 12.31 seconds. Its ignored checkpoint is
`.cache/goat-ai/fv23_on_policy_teacher_9900_9901.pt` (SHA-256
`cefc79d3e8944dd4d0285ef6a659d0105565b88a526dda97bc82bfc70f164d8a`).

On unseen Main Deck compositions, both deck assignments and seats, seeds
10100–10107, the child scored **28–35–1** directly against the unchanged
parent over 64 duels. The paired-bootstrap 95% score interval was
**35.2%–53.1%**; the child scored 6–10 when assigned Michael GOAT Control.
The ignored report is
`.cache/goat-ai/fv23_on_policy_teacher_vs_parent_10100_10107.json`
(SHA-256 `71b5975e6d8cc7bea59c860037eb45c4fb6a908fdf0830c4d50cdf6dca9e877e`).
The four-worker tournament took 49.41 seconds. Keep this child experimental;
the policy-visited labeling path is valid, but this small teacher correction
set did not establish a playing-strength gain.

Reproduce a source duel, then label saved duels with the matching parent:

```bash
PYTHONPATH=src:. python scripts/record_policy_match.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --deck1 examples/decks/chaos_return_dingosig_worlds_2022.ydk \
  --deck2 examples/decks/flip_control_goatformat_guide.ydk \
  --seed 9901 --policy-seat 0 --opponent tactical --max-decisions 5000 \
  --output .cache/goat-ai/on_policy_teacher_9900_9901/return_flip_9901_seat0.json
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/train_behavioral_clone.py \
  .cache/goat-ai/on_policy_teacher_9900_9901/*.json \
  --engine experimental --on-policy-teacher tactical_v14 \
  --feature-version 23 --width 32 --epochs 2 --batch-size 16 \
  --learning-rate 0.0001 --seed 37 \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/fv23_on_policy_teacher_9900_9901.pt
```

### Expanded policy-visited synthetic teacher pilot

The deterministic batch collector recorded 64 native feature-v23 policy
versus Tactical-v14 duels on Jesse Goat Control/Warrior and DingoSig Chaos
Return/Flip Control, seeds 12100–12115 and both policy seats. All 27,983
decisions replay-verified and passed the player-visible audit. The policy
won 18, lost 43, and drew three of those collection games; those are
collection outcomes, not a strength evaluation. Tactical-v14 labeled
4,679 multi-option policy-seat decisions and disagreed with the policy's
executed choice on 1,025. These remain **synthetic** labels; no human
demonstrations were added. The ignored collection manifest is
`.cache/goat-ai/policy_vs_tactical_12100_12115/manifest.json` (SHA-256
`fc3f00ff437a1e6dd141fd926196bbeac968e70132175988eafdb1d037cb1df2`).

Two continuations from the same unchanged v23 parent used all 64 verified
trajectories, two epochs, batched forward with minibatch size 16, learning
rate 0.0001, and seed 37. The plain fit took 32.51 seconds including 14.03
seconds of replay verification. An opt-in
`--on-policy-disagreement-weight 4` fit sampled policy/teacher disagreements
at four times the weight of agreements; it took 31.91 seconds including
13.93 seconds of verification. This changes sampling frequency, not the
number of distinct labels. The checkpoint records the weight and correction
count. The ignored checkpoints are
`.cache/goat-ai/fv23_on_policy_teacher_12100_12115_plain.pt` (SHA-256
`7ed7a90f3fc4dc8ac5d6ba3f9a5183ac01845fd479e5d35ca9e0bb7c6eb176e6`)
and `.cache/goat-ai/fv23_on_policy_teacher_12100_12115_disagreement4.pt`
(SHA-256 `8221c5f72dddfd43bb727e254cdc486c0341a8a84ae331976aa91643d780d99f`).

Evaluation excluded the training seeds and Main Deck compositions and used
both deck assignments and both policy seats. On Insids Chaos Control/Bazoo
Return and Lolmarcus/Michael GOAT Control, seeds 12200–12215, the weighted
child scored **62–66** directly against its parent over 128 games (paired
95% score interval 41.4%–55.5%). Against Tactical it scored **27–101**;
the parent scored **15–112 with one draw** on the same schedule. The paired
Tactical score difference was **+9.0 percentage points** (95% interval
+2.3 to +16.0 points). On the first 64 games, the plain child scored
**31–33** against its parent and **12–52** against Tactical; the weighted
child scored **29–35** directly against the plain child. The weighted
child's direct parent comparison on those 64 games was **28–36**. The
Tactical gain on these two pairings did not establish a direct parent gain.

An additional unseen Main Deck family, guide Dimension Fusion Turbo versus
Bazoo Return and Insids Chaos Control, was evaluated on seeds 12216–12223
with the same assignment and seat controls. The weighted child scored
**8–55 with one draw** against Tactical versus the parent's **14–49 with
one draw**. The paired score difference was **−9.4 points** (95% interval
−17.2 to −0.8). The plain child also scored **8–55 with one draw** against
Tactical. Both children split **31–31 with two draws** directly against the
parent on that schedule. The new family contradicts a general Tactical
strength gain. Neither child is promoted; M4 remains open.

With the pinned native assets and parent checkpoint present, reproduce the
weighted training path with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk examples/decks/warrior_montague_clash.ydk \
  --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/flip_control_goatformat_guide.ydk \
  --opponent tactical --seed 12100 --seeds 16 --workers 4 \
  --max-decisions 3000 \
  --output-dir .cache/goat-ai/policy_vs_tactical_12100_12115
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/train_behavioral_clone.py \
  .cache/goat-ai/policy_vs_tactical_12100_12115/matchup*.json \
  --engine experimental --on-policy-teacher tactical_v14 \
  --on-policy-disagreement-weight 4 --feature-version 23 --width 32 \
  --epochs 2 --batch-size 16 --batched-forward \
  --verification-workers 4 --learning-rate 0.0001 --seed 37 \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/fv23_on_policy_teacher_12100_12115_disagreement4.pt
```

The ignored reports for the first two pairings are:

| Comparison and seeds | Report SHA-256 |
| --- | --- |
| Plain/parent 12200–12207: `fv23_on_policy_teacher_plain_vs_parent_12200_12207.json` | `0dd01bd1a86bb08a1f1c1a0f9cf1fd5043668e23c54c9e9a4fb42a2a5fad84a3` |
| Plain/Tactical 12200–12207: `fv23_on_policy_teacher_plain_vs_tactical_12200_12207.json` | `45b32764b51b74683abb4acacd0296eb1c511207b8c31287420392efe41fb9cb` |
| Weighted/plain 12200–12207: `fv23_on_policy_disagreement4_vs_plain_12200_12207.json` | `c760b3b9888cfb45930ba1a2a35d63be87132e82bac2c483b3b545871974af63` |
| Weighted/parent 12200–12207: `fv23_on_policy_disagreement4_vs_parent_12200_12207.json` | `f41b2d8f79d7f166cce6ed6771f8e66efbebf63c30870c0dca6797dd0c454c5b` |
| Weighted/parent 12208–12215: `fv23_on_policy_disagreement4_vs_parent_12208_12215.json` | `823fb292739a03394ef7363b6135dda99fe168275de12a8d3b131d6bcd1f8eef` |
| Weighted/Tactical 12200–12207: `fv23_on_policy_disagreement4_vs_tactical_12200_12207.json` | `eb8964456a5933504074cd617a9c77a9804dce51e04c516b9db5d07f37c2ea96` |
| Weighted/Tactical 12208–12215: `fv23_on_policy_disagreement4_vs_tactical_12208_12215.json` | `f3a21bf43eeef6618fa2503bffed14d70d649e1bdeb2fd45c32261e33a6ab778` |
| Parent/Tactical 12200–12207: `fv23_parent_vs_tactical_12200_12207.json` | `111015da4c15ec50c3b6003b5cf48ca5344865dfcf3b6d702e320581f0edc0d1` |
| Parent/Tactical 12208–12215: `fv23_parent_vs_tactical_12208_12215.json` | `bacb65fa6a76c3db78d0ad233340fd2ee0085ecae8ca9436bbda7754b19f249c` |

For the Dimension Fusion schedule, the reports are
`.cache/goat-ai/fv23_on_policy_disagreement4_vs_tactical_dimension_12216_12223.json`
(SHA-256 `6ce34394eb0d2abcfdded1f807b812a1fed42e7ffbfad81f1af7f39930cb7ce5`),
`.cache/goat-ai/fv23_parent_vs_tactical_dimension_12216_12223.json`
(SHA-256 `3e709370e68b480783a01036eaa1820c9e215344cf0b6bd58aa14769f05653a8`),
`.cache/goat-ai/fv23_on_policy_plain_vs_tactical_dimension_12216_12223.json`
(SHA-256 `8c29a71940837907fae414b1dbffc5d9e382f744b467e60a148d85314bd63937`),
`.cache/goat-ai/fv23_on_policy_disagreement4_vs_parent_dimension_12216_12223.json`
(SHA-256 `c31c4df4a61782d824b4ea0b6effda5b68a5db3ba23f559afa54d8d4cc81ce28`),
and `.cache/goat-ai/fv23_on_policy_plain_vs_parent_dimension_12216_12223.json`
(SHA-256 `e1e37ed71f26551225b930d7ec8e016c86a3b8be5a60379efb83d56d217737ea`).
All full reports and checkpoints are ignored by Git; their hashes bind the
measured claims to the local artifacts.

### Spirit Reaper Set preference and Balter/Serpent correction

An opt-in Tactical-v14 variant prefers Setting GOAT Spirit Reaper if it has
no available direct attack or visible monster it can beat, while retaining
the baseline's other tactical guards. It changes the exact seed-6803 turn-19
reviewed decision from Attack Position Normal Summon to Set. It is a
strategic preference, not a change to the engine's legal actions.

An initial tournament result of 30–65–1 is invalid as a Reaper ablation:
the first candidate factory accidentally disabled older v9–v13 guards. A
configuration regression test now compares every guard flag with v14. The
corrected factory's first attempt hit the 5,000-decision cap in seed 10302.
Reproduction traced that cap to an independent native issue: Dark Balter
battle-destroyed Sinister Serpent, whose negated return was repeatedly
offered in one Standby Phase. The pinned Serpent script now receives a
SHA-guarded in-memory historical correction. The exact duel terminates and
replay-verifies; see [GOAT rules](goat_rules.md).

After both corrections, a fresh complete run of the original predeclared
schedule compared the Reaper variant with unchanged Tactical v14 on Matt
Peddle/Michael Fukuyama/Chaos Control pairings, both deck assignments and
seats, seeds 10300–10307. The variant scored **52–44** over **96/96 terminal
duels**; the paired-bootstrap 95% score interval was **50.0%–59.4%**.
Assigned-deck results were Matt 22–10, Michael 15–17, and Chaos Control
15–17. The four-worker tournament took **26.99 seconds** and averaged
**787.06 decisions** per duel. The ignored report is
`.cache/goat-ai/reaper_set_vs_v14_10300_10307_balter_fixed.json` (SHA-256
`4d40d441b6e6184cc72cd37aa636e32b2174010ae5b6f0f58c4c4c543ae1e210`).
The interval touches 50% and deck splits vary, so the new preference stays
opt-in pending a separate deck-family comparison. This result says nothing
about neural-policy strength.

### Reviewed Nobleman and Heavy Storm card trades

The policy-versus-Tactical Return/Flip seed-9901 replay has two reviewed
resource losses: viewer frame 11 activates Nobleman when the only Set monster
is its own Gravekeeper's Spy, and frame 26 activates Set Heavy Storm into two
other friendly back-row cards and no opposing back row. The replay SHA-256 is
`a8158006692a3f7e68aaff18a5c910cc1bb1344ebebf6aec50f90f398f4df3a6`.
The replay audit reproduces the greedy checkpoint's choices and flags both
frames. A retrospective preference file binds the user's rejection of those
actions to that exact replay (SHA-256
`06bba1e47188ac61ab4141b1b8d6cc1babaa3c363e1211882973d653b5a673a7`).
Its choice of an alternative Set or End Phase is an engineering inference
from the user's feedback, not an additional human demonstration.

The unchanged Tactical-v14 synthetic teacher chose Heavy Storm in **27/56**
policy-visited states where the visible opponent back row could not repay the
Storm plus friendly collateral. An opt-in teacher variant excludes the Storm
itself from collateral when Set, then defers activations with a negative
before-chain card count. It chose **0/56** in those exact states. On a separate
96-duel, three-pairing schedule with both deck assignments and seats, seeds
10700–10707, it scored **47–49** versus Tactical v14 (paired-bootstrap 95%
score interval **44.8%–52.1%**, 22.84-second four-worker run). The ignored
report is `.cache/goat-ai/card_advantage_vs_v14_10700_10707_sourcefixed.json`
(SHA-256 `9143ee22fb7e7b60b7f893555dfd7c0e035aaf671a72455a6d136676e7a51b3d`).
This heuristic corrects the reviewed visible trade without showing a broad
match advantage; it remains opt-in. An earlier report without Set-Storm
source subtraction is invalid for this comparison.

Thirty-two greedy parent-policy versus Tactical-v14 duels on Jesse/Warrior
and Return/Flip, seeds 10400–10407 and both policy seats, yielded **13,995**
replay-verified decisions. Full-policy Tactical-v14 relabeling supplied
**2,474** multi-option labels, including **726** disagreements. Its feature-v23
child scored **27–37** against the unchanged parent on unseen Main Decks,
seeds 10600–10607, and still chose both reviewed losses. The report is
`.cache/goat-ai/fv23_on_policy_teacher_10400_10407_vs_parent_10600_10607.json`
(SHA-256 `35f17c08626846111615d87711341fa0aafdfd56ea45dea7191488602ceefd84`).
The child checkpoint SHA-256 is
`aa617d3129f417d07fead788147449c6d567388123b1688cd818074e21caf166`.
The weak original teacher and large number of routine labels limit this
result.

Feature v24 adds a before-chain visible card-trade estimate to Heavy Storm
and Nobleman action features, with an explicit zero-extended warm start from
feature v23. A corrected-teacher continuation on all 2,474 labels, with the
two cards weighted tenfold at their opportunities, still chose both bad
actions in the reviewed replay. It scored **32–32** against the original
parent on 64 unseen-deck games, seeds 10800–10807 (paired interval
**39.1%–62.5%**; report SHA-256
`a41d1a2c9f710dfb2b49974e79350228a425f02cdf09b70af1b31c3975900523`.
A two-preference parent-KL update did fix both marked
frames, but generalized by largely suppressing useful activations: on a
separate 16-replay decision set it chose Nobleman for an opposing Set monster
in only **5/19** opportunities and Heavy Storm for an even-or-better visible
trade in only **1/53**. It scored **31–33** versus its unchanged v24 parent on
64 fresh games, seeds 10900–10907 (paired interval **35.9%–60.9%**). These
children are not promoted; the latter report SHA-256 is
`cab17456a260200946d5bb7c247934eeb14add1d06056b0c57c1325be2c4f7f1`.

The next controlled training run kept only **149** activation opportunities
from the same 32 verified source duels, including **100** disagreements with
the corrected teacher. A feature-v24 full-network fit still chose Heavy
Storm in **9/16** negative trades on the separate decision set after a
30-epoch stronger fit. Feature v25 instead adds a zero-initialized two-weight
trade scorer and trains only that head from the same original v23 parent.
Its learned weights were **2.057** on visible net card margin and **2.486**
on the resource-activation flag; all other parent weights stayed frozen.
Training took **35.08 seconds**. This checkpoint changes both seed-9901
reviewed choices: it Sets Solemn Judgment rather than using Nobleman on Spy,
then ends the turn instead of using Heavy Storm into its own back row. The
ignored checkpoint is `.cache/goat-ai/fv25_resource_trade_head_10400_10407.pt`
(SHA-256 `15c8e3ab5d72eea35d57bcfa4df1a5153079d84f3c382bd2b806c88e4fbfe992`).

Sixteen independent parent-policy recordings, seeds 11100–11103, yielded
**7,792** replay-verified decisions. On their player-visible states, the
v25 head versus the unchanged v23 parent chose Nobleman on its own only Set
monster **0/3 versus 2/3**, Nobleman with an opposing Set monster **15/19
versus 9/19**, Heavy Storm in negative visible trades **2/16 versus 3/16**,
and Heavy Storm in even-or-better visible trades **37/53 versus 1/53**.
These are counterfactual action choices on recorded states, not duel wins;
chain responses and the value of specific cards can change the actual trade.
On a separately held-out 64-duel tournament using Chaos Control/Bazoo Return
and Lolmarcus/Michael GOAT Control, both assignments and seats, seeds
11300–11307, v25 scored **31–33** directly against its unchanged parent
(paired interval **35.9%–59.4%**). The ignored report is
`.cache/goat-ai/fv25_resource_trade_head_vs_parent_11300_11307.json`
(SHA-256 `351f26830ddb83e20b99368d4abd71c47dda0d4572a721ded044db06807aabe6`).
Decision quality on this narrow resource class improved, but held-out match
strength did not; feature v25 remains experimental and M4 stays open.

On a separate matched schedule against unguarded `TacticalHeuristicAgent`,
seeds 11500–11507 with the same two held-out deck pairs, both assignments,
and both seats, v25 scored **17–47** and its unchanged v23 parent **16–48**.
The paired score difference was **+1.6 percentage points**, with a 95%
matchup-seed bootstrap interval of **−7.8 to +10.9 points**. Both policies
remain well below this tactical baseline on these deck pairs. The ignored
reports are `.cache/goat-ai/fv25_trade_vs_tactical_11500_11507.json`
(SHA-256 `84219b73c300673aa50f652d6c15c847a3a1043c5f89628079f8f387ed28bc24`)
and `.cache/goat-ai/fv23_parent_vs_tactical_11500_11507.json`
(SHA-256 `d3b205585a7b5f384062eafabae5c744265b7f58ee41db194d8e811b654a466b`).
This strengthens the conclusion that the local card-trade correction has
not established a competitive gain.

A separate full-decision on-policy imitation test relabeled **2,474**
multi-option neural decisions from the same 32 replay-verified source duels
with Tactical v14, then continued the original v23 parent for two epochs
(width 32, batch 16, learning rate 0.0001, seed 48). The source duels span
Jesse/Warrior and Return/Flip; the held-out schedule used Chaos Control/Bazoo
Return and two different Goat Control lists, both assignments and seats, on
seeds 11500–11507. The child scored **27 wins, 35 losses, and 2 draws**
directly against its parent, with a paired score interval of **33.6%–53.9%**.
This run did not close the competitive gap. Its ignored checkpoint is
`.cache/goat-ai/fv23_full_on_policy_tactical_10400_10407.pt` (SHA-256
`48a356fae3605bec346c2fad48312b47e9243f1bccd4b52d1518cdff2e59461a`)
and tournament report is
`.cache/goat-ai/fv23_full_on_policy_vs_parent_11500_11507.json` (SHA-256
`f99994ceabc287aa89783df66fb3bea2aebf7e8703b1b0e716638d0bc43c4bdd`).

### Larger on-policy imitation and response weighting

Thirty-two more parent-policy versus Tactical v14 games on the same two
training deck pairings, both seats and seeds 10408–10415, all reached
terminal and replay-verified **16,103** decisions. Combined with the
preceding 32 source games, the 64-game set supplied **5,095** multi-option
policy decisions for synthetic Tactical labels. A v23 child restarted from
the same parent and used two epochs, width 32, batch 16, learning rate
0.0001, seed 48, four verification workers, and opt-in batched forward.
Training took **41.70 seconds**, including **18.48 seconds** of replay
verification and **9.65 seconds** of model fitting. The ignored checkpoint
is `.cache/goat-ai/fv23_full_on_policy_tactical_10400_10415_batched.pt`
(SHA-256 `36701ac4b143ce0142b89f7231241f1dff96785156ac80df6505ed6b7a53e3d6`).

On 1,292 multi-option decisions from 16 separate parent-policy recordings
(seeds 11100–11103), exact raw-policy agreement with Tactical v14 rose from
**1,018** for the parent to **1,094** for the 32-game clone and **1,136**
for the 64-game clone. This is a fixed-state imitation measure. On the
previously used held-out tournament schedule, seeds 11500–11507 and two
unseen deck pairings with both deck assignments and seats, the 64-game
child scored **32–31 with one draw** directly against its parent (paired
score interval **37.5%–64.1%**). The earlier 32-game child scored
27–35 with two draws on the same schedule; their paired score difference
was **+7.0 percentage points** with a **−4.7 to +19.5** point interval.
The 64-game child scored only **13–51** against Tactical on that schedule
(paired score interval **10.9%–31.3%**), versus **16–48** for the parent.
These results do not establish a competitive gain. The ignored reports are
`.cache/goat-ai/fv23_full_on_policy_64duels_vs_parent_11500_11507.json`
(SHA-256 `32e9be6195b601eff3e082c9b6e24ea8d781a3758c00eb21dfaf31a85dde26d6`)
and `.cache/goat-ai/fv23_full_on_policy_64duels_vs_tactical_11500_11507.json`
(SHA-256 `caa3ef8314049d383072e38a990dfd452926bf4cb164b331af956ecd842c49b6`).
The 32-game and 64-game fits also used different forward implementations,
so their difference cannot be attributed to data volume alone.

The 64-game child disagreed with Tactical on 156 of those 1,292 visible
decisions, including 30 cases where Tactical passed but it chained and 14
where Tactical chained but it passed. A controlled second fit oversampled
selected `pass` and `chain` labels threefold from the same 64-game set.
It matched Tactical on **228/269** recorded chain/pass opportunities versus
**223/269** for the unweighted fit, but overall agreement fell slightly
to **1,129/1,292**. On fresh seeds 11700–11707, two unseen deck pairings,
both assignments and seats, the response-weighted child split **32–32**
directly with the unweighted child (paired score interval **42.2%–57.8%**).
The weighting did not establish a strength gain. The ignored checkpoint
is `.cache/goat-ai/fv23_full_on_policy_tactical_10400_10415_response3.pt`
(SHA-256 `58de434f974d0cb52c9e308c6af911d352d1e8e55a608a1475bb80b09f12372d`);
the tournament report is
`.cache/goat-ai/fv23_response3_vs_unweighted_11700_11707.json`
(SHA-256 `ed0644c568f448720c21277a87c24307db6cedf8a0120eff69fdb359b2ff7912`).
Neither child is promoted. The next policy experiment needs evidence that
its choices improve complete duels, not only teacher agreement.

### Clipped self-play update pilot

An opt-in single-duel clipped PPO update was compared with the existing
REINFORCE update from the same feature-v23 parent checkpoint,
`.cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt`.
Both trained for 32 native duels on the four-role schedule using Jesse Goat
Control versus Montague Warrior and DingoSig Chaos Return versus the
GoatFormat Guide Flip Control list, seeds 11820–11851. Both used learning
rate 0.0003, historical-opponent probability 0.75, a frozen-parent KL
weight of 0.1, and the learner-deck moving baseline. PPO used three epochs,
batch size 16, and clip epsilon 0.2; REINFORCE used the per-decision mean
reduction. Because policy updates change subsequent play, matched initial
seeds do not imply identical later training trajectories.

The PPO run completed 32/32 duels (20 wins, 12 losses; 3,185 learner
decisions) in 73.65 seconds. REINFORCE completed 32/32 (20 wins, 11 losses,
one draw; 2,995 learner decisions) in 76.21 seconds. All 64 recorded
training duels passed native replay verification and the visibility audit:
16,851 and 16,873 total decisions respectively. These elapsed times are
small-run measurements, not a simulator-throughput claim. The ignored PPO
checkpoint is `.cache/goat-ai/ppo32_11820_11851.pt` (SHA-256
`6bc715e0bd0977d9a1f0ee597f6db7e28126ec2012e5df4c046aecb16f706e57`);
the REINFORCE checkpoint is `.cache/goat-ai/reinforce32_11820_11851.pt`
(SHA-256 `f048bc23e99e34cbae457b2b8fa8e3490aff54105f4a3e3d2b99acdb7a5fcbe3`).

Evaluation used unseen Main Deck compositions: Insids Chaos Control versus
Weirdchamp Bazoo Return and Lolmarcus Goat Control versus Fukuyama Goat
Control, with both deck assignments and both policy seats. On held-out seeds
11900–11923, PPO scored **122 wins, 69 losses, one draw** directly against
REINFORCE in 192 games (63.8% score, paired 95% interval 57.0%–70.3%).
The two ignored report files are
`.cache/goat-ai/ppo32_vs_reinforce32_11900_11907.json` (SHA-256
`c128e96c55a245ca54bfd5a0f9eb5e93a7ac750d505d05d3e8a0a28fcfa76db7`)
and `.cache/goat-ai/ppo32_vs_reinforce32_11908_11923.json` (SHA-256
`fa402200321df57e50bcaaef2ca7cbda058233e8c57c7a1be29beae5d12a5e58`).

On a separate 64-game schedule, seeds 11924–11931, PPO scored **31–33**
against its unchanged parent (paired score interval 42.2%–54.7%) and
**11–52 with one draw** against Tactical (9.4%–27.3%). The unchanged
parent scored **13–50 with one draw** against Tactical on that schedule;
PPO's paired score difference against Tactical was −3.1 percentage points
with an interval of −14.1 to +8.6 points. These reports are
`.cache/goat-ai/ppo32_vs_parent_11924_11931.json` (SHA-256
`ce57116035fefd4357948b12128f18d5a485dc5ad74ec99b333e5a4d10cf9a2f`),
`.cache/goat-ai/ppo32_vs_tactical_11924_11931.json` (SHA-256
`975b6c66f420bc3a35daab72f4cb3753a01f42d17b363be30c618917dda12c4a`),
and `.cache/goat-ai/parent_vs_tactical_11924_11931.json` (SHA-256
`2b32c5f2a5ad2829930c6e8dced274aaa0579a42c7df90c17bc5e40c4ad3bef5`).
PPO improved relative to this REINFORCE child, but did not demonstrate an
absolute playing-strength gain. The parent remains the neural reference;
PPO remains opt-in and M4's self-play strength gate remains open.

### Four-duel PPO rollout and weighting check

The PPO trainer can now collect multiple complete duels with the same
unchanged learner policy before a clipped update. The first comparison used
four duels per update with per-decision loss weighting. A controlled variant
gave every duel equal total loss weight to test whether longer duels were
dominating the update. Both started from the same v23 parent and used the
same 32-game four-role training schedule, seeds 11820–11851, opponent-pool settings,
learning rate, three PPO epochs, minibatch size 16, clip epsilon 0.2, and
parent KL weight 0.1 as the single-duel PPO pilot above. Policy updates
changed later trajectories, so the sampled games are not identical after
the first rollout.

The unweighted four-duel run completed 32/32 games (17–15, 3,022 learner
decisions) in 75.77 seconds. Its 32 recordings passed native replay
verification and the visibility audit (16,988 total decisions). The
equal-duel-weight run completed 32/32 (18–13 with one draw, 3,196 learner
decisions) in 72.26 seconds; all 16,510 decisions likewise verified and
passed the visibility audit. The single-duel PPO control took 73.65 seconds
for 32 games with different trajectories, so these small runs do not
establish a speed gain from rollout batching. Ignored checkpoints:
`.cache/goat-ai/ppo_rollout4_11820_11851.pt` (SHA-256
`b2e6421def1630b1f3a371904183ea314bd272b7d1254b36efb03ceb1a4dbcda`)
and `.cache/goat-ai/ppo_rollout4_equal_11820_11851.pt` (SHA-256
`86004ba01c8cb5d46e95b79f054fd213eb61945b4030039e50138d7a7b671d57`).

On the same unseen-Main-Deck, two-pairing, both-assignment and both-seat
schedule as the earlier PPO pilot, with fresh seeds 11940–11947, the
unweighted rollout child scored **20–44** against single-duel PPO (paired
95% score interval 21.9%–42.2%). The equal-duel-weight child scored
**29–33 with two draws** against single-duel PPO (35.9%–58.6%) and
**30–33 with one draw** directly against the unweighted rollout child
(35.2%–61.7%). On separate seeds 11948–11955, the equal-weight child scored
**29–35** against its unchanged parent (37.5%–53.1%) and **17–47**
against Tactical (15.6%–37.5%). The unweighted child scored **31–33**
against the parent (37.5%–59.4%). None establishes an absolute gain. Keep
single-duel updates as the default; neither rollout variant is promoted.

The ignored reports, in the order above, are
`.cache/goat-ai/ppo_rollout4_vs_single_11940_11947.json` (SHA-256
`8bd4540629952dc0b6e5766f04517484ff0cf90400c1b12f283e4d0db1de370d`),
`.cache/goat-ai/ppo_rollout4_equal_vs_single_11940_11947.json` (SHA-256
`9d549cf2cef1cd720d9e0a9950c14ddeba8ef40f864fcfbc3243eaf1971dd516`),
`.cache/goat-ai/ppo_rollout4_equal_vs_unweighted_11940_11947.json` (SHA-256
`8af967acbc9b94268e81f5a8b280dce319b10bd366b276648682f308d0331dc1`),
`.cache/goat-ai/ppo_rollout4_equal_vs_parent_11948_11955.json` (SHA-256
`28ff3bfaed4fcb6856ee63ede2d56791211ba182ddf6e4baeacc692a4ad4e64c`),
`.cache/goat-ai/ppo_rollout4_equal_vs_tactical_11948_11955.json` (SHA-256
`fa84bdfe03acef9af924a70bb4c2a44d187d9432d7ef0f2f7810d89b6407235b`),
and `.cache/goat-ai/ppo_rollout4_vs_parent_11948_11955.json` (SHA-256
`551db2179b0ce6e52112e7d21b711ecc4399c7e5564bd63da9f8d9f7ae029ae0`).

With the pinned native assets and parent checkpoint present, reproduce the
equal-duel-weight training run using:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk examples/decks/warrior_montague_clash.ydk \
  --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk examples/decks/flip_control_goatformat_guide.ydk \
  --schedule-mode four_roles --seed 11820 --games 32 \
  --learning-rate 0.0003 --historical-probability 0.75 \
  --snapshot-every 8 --baseline-scope learner_deck \
  --policy-update clipped_ppo --ppo-epochs 3 --ppo-batch-size 16 \
  --ppo-clip-epsilon 0.2 --ppo-rollout-games 4 \
  --ppo-rollout-weighting per_episode --parent-kl-weight 0.1 \
  --max-decisions 3000 \
  --record-dir .cache/goat-ai/ppo_rollout4_equal_11820_11851_replays \
  --output .cache/goat-ai/ppo_rollout4_equal_11820_11851.pt
```

### Batch policy replay collection

`scripts/collect_policy_matches.py` now records a deterministic schedule of
both policy seats per matchup and seed through the existing single-duel
recorder. Every saved trajectory is replay-verified and visibility-audited;
the manifest binds the checkpoint, deck files, and trajectories by SHA-256.
With the pinned v23 parent, Jesse Goat Control versus Warrior and seed
12050, one-worker and two-worker runs each completed two games and 703
verified decisions. Corresponding trajectory bytes were identical across
worker counts. A fresh two-worker run on seed 12051 completed both games
with 663 verified and visibility-audited decisions. Its ignored manifest
is `.cache/goat-ai/policy_batch_smoke_12051_audit/manifest.json`
(SHA-256 `40a38d074dd715eaa38ee6cd5c20bd3c56da66cf4b62a6530c29e1148c018578`).
This validates the collector on a small native schedule; it does not
measure scaling for large collection jobs or policy strength.

For visual review, a new v25-versus-Tactical duel on the *previously reviewed*
Return/Flip seed 9901 reached terminal in **251 replay-verified decisions**
with the neural seat winning. Its greedy choices reproduce from the saved
checkpoint, and the resource-review shortlister found no candidate in that
new trajectory. The ignored viewer is
`replays/neural_v25_trade_head_vs_tactical_return_flip_seed9901.html`.
This reused seed is an explanatory replay, not held-out strength evidence;
the policy still Sets multiple Spells/Traps early and may overcommit back row.

The post-Balter script fingerprint prevents the current verifier from using
some older pre-correction demonstration replays as KL-preservation inputs.
The two-preference experiment therefore preserved four newer, current-asset
policy trajectories from seeds 10400 instead. Old checkpoints retain their
original trajectory hashes and can be reproduced from the corresponding
earlier code and pinned native assets. Generated data and checkpoints remain
ignored by Git.

With the 32 source trajectories recorded by `record_policy_match.py` in
`.cache/goat-ai/on_policy_teacher_10400_10407/`, reproduce the v25 head and
held-out tournament after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/train_behavioral_clone.py \
  .cache/goat-ai/on_policy_teacher_10400_10407/*.json \
  --engine experimental --on-policy-teacher tactical_card_advantage \
  --on-policy-teacher-activation-focus-only \
  --focus-card 504700116 --focus-card 19613556 \
  --feature-version 25 --width 32 --epochs 30 --batch-size 16 \
  --learning-rate 0.01 --seed 47 --trainable-module trade_head \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --upgrade-feature-23-to-25 \
  --output .cache/goat-ai/fv25_resource_trade_head_10400_10407.pt
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/evaluate_policy.py \
  .cache/goat-ai/fv25_resource_trade_head_10400_10407.pt \
  --engine experimental \
  --opponent-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
            examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 11300 --seeds 8 --workers 4 \
  --output .cache/goat-ai/fv25_resource_trade_head_vs_parent_11300_11307.json
```

### Forced-choice inference shortcut (27 October 2026)

Self-play sampling now returns the only legal action without encoding an
observation, running a policy forward pass, or consuming the policy's sampling
generator. This applies equally to the learner and frozen-policy opponents;
multi-option decisions still use the same sampling path. The changed generator
consumption means new seed-matched runs need not reproduce action sequences
from earlier code revisions. Trajectory replay remains based on recorded
actions.

On Linux x86_64 with PyTorch CPU and `OMP_NUM_THREADS=1`, a single ignored
trajectory (`.cache/goat-ai/on_policy_teacher_10400_10407/jesse_warrior_10400_seat0.json`,
SHA-256 `e5ce07fa2e62f2dcfe6b7613260207a416dc636e291baec26b0a2e0748863fe9`)
contained **716 forced choices among 1,122 decisions**. Scoring those 716
recorded forced choices once with the previous encode/forward/sample path took
**0.956638 seconds**; the shortcut took **0.000534 seconds**. Both returned the
recorded action every time. This measures only forced-choice policy work in one
process, not complete duel throughput or training-wall-time speedup. The
corresponding focused policy and native information-boundary tests passed:
`86 passed` in 2.67 seconds.

A separate native smoke ran the v23 checkpoint against `RandomAgent` on the
control/Chaos probe decks at seed 441. It reached terminal in 1,347 decisions
and 2.085 seconds of episode wall time; all 1,347 decisions replay-verified
and passed the legal-choice visibility audit. This was one optimized run, with
no matched pre-change whole-duel timing.

The reproducible `scripts/benchmark_forced_inference.py` ablation ran four
complete, matched duels (seeds 12000–12003, 4,322 decisions per schedule)
twice, reversing the order of the reference and shortcut paths. The reference
still skips RNG consumption on forced choices, isolating only the redundant
encode/forward work. All eight reference/shortcut trajectory pairs were
identical. On an Intel Core i7-10700K, Linux 6.8.0 x86_64, PyTorch 2.5.1 CPU,
and one Torch thread, the reference and shortcut times were respectively
**8.816 vs 7.123 seconds** (1.238×) and **8.768 vs 6.910 seconds** (1.269×).
These are two matched schedules on the control/Chaos probe decks; other decks,
hardware, and training updates may differ. The checkpoint SHA-256 was
`93ca70795e2c5316ab349a4e5c61ebd553915e49abdbe469d0976d3bebe3d9b2`.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/benchmark_forced_inference.py \
  .cache/goat-ai/fv23_tactical_v6_current_assets.pt --games 4 --rounds 2
```

One `cProfile` pass over the optimized first duel attributed about 1.16 of
2.23 profiler-accounted seconds to building native observations, including
0.79 seconds in native location queries. Policy sampling took 0.54 seconds.
These overlapping cumulative times identify observation construction as the
next performance candidate, but the Python profiler does not establish how
much can be saved without changing the information contract.

### Greedy forced-choice and inference-mode ablations (27 October 2026)

Greedy `PolicyAgent` now returns its sole legal action without feature encoding
or a network forward. The self-play sampler and greedy agent also use PyTorch
inference mode for multi-option decisions. Neither change alters model weights,
legal choices, or the agent's information boundary. A focused test makes the
greedy policy forward fail if it is called on a forced decision.

On the same Intel Core i7-10700K, PyTorch 2.5.1 CPU, and one Torch thread, an
AB/BA benchmark of four native control/Chaos probe duels (seeds 12000–12003)
found 1,020 forced **greedy-policy** decisions per schedule. Each comparison
produced exactly the same four native trajectories, with 3,284 total decisions.
The reference path still scored forced choices and took **4.888 versus 3.398
seconds** in the first order (1.438×); the reversed order took **4.676 versus
3.370 seconds** (1.387×). This is a measured speedup for these complete
greedy-policy duels against `RandomAgent`, not a training update or a playing
strength gain.

An independent AB/BA benchmark isolated inference mode in sampled self-play on
the same four seeds. All trajectories matched. No-grad versus inference-mode
times were **3.835 versus 3.542 seconds** (1.083×) and **3.518 versus 3.582
seconds** (0.982×); the full-duel result is inconclusive at this scale. A
single fixed-decision, 3,000-forward microbenchmark measured approximately
3.00 versus 2.67 seconds, but does not establish an overall duel speedup.
Both benchmarks used v23 checkpoint SHA-256
`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/benchmark_greedy_forced.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --games 4 --rounds 2 --seed 12000
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/benchmark_inference_mode.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --games 4 --rounds 2 --seed 12000
```

### Batched REINFORCE update microbenchmark (27 October 2026)

The supported `--reinforce-batch-size 16` path was compared against scalar
updates on the same 136 learner decisions from a recorded feature-v23 native
duel. Four AB/BA rounds each started from the same parent weights and Adam
optimizer settings. Scalar CPU update time was **0.423–0.450 seconds**;
batched time was **0.110–0.116 seconds** (**3.73–3.93×** for this update).
Mean reported loss differed by about `1.58e-8`, and the largest post-update
parameter difference was `1.82e-5`. This measures one update, not whole
self-play training or playing strength. The ignored
report is `.cache/goat-ai/reinforce_batch_microbench_20261027.json`
(SHA-256 `915404428ea2bbd1e9ece9e4553b4b79975147b0cbbe9c022e8168fe08dbfac0`).

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/benchmark_reinforce_update.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  .cache/goat-ai/fv23_parentkl_timer_smoke/episode_00000_seed_7600.json \
  --seat 0 --batch-size 16 --rounds 4
```

An AB/BA full-training pilot used the same feature-v23 parent, two sourced
Jesse/Warrior and DingoSig Return/Flip pairings, four-role seats, seeds
14000–14007, a 3,000-decision cap, REINFORCE mean reduction, learner-deck
baseline, and frozen-parent KL weight 0.1. With one Torch thread, the scalar
eight-game runs took **9.595 and 9.485 seconds**, versus **6.861 and 6.855
seconds** with batch size 16 (about **1.40× and 1.38×**). Each mode repeated
bit-identical weights across order, and all runs reported the same eight
winners and game lengths (4–4, 819 learner decisions). Scalar and batched
final weights differed by at most `2.05e-4`; identical summaries do not
prove identical action sequences or held-out strength. This establishes a
small-schedule training wall-time gain, not a competitive gain. Batch size 16
remains opt-in for supported feature versions until broader outcome checks.
The four ignored run reports are
`reinforce_batch_ab_scalar_14000.json` (SHA-256
`2070b5d331486a33092511722dea9ac10c7e94bed8ce75831688e989b8288e29`),
`reinforce_batch_ab_batched_14000.json` (`5be005fc2850c0857a37151d708e981685023e8a9b396ec7befeca14f61b13bb`),
`reinforce_batch_ba_batched_14000.json` (`1939b59e24c4cddc5c6097d408f7857ea194f83bfb91b26fd4a7d22a19b8bee8`),
and `reinforce_batch_ba_scalar_14000.json`
(`1f3e6811fa5c30d1eb44d882fe72c7c35a9aaccee59ff7005f41afd82e2bf724`)
under `.cache/goat-ai/`.

### Player-visible disagreement review queue (27 October 2026)

`scripts/shortlist_policy_disagreements.py` now turns existing greedy policy
replays into a bounded human-review queue. It requires the matching checkpoint
hash, replays each complete duel against pinned native assets, audits the
recorded visibility boundary, and reproduces the complete greedy agent's
choices, including its cancel/selection safeguards. It then asks Tactical-v14
what it would choose from each *recorded player-visible legal set*. Different
choices and conservative player-visible audit flags enter the queue. Audit
flags rank first; remaining disagreements rank by the model's probability
margin. Both groups are limited by response pattern and replay. Each
counterfactual teacher choice starts with fresh
agent memory, so a teacher-proposed attack that the policy never executed
cannot influence a later label. This ranking is a review priority only:
Tactical may be wrong, probability is not a value estimate, and neither
choice becomes a training label without a separate human preference annotation.

The four seeds 12100–12103 across both sourced Jesse/Warrior and DingoSig
Return/Flip matchups and both policy seats supplied **16 complete,
replay-verified duels**, **7,071 verified decisions**, and **291
disagreements** among 3,505 policy-seat choices. The visible-state audit
flagged eight choices; one of those had the same Tactical choice, yielding
292 total candidates. The bounded queue selected 20 prompts, including four
audit-flagged choices, from 14 replay viewers. The generated
`review_queue_12100_12103.html` index presents card names and direct frame
links; all 20 local links resolve. Queue entries expose selected legal-action
summaries and omit raw observations and outcomes. The ignored queue is
`.cache/goat-ai/review_queue_12100_12103.json` (SHA-256
`13db476e557ec3e3672030bced456e8d291850e652832d46db1f63f0fa17c170`).

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  .cache/goat-ai/policy_vs_tactical_12100_12115/matchup_*_seed_1210[0-3]_seat_*.json \
  --limit 20 --per-replay 2 \
  --output .cache/goat-ai/review_queue_12100_12103.json --render-viewers
```

The visible-state audit now also flags Chaos Sorcerer or Black Luster Soldier
banishing itself when a legal opposing target exists, and Raigeki Break
targeting a friendly card with an opposing target available. These remain
human review prompts; the latter can have situational uses. An extended
18-duel queue added policy replays `matchup_01_seed_12105_seat_0.json` and
`matchup_00_seed_12115_seat_1.json` to the original schedule. It verified
**8,578 decisions**, including **4,273 policy-seat choices**, and found
**334 Tactical disagreements** plus one audit-only choice, for **335
candidates**. The 24 selected prompts include six audit findings across
16 replay viewers. The new Chaos Sorcerer self-banish at decision 111 and
Black Luster Soldier self-banish at decision 727 each had a legal opposing
monster target in that player's recorded view. The ignored output is
`.cache/goat-ai/review_queue_extended_20261027.json` (SHA-256
`a1284f5f163e07cc477ba9a34b39b6a94194bd757dd24ccaf4f6cfb9681e40e7`);
its adjacent HTML index links to the review frames. This changes review
coverage, not trained weights or competitive strength.

### Self-banish preference pilot (27 October 2026)

The player had repeatedly identified Black Luster Soldier and Chaos Sorcerer
banishing themselves as a serious error when an opposing monster is available.
Two **rule-derived** pairwise annotations apply that general guidance to
specific native-verified policy decisions; the player did not review these
exact frames. They are tracked as
`examples/preferences/fv23_chaos_sorcerer_self_banish_12105_p0.preference.json`
and `examples/preferences/fv23_bls_self_banish_12115_p1.preference.json`.
At decision 111 of the first replay, Sorcerer chose itself over one opposing
monster. At decision 727 of the second, Black Luster Soldier chose itself
over four opposing Sheep Tokens. All legal non-self targets are acceptable
for this *target-choice* comparison; it does not establish that activating
the banish effect was better than an earlier attack or pass. The annotations
bind to their source replay hashes and acting seats. The preference reader
now rejects a supplied `reviewed_seat` if it disagrees with the replay's
agent seat. This does not turn the derived labels into direct human reviews.

`scripts/train_review_preferences.py` replay-verified and visibility-audited
both policy sources and four preservation replays from the parent checkpoint.
Three older potential preservation replays were rejected because their
recorded hash for `scripts/pre-errata/c511000818.lua` differs from the
current native asset; the pilot used four currently verifiable Return/Flip
replays instead. Starting from the frozen feature-v23 parent, 120 preference
steps used 64 sampled preservation states, batch 16, parent KL weight 1.0,
learning rate 0.0001, and seed 27. Preference loss fell from **1.5357** to
**0.0490**; final sampled preservation KL was **0.0010**. The child selected
a non-self target at both *training* decisions, versus 0/2 for the parent.
Its ignored checkpoint is
`.cache/goat-ai/fv23_self_banish_pairwise_12105_12115.pt` (SHA-256
`513b765b5d3265ab89d680f5595f496bb94c6739c8ab085b38e56fdc90b00770`).

Held-out Main Deck composition checks passed for Insids Chaos Control versus
Weirdchamp Bazoo Return and Lolmarcus Goat Control versus Fukuyama Goat
Control, with both deck assignments and seats. Against its parent, the child
scored **35–29** on seeds 14100–14107 and **31–32–1** on fresh seeds
14108–14115. Pooled over 128 games, it scored **66–61–1** (51.95%, paired
95% interval **44.92–58.98%**). On seeds 14116–14123 against Tactical-v14,
the child scored **15–49** and the unchanged parent **12–52**; their paired
score difference was 4.69 percentage points (95% interval **−4.69 to
14.06 points**). These small, same-family schedules show target-choice fit
but no established competitive gain. Keep the parent as the reference and
the child experimental.

The ignored evaluation reports are
`.cache/goat-ai/fv23_self_banish_vs_parent_14100_14107.json` (SHA-256
`999ac95860d81f98b8106c2ea6235b37c2e6b90433b6187d2d339b9f7876c477`),
`.cache/goat-ai/fv23_self_banish_vs_parent_14108_14115.json`
(`e57f52bd6276f344cc3775294a2a0a7bcee710940577ef6fe1f1ba40960cdd30`),
`.cache/goat-ai/fv23_self_banish_vs_tactical_14116_14123.json`
(`43f6f6fa784e7e399be4d5569d3ffdb7054235e5ff1e8a3c3b215448fdcca60d`),
and `.cache/goat-ai/fv23_self_banish_parent_vs_tactical_14116_14123.json`
(`a52e688fbaaff749a7142aee358c86b9fb21583d8a12d527de490fa82c09a40b`).

`scripts/compare_tournament_reports.py` now validates saved game outcomes,
declared evaluation seeds, training-seed separation, summary counts, and
matched schedules before computing a paired score difference. It also
requires identical opponent identity, opponent settings, deck hashes,
engine, core commit, and recorded global native-asset hashes. With
`--verify-local-decks`, it checks the currently available deck bytes against
each report. Applied to the two Tactical reports above, it reproduced the
**4.69-point** difference and **−4.69 to 14.06-point** paired interval.
These older tournament reports do not bind every loaded card script, so
matching their recorded global hashes does not independently prove their
entire native script trees were identical. New `evaluate_policy.py` reports
also include SHA-256 fingerprints of the complete Lua script tree and the
project Python source plus evaluators. The comparator requires those
fingerprints to match when either report contains them. A two-game native
smoke report on seed 14300 recorded script-tree fingerprint
`f886f54c419d3792fd69888d74190c070992609caad8f5737e3f563bd736b71c`
and source fingerprint
`78b6a2088879cfd7d1da034a59eee8f777a436d6f627533bfa5b699315d1298f`;
comparing it to itself with local deck-byte verification returned exactly
zero paired difference. Its ignored report is
`.cache/goat-ai/evaluate_policy_script_tree_smoke_14300.json` (SHA-256
`bd5fc7e7e3e1aab464ad3d6f08418cac8630428b3cf1ead6fb126fc538d59621`).

```bash
PYTHONPATH=src:. python scripts/compare_tournament_reports.py \
  .cache/goat-ai/fv23_self_banish_vs_tactical_14116_14123.json \
  .cache/goat-ai/fv23_self_banish_parent_vs_tactical_14116_14123.json \
  --verify-local-decks
```

### Broader Tactical continuation and batched fitting (27 October 2026)

To test whether more deck variety helps the feature-v23 policy, the unchanged
parent (SHA-256 `9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`)
was continued on 16 new native Tactical-v14 versus Combat-v3 duels. The
training pairs were Insids Chaos Control/Weirdchamp Bazoo Return (seeds
14400–14403) and Lolmarcus/Fukuyama Goat Control (14410–14413), each with
both teacher seats. All 16 duels reached terminal, were replay-verified and
visibility-audited by the training command, and supplied 4,464 Tactical-seat
decisions. The teacher won 14/16. The resulting checkpoint contains 96
training games across 12 distinct Main Deck compositions. These are
synthetic teacher labels, not human demonstrations.

With width 32, feature v23, two epochs, minibatch 16, learning rate 0.0002,
seed 45, and four replay-verification processes, the batched-forward run took
**14.22 seconds** overall, including **4.32 seconds** of verification and
**6.72 seconds** of fitting. Epoch loss was **0.18939**, then **0.16347**.
The same input and settings through the scalar-forward reference took
**32.97 seconds** overall, including **4.28 seconds** of verification and
**25.46 seconds** of fitting. Batched forward was **3.79× faster for fitting**
and **2.32× faster end to end** in this one matched run. Losses agreed to
within `8e-10`, although final parameters differed by as much as `0.00375`;
the two numerical paths are not bit-identical. The batched child checkpoint
is ignored at
`.cache/goat-ai/fv23_tactical_v14_sixdeck_continuation_14400_14413.pt`
(SHA-256 `5941c66ec1ee68babf2f359c9e6dab807b3e50021761fe0ce8214aac873abab0`).

The reserved GoatFormat Guide and WikiFormat Dimension Fusion Turbo Main
Decks were absent from both the parent and child training compositions.
Across both deck assignments and seats on seeds 14500–14515, the batched
child scored **36–27–1** against its parent over 64 games: **57.03%** score,
with matchup/seed paired 95% bootstrap interval **48.44–65.63%**. On seeds
14516–14523 against Tactical-v14, the child scored **8–24** and the parent
**6–26** on the same 32-game schedule. The paired score difference was
**6.25 points**, interval **−12.5 to 25 points**. Neither comparison
establishes a competitive gain, and Tactical remains substantially stronger
on these decks. Keep the parent as the reference. All reports record the
current native script-tree and project-source fingerprints.

The four ignored tournament reports, in order, are
`fv23_sixdeck_vs_parent_dimension_14500_14507.json` (SHA-256
`bf27c6517ddbfdba06a7c49d6414a6e05a0f3b29ee44c234bd1420ee9250cc92`),
`fv23_sixdeck_vs_parent_dimension_14508_14515.json`
(`39c422c5ecedb6fcc62e0cf4fb9484692744a59025ea867fa31285d3e215d7c5`),
`fv23_sixdeck_vs_tactical_dimension_14516_14523.json`
(`b0dfbc0dd55cf4be0f772a387254b9f38d66dd67f287a1701c8f2ed3a4f06a53`),
and `fv23_parent_vs_tactical_dimension_14516_14523.json`
(`82c17b8a0f0e538404e3be42d6f9eafb50357e4bcbf44bb623c595ba24278eed`).
Reproduce collection and fitting with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher tactical --opponent combat_heuristic \
  --deck-a examples/decks/chaos_control_insids_worlds_2022.ydk \
  --deck-b examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --seed 14400 --seeds 4 \
  --output-dir .cache/goat-ai/tactical_v14_insids_bazoo_14400_14403
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher tactical --opponent combat_heuristic \
  --deck-a examples/decks/goat_control_lolmarcus_2020.ydk \
  --deck-b examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --seed 14410 --seeds 4 \
  --output-dir .cache/goat-ai/tactical_v14_lolmarcus_fukuyama_14410_14413
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/train_behavioral_clone.py \
  .cache/goat-ai/tactical_v14_insids_bazoo_14400_14403/seed_*.json \
  .cache/goat-ai/tactical_v14_lolmarcus_fukuyama_14410_14413/seed_*.json \
  --engine experimental --feature-version 23 --width 32 --epochs 2 \
  --batch-size 16 --batched-forward --verification-workers 4 \
  --learning-rate 0.0002 --seed 45 \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/fv23_tactical_v14_sixdeck_continuation_14400_14413.pt
```

### Fresh-asset KL preservation for replay preferences (27 October 2026)

`train_review_preferences.py` now accepts `--preserve-current-trajectory`
for new full-duel replays in addition to `--preserve-trajectory` for exact
parent-training replays. Both modes replay-verify against current native
assets and pass the visibility audit. The new mode rejects replay bytes
already in parent or review training, seeds used by the parent or reviews,
and duplicate paths or bytes. Its games and hashes enter the child checkpoint
as **preservation-only training provenance**: they affect the frozen-parent
KL loss, so held-out evaluation excludes their seeds and Main Deck
compositions. This permits preservation coverage after a historical script
correction makes some old parent recordings unverifiable; it does not silently
accept those old recordings under changed rules.

A native pilot reused the two rule-derived self-banish preferences above and
four current-asset Tactical trajectories from seeds 14400 and 14410, each
with both teacher seats. All six complete replays verified. The trainer
sampled 64 multi-option preservation decisions and took 120 steps with the
same preference optimizer settings as the earlier pilot. Preference loss fell
from **1.53573 to 0.04901**; sampled preservation KL ended at **0.00177**.
The child chose a preferred non-self target at both **training** decisions.
Its checkpoint contains 80 parent training games, two preference games,
and four preservation-only games, with exact hashes for all 86. It is ignored
at `.cache/goat-ai/fv23_self_banish_current_preservation_14400_14410.pt`
(SHA-256 `16c62333fe3087c10d9cf4223400fda5dc550c969e9108d240a202421ad28595`).

The GoatFormat Guide/WikiFormat Dimension Fusion Turbo pair remained unseen
by parent, preference, and preservation training. On seeds 14600–14607,
both deck assignments and seats, the child scored **18–14** directly against
its parent (32 games; paired 95% score interval **50–62.5%**). Against
Tactical-v14 on the same schedule it scored **5–27**, while the parent scored
**3–29**. Their paired score difference was **6.25 points**, interval
**0–15.625 points**. These small tests do not establish a competitive gain;
the parent stays the reference. The three ignored reports are
`fv23_current_preservation_vs_parent_dimension_14600_14607.json` (SHA-256
`fcacaf42984de0153c0d533c112a6f1098c2690bd32d12b3be01aea268e39b4f`),
`fv23_current_preservation_vs_tactical_dimension_14600_14607.json`
(`94dc2a038497c40f81a46b402cab80533edf25b623ef93209cd39d4ddeba2215`),
and `fv23_parent_vs_tactical_dimension_14600_14607.json`
(`0f184b1d8de21ecffd1eb63a9512e5728debb216675707fecff7d17d6ff75a61`).
The focused preference and provenance tests passed (**15 tests**).
The original parent-replay option also completed a one-step native smoke
using the replay-verified seed-9110 Return/Flip game.

After collecting the source trajectories using the commands above, reproduce
the pilot with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/train_review_preferences.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --case .cache/goat-ai/policy_vs_tactical_12100_12115/matchup_01_seed_12105_seat_0.json \
    examples/preferences/fv23_chaos_sorcerer_self_banish_12105_p0.preference.json \
  --case .cache/goat-ai/policy_vs_tactical_12100_12115/matchup_00_seed_12115_seat_1.json \
    examples/preferences/fv23_bls_self_banish_12115_p1.preference.json \
  --preserve-current-trajectory .cache/goat-ai/tactical_v14_insids_bazoo_14400_14403/seed_14400_seat_0.json \
  --preserve-current-trajectory .cache/goat-ai/tactical_v14_insids_bazoo_14400_14403/seed_14400_seat_1.json \
  --preserve-current-trajectory .cache/goat-ai/tactical_v14_lolmarcus_fukuyama_14410_14413/seed_14410_seat_0.json \
  --preserve-current-trajectory .cache/goat-ai/tactical_v14_lolmarcus_fukuyama_14410_14413/seed_14410_seat_1.json \
  --steps 120 --preserve-per-trajectory 16 --preserve-batch 16 \
  --parent-kl-weight 1 --learning-rate 0.0001 --seed 27 \
  --output .cache/goat-ai/fv23_self_banish_current_preservation_14400_14410.pt
```

### Exact self-play replay provenance (27 October 2026)

`train_self_play.py` now records every terminal training duel by default in
`<checkpoint-stem>_replays/` beside its output checkpoint. An explicit
`--record-dir` can select another empty directory. Each new training-game
entry names its replay and SHA-256; the checkpoint's `trajectory_sha256` map
contains those hashes along with the parent's. The trainer rejects missing,
changed, duplicated, or overlapping replay paths before saving the child.
Censored games have no training-game entry. Existing checkpoints are not
retroactively given replay provenance.

A one-game experimental-engine smoke from the unchanged four-deck v23 parent
used control/Chaos probe decks at seed 14700. It completed **1,072 native
decisions**, including **216 learner decisions**, and reported **2.519 s**
run wall time. The saved trajectory hash matched both the new training-game
entry and the checkpoint hash map. Full native replay verification returned
1,072 decisions, and the visibility audit passed. The ignored checkpoint is
`.cache/goat-ai/selfplay_provenance_smoke_14700.pt` (SHA-256
`6dcfdd6358c8f93e7657fe3b462b22a71aedb7e013d5ce983d25fb5b132bab00`);
its replay is in the adjacent `_replays` directory (SHA-256
`3ef7714b8eb8e3ca3a72d24c448dc68e1915acfaab42c90f91e8f0821c1eaec2`).
This is a provenance and reproducibility check, not a strength result or a
throughput benchmark.

### Replay serialization cost (27 October 2026)

Profiling one 437-decision, single-game self-play run at seed 14701 attributed
about **0.36 profiler-accounted seconds** to writing its replay. The writer
now lets JSON traverse dataclass fields directly instead of building a
recursive `dataclasses.asdict` copy. Its schema validation and on-disk format
are unchanged. The 437-decision replay then passed full native verification
and the player-visible trajectory audit.

An AB/BA in-memory serialization benchmark, excluding replay loading and
file I/O, compared both encoders on two current schema-v25 replays. Each
round produced **byte-identical output**, also identical to the original
replay file. On the 437-decision, 4.34 MB replay, legacy conversion/encoding
took **0.114–0.141 s** and shallow encoding **0.082–0.086 s** across four
rounds. On a 1,072-decision, 13.38 MB replay, the ranges were **0.347–0.444
s** and **0.239–0.255 s**. Two rounds each on schema-v17 and schema-v3
replays also matched between encoders. Those older loaded objects normalize
legacy fields, so neither encoder reproduces the original old-file bytes.
This isolates a serialization speedup, not a measured full-training gain.

The ignored benchmark reports are
`.cache/goat-ai/trajectory_serializer_14701.json` (SHA-256
`812023f97404abc80fcd5bccdf44cfba35496733db592959fab9fa52aa6e164e`),
`.cache/goat-ai/trajectory_serializer_14700.json` (SHA-256
`ff1a0a8e506c994b94565eaa07ce97fac6bb864cb9f6412008e3b2517806a74d`),
`.cache/goat-ai/trajectory_serializer_v17.json`, and
`.cache/goat-ai/trajectory_serializer_v3.json`. Reproduce the current-schema
measurements with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/benchmark_trajectory_serialization.py \
  .cache/goat-ai/selfplay_profile_14701_replays/episode_00000_seed_14701.json \
  --rounds 4
```

### Resource trade head on new deck families (27 October 2026)

The experimental v25 resource trade head was evaluated on four Main Deck
compositions absent from both its training lineage and the v23 parent's:
WikiFormat Dimension Fusion Turbo, Roberto Martinez Phoenix Control,
WeirdChamp Bazoo Return, and Michael Fukuyama Goat Control. Two pairings
(Dimension Fusion/Phoenix and Bazoo/Michael) used both deck assignments and
both seats. Against its unchanged v23 parent, v25 won **34 of 64** duels on
seeds 17000–17007; its paired 95% bootstrap score interval was **43.8%–60.9%**.
The ignored report is
`.cache/goat-ai/fv25_vs_parent_df_phoenix_bazoo_michael_17000_17007.json`
(SHA-256 `aea4b728590129569acf8a58edb4f07412b0c19b0d0a930f46f22d2fdb11c734`).

On a separate matched schedule against unguarded Tactical v14, seeds
17008–17015, v25 won **16 of 64** and v23 won **15 of 64**. The paired
score difference was **+1.6 percentage points**, with a 95% matchup-seed
bootstrap interval of **−7.8 to +10.9 points**. The reports are
`.cache/goat-ai/fv25_vs_tactical_df_phoenix_bazoo_michael_17008_17015.json`
(SHA-256 `077393ed1a3e028ce2709f9562307dcb4db2cd38a1a190973b04b1b09d26c8c2`)
and `.cache/goat-ai/fv23_parent_vs_tactical_df_phoenix_bazoo_michael_17008_17015.json`
(SHA-256 `a531605205073265ef172dd7f675d9f82847f74a92c00662ca2f1f54eabe019b`).
`compare_tournament_reports.py --verify-local-decks` accepted matching engine,
source, assets, card scripts, deck hashes, seeds, opponent, and assignments.
The new deck families did not establish a competitive gain, and both neural
policies remain far below Tactical on this schedule. v25 stays experimental.

One v25-versus-Tactical Dimension Fusion/Phoenix duel at seed 17008 ended in
a v25 loss. Its **482** decisions passed native replay verification and its
**227** policy choices reproduced from the saved checkpoint; the visibility
audit passed. The existing candidate detector returned no flagged decisions
for this duel, which is not evidence that every play was sound. The ignored
trajectory is `.cache/goat-ai/fv25_df_vs_phoenix_tactical_17008.json`
(SHA-256 `a52f48b2aec065e0c8cd2231c928bd33088ba526c5e5a52bdd2a3567dc49a12c`).
The next policy experiment should address the wider action-value errors
visible in losses, and require improvement against Tactical across multiple
unseen deck families before replacing v23.

### Focused Thunder Dragon imitation pilot (27 October 2026)

The held-out loss audit exposed repeated missed Thunder Dragon activation
opportunities. A new **32-duel** policy-versus-Tactical collection used
WikiFormat Dimension Fusion/Michael Goat Control and WeirdChamp Bazoo
Return/Roberto Martinez Phoenix, seeds 17200–17207, both policy seats. All
**14,715** decisions replay-verified. Among the policy seat's multi-option
states, **71** offered a Thunder Dragon activation; Tactical v14 chose that
activation in **58**, and disagreed with the recorded policy in **53**. These
are synthetic baseline labels, not human demonstrations. The ignored
collection manifest is
`.cache/goat-ai/fv23_td_opportunity_train_17200_17207/manifest.json`
(SHA-256 `b06d6c2ff12aa8818a9b00ec1ba8199572828bdbcbcf74d26b9593aad655d8bf`).

A child of the unchanged feature-v23 reference trained **only its scorer**
on those 71 labels for 12 epochs, batch 16, learning rate 0.0003, seed 53.
Training took **13.45 s**, including **6.16 s** for source replay
verification and **0.89 s** for fitting. The ignored checkpoint is
`.cache/goat-ai/fv23_td_score_head_17200_17207.pt` (SHA-256
`bce9bacc9449e8973dfcb2837f2a316ec01ff06862deef057fd47524383db973`).
On the earlier eight replay-verified loss-audit duels, excluded from this
fit, the child chose Thunder Dragon activation in **9/13** offered states
versus the parent's **1/13**; exact Tactical agreement on those states was
**6/13 versus 1/13**. Overall agreement on the 534 multi-option policy
states was **428/534 versus 408/534**. These are counterfactual decisions
on recorded states, not wins.

For competitive evaluation, Dimension Fusion Turbo from GoatFormat Guide,
Insids Chaos Control, and Lolmarcus Goat Control Main Deck compositions were
absent from both the parent and child training lineages. On two pairings of
the first two decks versus Lolmarcus, both assignments and seats, seeds
17300–17307, the child scored **26–38** directly against its parent over 64
duels (paired 95% interval **28.1%–53.1%**). When piloting the two Thunder
Dragon decks it won only **8/32**. The ignored report is
`.cache/goat-ai/fv23_td_score_head_vs_parent_17300_17307.json` (SHA-256
`6dad0fe093c507e6d797cc671539ee5494c88b95b0948ee5a5d54468fe39ae50`).
On a separate matched schedule versus Tactical, seeds 17308–17315, the child
won **7/64** and the unchanged parent **6/64**. The paired score difference
was **+1.6 percentage points** with a 95% matchup-seed interval of
**−6.3 to +9.4 points**. Both policies went **0/16** when piloting Insids
Chaos Control. The ignored child and parent reports are
`.cache/goat-ai/fv23_td_score_head_vs_tactical_17308_17315.json` (SHA-256
`08fcdd8d0ad60e6552fd6380a289cd5afb6809717112d62aeae7e6229431390a`)
and `.cache/goat-ai/fv23_parent_vs_tactical_17308_17315.json` (SHA-256
`dc61c9baec389469c4db17f7d2e69bc29da59e6e45e3c2d2f6aa44aa05f5235b`).
The saved-report comparator accepted matching assets, code, card scripts,
decks, seeds, and opponent for the Tactical pair. The focused fit corrected
some isolated decisions but did not improve held-out match strength; the v23
reference remains unchanged. Broader card-value and timing feedback, with
separate competitive checks, is needed before another promotion attempt.

Reproduce the fit after collecting the 32 source duels with
`scripts/collect_policy_matches.py` on the named training pairings and seeds:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/fv23_td_opportunity_train_17200_17207/matchup_*.json \
  --engine experimental --on-policy-teacher tactical_v14 \
  --on-policy-teacher-activation-focus-only --focus-card 504700054 \
  --feature-version 23 --width 32 --trainable-module score \
  --epochs 12 --batch-size 16 --batched-forward --verification-workers 4 \
  --learning-rate 0.0003 --seed 53 \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/fv23_td_score_head_17200_17207.pt
```

Use `scripts/evaluate_policy.py` with the two held-out pairings above,
`--both-deck-assignments --require-unseen-main-decks --seeds 8 --workers 4`.
For the direct comparison use `--seed 17300` and `--opponent-checkpoint`
pointing to the unchanged v23 parent. For the matched Tactical reports use
`--seed 17308 --opponent tactical` with each checkpoint in turn.

### Early visible-value signal audit (27 October 2026)

The current synthetic-teacher and sparse-terminal-reward experiments have not
produced a cross-deck strength gain. Before adding card-advantage reward
shaping, `scripts/audit_visible_value_signals.py` measured two fixed,
player-visible quantities at the **first learner Main Phase at or after turn
four**, once per completed policy-versus-Tactical game. Card margin is own hand
size minus opponent hand size plus the count of controlled field cards minus
opposing field cards, excluding visible Sheep Tokens. LP margin is the same
player's Life Point difference in thousands. The audit uses only the acting
player's observation and compares each game's early value with its eventual
binary win/loss; draws and games without the snapshot are excluded. Its AUC is
pairwise win-versus-loss ranking accuracy, with 0.5 for ties.

| Fresh source batch | Games sampled | Policy wins | Card margin AUC | LP margin AUC |
| --- | ---: | ---: | ---: | ---: |
| Seeds 10400–10407 | 32 | 8 | 0.771 | 0.365 |
| Seeds 10408–10415 | 31 | 8 | 0.595 | 0.766 |

Both batches use Jesse/Warrior and Return/Flip training-deck pairings, with
both policy seats. One second-batch duel ended before the chosen snapshot.
The reversal means this tiny retrospective sample does not support a fixed
card-margin or LP-margin reward weight. Deck effects and later decisions can
confound either metric; AUC here does not identify causal action value. This
does not refute the user's card-advantage insight, but it is insufficient to
alter the terminal-win objective. Future value experiments need broader deck
families, calibration on held-out games, and competitive comparisons.

Reproduce the ignored reports from the 64 replay-verified source duels:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/audit_visible_value_signals.py \
  .cache/goat-ai/on_policy_teacher_10400_10407 \
  --output .cache/goat-ai/value_signals_10400_10407.json
PYTHONPATH=src:. .venv/bin/python scripts/audit_visible_value_signals.py \
  .cache/goat-ai/on_policy_teacher_10408_10415 \
  --output .cache/goat-ai/value_signals_10408_10415.json
```

The report SHA-256 values are
`ce5fb3f58da74e8c75026a3566dabe99d87117f787a8da5ca0c463735f8ef7e0` and `64baf655633de5aa942388333adde697333d3c5b4c8592c22af7b616a6b6612e`, respectively; each report binds the
individual source replay hashes and sampled snapshot turns.

### Diverse resource-trade head and held-out outcome check (27 October 2026)

The unchanged feature-v23 parent still selected obvious visible resource
losses in its 64 saved policy-versus-Tactical games from seeds 12100–12115.
The player-visible replay audit flagged 10 Nobleman activations with only a
friendly Set monster, four negative Heavy Storm activations, four Sakuretsu
Armor activations under face-up Royal Decree, and six other isolated cases.
The original feature-v25 resource head would choose a different action on
eight of the 10 Nobleman and all four Storm snapshots. These are fixed-state,
off-policy choices, not corrected duel outcomes. A new audit category now
flags Solemn Judgment on a publicly pending opposing Sinister Serpent Summon;
among 62 such response prompts in this batch, Solemn was selected zero times.
The flag remains a human-review prompt, never an automatic play label.

A second v25 head used 48 complete parent-policy replays: the original 32
Jesse/Warrior and Return/Flip games plus eight WikiFormat Dimension Fusion
mirror games and eight Chaos Turbo/Matt Peddle games. All **20,786** source
decisions replay-verified and passed the visibility audit. The corrected
Tactical synthetic teacher supplied **207** Heavy Storm/Nobleman activation
labels, including 140 disagreements. Only the zero-initialized two-weight
trade head was trained; every other parent parameter stayed frozen. The head
weights became 2.491 and 2.898, versus 2.057 and 2.486 in the original v25
fit. On the same 64 saved parent states it changed nine of 10 flagged
Nobleman choices and all four negative Storm choices. The ignored checkpoint
is `.cache/goat-ai/fv25_trade_diverse_10400_13100_13300.pt` (SHA-256
`e5b6705673853ec1ced872b135fb4c5fa5e14e2a76c7e6398d570b6da170502c`).

Three Main Deck pairings excluded from both the parent and new head's
training compositions—Chaos Control/Bazoo Return, Lolmarcus/Michael Goat
Control, and GoatFormat Dimension Fusion/Phoenix Control—were evaluated with
both deck assignments and both policy seats on seeds 18300–18307. Over **96
direct held-out duels**, the new head scored **51–43–2** against its unchanged
v23 parent (54.2%, paired 95% interval 47.4%–60.4%) and **52–44** against
the original v25 head (54.2%, interval 50.0%–59.4%). Against Tactical-v14 it
scored **21–75**, while the v23 parent scored **20–76** on the matched schedule.
The paired Tactical score difference was +1.0 percentage point, interval
−4.2 to +6.2 points. More diverse resource examples improved one additional
recorded Nobleman choice, but did not establish a held-out competitive gain.
Keep v23 as the neural reference and both v25 heads experimental. A stronger
signal must address the other visible mistakes as well as win outcomes.

The direct and Tactical report SHA-256 values are, respectively,
`78c8088dbd0cb2fcd0ec54bbfa987bc3c96490345c70fe0b986335ccafa6d6da`,
`c688b15145367a7853f498e8f4251a111330203a651bd60c0e40fdb41ccbad5b`,
`b8765661982a7885d5d483ab2df7058e44fa82a4255b4f39c349f54bd358a206`,
and `8e1228f0c2a8e7a5d1d45fdab9dfff1bc6a15e9e142037604e823ff37dd21374`
under `.cache/goat-ai/` with the `fv25_trade_diverse_vs_parent`,
`fv25_trade_diverse_vs_v25_original`, `fv25_trade_diverse_vs_tactical`, and
`fv23_parent_vs_tactical` prefixes. The comparison tool verified matching
native, source, deck, and seed controls and unchanged local deck hashes.

Reproduce training from the three ignored source-replay directories:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/on_policy_teacher_10400_10407/*.json \
  .cache/goat-ai/on_policy_wikiformat_df_13100_13103/matchup_*.json \
  .cache/goat-ai/on_policy_chaos_turbo_matt_13300_13303/matchup_*.json \
  --engine experimental --on-policy-teacher tactical_card_advantage \
  --on-policy-teacher-activation-focus-only \
  --focus-card 504700116 --focus-card 19613556 \
  --feature-version 25 --width 32 --epochs 30 --batch-size 16 \
  --learning-rate 0.01 --seed 47 --trainable-module trade_head \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --upgrade-feature-23-to-25 --verification-workers 4 \
  --output .cache/goat-ai/fv25_trade_diverse_10400_13100_13300.pt
```

For a matched evaluation, use `scripts/evaluate_policy.py` with the three
pairings named above, `--engine experimental --both-deck-assignments
--seed 18300 --seeds 8 --max-decisions 3000 --require-unseen-main-decks
--workers 4`. Set the candidate checkpoint to the new v25 file and use
either `--opponent-checkpoint` for the v23 or original v25 file, or
`--opponent tactical`; then repeat the Tactical arm with the unchanged v23
candidate. Give each run its own ignored `--output` path.

### Batched visible-state critic fitting (27 October 2026)

The optional self-play `state_value` baseline previously encoded, forwarded,
and backpropagated each learner decision separately. The v1 and v2 critics now
pad visible card and Deck sequences, compute a batch of values, and fit in
minibatches of 32. A regression test compares batched and scalar predictions,
losses, and parameter updates for both architectures on variable-length
player-visible states. The critic still receives only encoded observations;
the objective remains terminal duel outcome.

On 75 learner decisions from saved self-play seed 6000, four AB/BA CPU-process
time rounds measured scalar fitting at **0.142–0.151 seconds** and batched
fitting at **0.036–0.038 seconds** (3.83–4.03× faster for this critic update).
The maximum absolute parameter difference was `1.20e-7`; the loss difference
was `4.49e-8`. This is a critic-update microbenchmark, not a whole-duel or
end-to-end training speedup. It does not establish stronger play. Reproduce:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/benchmark_critic_batch.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  .cache/goat-ai/fv23_selfplay_mean_6000_6007_replays/episode_00000_seed_6000.json \
  --limit 128 --rounds 4
```

The input checkpoint and trajectory SHA-256 values were
`9af25af5348eb9c857596aafca617afe6dce222d247de84da630b2b5f2f2d56c`
and `c3d4bfcf8ad7a994e3edcc3cb38b29823c70c10e61a3a1e0ed511e9ed4bc5c71`.
The run used PyTorch 2.5.1+cpu with one thread and the feature-v23 policy;
the reported project commit was the pre-change parent `08841fc` because this
measurement preceded the implementation commit.

### Broader Tactical-v14 imitation continuation (27 October 2026)

Starting from the unchanged feature-v23 neural reference
(`fv23_tactical_v14_unseen_fourdeck_continuation.pt`), two fresh native
matchups supplied **64 complete Tactical-v14 demonstrations**: Chaos Control
versus Bazoo Return with Tactical on both seats (seeds 18500–18515), and
Lolmarcus versus Michael Goat Control with Tactical against Combat v3 (seeds
18516–18531). The teacher occupied each seat 32 times. All **46,154 source
decisions** replay-verified and passed the player-visible audit during fitting;
the teacher supplied **23,566** selected decisions. The four new Main Deck
compositions were absent from the parent training set. A two-epoch,
batched-forward continuation with width 32, minibatch 16, learning rate
`0.0002`, seed 55, and four verification workers reduced source imitation
loss from `0.156409` to `0.131609`. The reported run took 71.87 wall seconds,
including 15.90 seconds of verification and 35.13 seconds of fitting. The
ignored child checkpoint is
`.cache/goat-ai/fv23_tactical_v14_broader_18500_18531.pt` (SHA-256
`1f42d70451521afa210d97f322d53d37eb139c62f6269dafc34c7794f971994f`).

Two held-out matchups paired Roberto Martinez Phoenix Control with either the
WikiFormat or GoatFormat Guide Dimension Fusion Main Deck. None of these
three compositions appeared in either checkpoint's training provenance. On
seeds 18600–18607, both deck assignments and both policy seats, the child
beat the unchanged parent **43–21** over 64 duels (67.2% score; paired
bootstrap 95% interval **56.2%–78.1%**). By assigned Main Deck its record was
21–11 Phoenix, 14–2 GoatFormat Dimension Fusion, and 8–8 WikiFormat
Dimension Fusion. This establishes an improvement over this neural parent on
the tested held-out schedule, with uneven deck results.

Against Tactical-v14 on matched seeds 18608–18615, the child scored **25–39**
and the parent **13–51**, each over 64 duels. The paired score difference was
**+18.75 percentage points** (95% interval **+7.8 to +31.3 points**). The child
still loses to Tactical-v14 overall. Its assigned-deck results were 14–18
Phoenix, 4–12 GoatFormat Dimension Fusion, and 7–9 WikiFormat Dimension
Fusion. This is a measured imitation gain, not a self-play improvement or a
superhuman-strength claim. M4 remains open.

The direct, child-versus-Tactical, and parent-versus-Tactical reports are in
`.cache/goat-ai/` with prefixes
`fv23_tactical_v14_broader_vs_parent_18600_18607`,
`fv23_tactical_v14_broader_vs_tactical_18608_18615`, and
`fv23_parent_vs_tactical_18608_18615`; their SHA-256 values are
`d88771821f2c9173d92a6216c15fa42a842c70741b190733a95d3d3776634682`,
`51956e035b4e13bf822bc2ac254ace776b967041140a8de192c30a31862b0bab`,
and `c385146cceb3202852c78d754bab208c3e7b6032cbee6f5535527c8a7d0cb255`.
`scripts/compare_tournament_reports.py --verify-local-decks` confirmed the
matched Tactical controls and the paired difference. The source and training
commands are:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher tactical --opponent tactical \
  --deck-a examples/decks/chaos_control_insids_worlds_2022.ydk \
  --deck-b examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --seed 18500 --seeds 16 --max-decisions 3000 \
  --output-dir .cache/goat-ai/tactical_v14_chaos_bazoo_18500_18515
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher tactical --opponent combat_heuristic \
  --deck-a examples/decks/goat_control_lolmarcus_2020.ydk \
  --deck-b examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --seed 18516 --seeds 16 --max-decisions 3000 \
  --output-dir .cache/goat-ai/tactical_v14_lolmarcus_michael_18516_18531
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/tactical_v14_chaos_bazoo_18500_18515/seed_*.json \
  .cache/goat-ai/tactical_v14_lolmarcus_michael_18516_18531/seed_*.json \
  --engine experimental --feature-version 23 --width 32 --epochs 2 \
  --batch-size 16 --batched-forward --verification-workers 4 \
  --learning-rate 0.0002 --seed 55 \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/fv23_tactical_v14_broader_18500_18531.pt
```

Use `scripts/evaluate_policy.py` with the two held-out `--matchup` pairs above,
`--engine experimental --both-deck-assignments --require-unseen-main-decks
--seeds 8 --max-decisions 3000 --workers 4`. Use `--seed 18600` with
`--opponent-checkpoint` pointing to the unchanged parent for the direct arm;
use `--seed 18608 --opponent tactical` once per checkpoint for the matched
baseline arms. Give each run a distinct ignored `--output` path.

### Self-play continuation of the broader imitation child

The stronger imitation child above was continued through **64 terminal native
self-play duels**, seeds 18700–18763, on its two training pairings. The
four-role schedule gave the learner each Main Deck in both seats. Four frozen
policy duels were collected per PPO update with four CPU workers, three PPO
epochs, minibatch 16, clip epsilon 0.2, per-episode weighting, learning rate
`0.0001`, parent KL weight 0.5, and a learner-deck moving baseline. The run
recorded **7,912 multi-option learner decisions** in 61.16 wall seconds,
with 40 wins, 23 losses, and one draw against its changing training-opponent
mixture. Those training wins do not establish improvement.

All **64 saved trajectories and 43,820 decisions** subsequently passed fresh
native replay verification and the player-visible audit. The conservative
review shortlist found 101 candidate mistakes across sampled actions,
including 23 Nobleman activations with only a friendly Set monster, 14
negative or own-only Heavy Storm activations, and 10 weak Flip-monster Normal
Summons with Set available. These are review prompts, not automatically
validated tactical labels; stochastic training choices are not the greedy
checkpoint's choices.

On fresh seeds 18800–18807 across the same two held-out Phoenix/Dimension
Fusion pairings as above, both deck assignments and both seats, the PPO child
scored **27–37** directly against its unchanged imitation parent (42.2%;
paired bootstrap 95% interval 32.8%–53.1%). By assigned Main Deck it scored
16–16 Phoenix, 6–10 GoatFormat Dimension Fusion, and 5–11 WikiFormat
Dimension Fusion. This continuation fails the M4 self-play improvement gate;
keep the imitation checkpoint as the neural reference. A future update needs
better action-level credit assignment or stronger sampled-action quality,
measured on fresh decks and seeds rather than training wins.

The ignored PPO checkpoint is
`.cache/goat-ai/fv23_broader_ppo_18700_18763.pt` (SHA-256
`58cef491e6f1e508498b186c13d5ac61354fe057a7207787e2f50cb9eb31e3b8`).
The training, held-out tournament, and replay-audit report SHA-256 values
are respectively
`e60bd85e8b8023e2a45d593fdf3db7ea9e8a1e8a4e38a0f645f141eb17cba9e2`,
`e99c7dfe8b6479e77813488ddd59fcdd5e4a7735fbc18e2de4b283f6596de71f`,
and `82eb98fab722c59fd003ee00d55787151cb6d54e126cd0667c5d4247c5dd7ca6`.
Reproduce the training with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_broader_18500_18531.pt \
  --engine experimental \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
            examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --schedule-mode four_roles --seed 18700 --games 64 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 --rollout-workers 4 \
  --ppo-rollout-weighting per_episode --ppo-epochs 3 --ppo-batch-size 16 \
  --ppo-clip-epsilon 0.2 --learning-rate 0.0001 --parent-kl-weight 0.5 \
  --baseline-scope learner_deck --snapshot-every 4 --max-snapshots 8 \
  --record-dir .cache/goat-ai/fv23_broader_ppo_18700_18763_replays \
  --output .cache/goat-ai/fv23_broader_ppo_18700_18763.pt
```

The held-out comparison used `scripts/evaluate_policy.py` with the two
Phoenix/Dimension Fusion `--matchup` pairs above,
`--engine experimental --both-deck-assignments --require-unseen-main-decks
--seed 18800 --seeds 8 --max-decisions 3000 --workers 4`, and
`--opponent-checkpoint` pointing to the unchanged imitation parent. The
replay audit used `scripts/audit_selfplay_replays.py` on all
`episode_*.json` files in the recorded directory.

### Fixed-policy Tactical labels on visited states

The PPO continuation above used a changing policy, so its saved decisions do
not satisfy the fixed-checkpoint attribution required by the on-policy
teacher-labeling path. Instead, the unchanged broader imitation checkpoint
played Tactical-v14 on the two training pairings, seeds 18900–18915, with
both policy seats. The collector recorded **64 complete games and 42,060
replay-verified, visibility-audited decisions**. Its manifest SHA-256 is
`8fdad424254613de6e72b615b08dd4ed37dc2897af4c1cd78bfb81de9d914535`.
The teacher labeled **7,538** multi-option policy-seat decisions and disagreed
with the recorded choice on **1,891**. These are synthetic Tactical labels on
the policy's visited states, not human reviews or counterfactual outcomes.

Starting from the same unchanged imitation checkpoint, a two-epoch,
feature-v23, width-32 continuation used learning rate `0.0001`, minibatch 16,
batched forward, disagreement sampling weight 4, seed 57, and four native
verification workers. The source losses were `0.867216` and `0.651083`.
The ignored checkpoint is `.cache/goat-ai/fv23_broader_teacher_18900_18915.pt`
(SHA-256 `d48cd9815cfcb6983f02b5123ffc80163639c85948b020f86f0650487168ac60`).

On held-out Phoenix/Dimension Fusion pairings, seeds 19000–19007 with both
deck assignments and seats, the labeled child scored **30–34** against its
unchanged parent (46.9%; paired 95% interval **39.1%–56.3%**). Its
assigned-deck records were 18–14 Phoenix, 8–8 GoatFormat Dimension Fusion,
and 4–12 WikiFormat Dimension Fusion. Against Tactical-v14 on matched seeds
19008–19015, the child scored **16–47–1** while the parent scored **20–44**.
The paired score difference was −5.47 points, with a 95% interval of
−19.53 to +8.59 points. More teacher agreement on the source states did not
produce a held-out gain in this experiment; retain the broader imitation
checkpoint as the neural reference.

The training, direct, child-versus-Tactical, and parent-versus-Tactical
report SHA-256 values are respectively
`4b5e68542adb1d6dbd5e6b16edfe7d2baea8656e1eca046d4cb05f3ff950a337`,
`3ea44d663cec10d44fcf091ddbe17b5a9c5aa644be9533ca714636724e930681`,
`6f2f502908bae8dd3bbc3ad3a5f3a7846fc97fea09f9d131257e0c7735219fe3`,
and `3d611c71199c92700c274a1d1107bf77fec5c4be561245596ec2f23ec74a4b35`.
The matched report comparator verified the Tactical controls and local deck
bytes. To reproduce the fixed-policy source and fit:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_tactical_v14_broader_18500_18531.pt \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
            examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --opponent tactical --seed 18900 --seeds 16 --workers 4 \
  --max-decisions 3000 \
  --output-dir .cache/goat-ai/fv23_broader_vs_tactical_teacher_18900_18915
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/fv23_broader_vs_tactical_teacher_18900_18915/matchup_*.json \
  --engine experimental --on-policy-teacher tactical_v14 \
  --on-policy-disagreement-weight 4 --feature-version 23 --width 32 \
  --epochs 2 --batch-size 16 --batched-forward --verification-workers 4 \
  --learning-rate 0.0001 --seed 57 \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_broader_18500_18531.pt \
  --output .cache/goat-ai/fv23_broader_teacher_18900_18915.pt
```

The evaluation used the same two held-out `--matchup` pairs, engine, deck
assignment, unseen-composition gate, decision cap, and workers as the prior
experiment, with `--seed 19000 --seeds 8` for the direct arm and
`--seed 19008 --seeds 8 --opponent tactical` for both matched baseline arms.

### Further distinct-deck native protocol sweeps

A fresh full-whitelist sweep used independent legal 40-card Main Decks for
both players on seeds 10356–10455. RandomAgent completed **100/100** duels
within a 3,000-decision cap; the longest took 1,655 decisions. All **109,551**
decisions replay-verified and passed the player-visible audit, including
1,021 hidden-field and 93 opponent-hand choices. The games loaded 1,306
distinct native assets and offered 5,360 source-card/action-kind pairs.
Relative to the union of the local reports for whitelist seeds 10274–10323,
whitelist seeds 10324–10355, and tournament-mix seeds 30000–30049, this run
loaded **22 previously unobserved script assets**. The ignored report is
`.cache/goat-ai/whitelist_distinct_10356_10455/report.json` (SHA-256
`71557cfa080c21dc1850355fff6be6c34b98956b4aab34853c5d79db941b9515`).

A second sweep mixed cards from six sourced tournament Main Decks, using
distinct legal opponent decks on seeds 30050–30149. RandomAgent completed
**100/100** duels; the longest took 1,461 decisions. All **94,921** decisions
replay-verified and passed visibility checks, including 1,162 hidden-field
and 557 opponent-hand choices. It selected 115 distinct chain-response/source
pairs, **68** absent from the earlier tournament-mix seeds 30000–30049.
The run loaded no script asset absent from that earlier mix. The ignored
report is `.cache/goat-ai/tournament_mix_distinct_30050_30149/report.json`
(SHA-256 `422f3fe4f33918acd253c149ad7573f0de0bb100926fb5e2a7b6230bf3076e79`).

These are sampled native protocol and information-boundary checks. The decks
are randomly assembled, and random decisions do not validate historical
card rulings or competitive strength. Reproduce after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/whitelist_distinct_10356_10455 \
  --seed 10356 --seeds 100 --max-decisions 3000 \
  --verify-replays --distinct-opponents --count-card-actions
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/tournament_mix_distinct_30050_30149 \
  --seed 30050 --seeds 100 --max-decisions 3000 --card-pool tournament \
  --verify-replays --distinct-opponents --count-card-actions
```

### Optional forced-choice filtering for cloning (27 October 2026)

`train_behavioral_clone.py --skip-forced-training` now removes decisions with
only one legal action from the optimizer input, after the full native replay
and visibility checks. Such decisions have zero choice cross-entropy. They
remain counted in the verified replay and checkpoint provenance; the new
`fit_decisions` field reports the actual optimizer input. The flag is limited
to behavioral cloning. It is opt-in because removing records changes batch
composition, update count, sampling distribution, and learned weights.

One recorded policy-versus-Tactical duel, seed 10400, supplied **562** labeled
decisions, including **351 forced** and **211 multi-option** choices. With
feature v23, width 32, two epochs, batch size 16, batched forward, and one
Torch thread, AB then BA full-command runs measured these process-internal
times (seconds):

| Order | All 562: fit / total | Filtered 211: fit / total |
| --- | ---: | ---: |
| AB | 1.357 / 2.958 | 0.880 / 2.545 |
| BA | 1.338 / 2.904 | 0.901 / 2.510 |

The fit step was **1.48–1.54× faster**; total command time was **1.14–1.16×
faster** because replay verification still took roughly 1.05–1.12 seconds.
Each mode produced identical model tensors on its two runs. The modes did
**not** produce identical weights, and their mean losses have different
denominators. This is a one-replay training-speed measurement, not evidence of
playing-strength improvement. A cross-deck held-out tournament is required
before using a filtered child as a stronger checkpoint.

To reproduce, run the same command twice, once with and once without
`--skip-forced-training`, using different ignored output paths:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/on_policy_teacher_10400_10407/jesse_warrior_10400_seat0.json \
  --engine experimental --feature-version 23 --width 32 --epochs 2 \
  --batch-size 16 --batched-forward --learning-rate 0.0002 --seed 82 \
  --output .cache/goat-ai/forced_filter_example.pt
```

### Filtered cloning continuation and held-out strength (27 October 2026)

The speed option was also applied to the existing 32 replay-verified
Tactical-v14 demonstrations on Chaos Control/Bazoo Return and
Lolmarcus/Michael Goat Control, starting from the same v23 parent as the
unfiltered broader imitation child. The matched settings were width 32,
two epochs, batch 16, batched forward, learning rate 0.0002, and seed 55.
**8,270 of 23,566** labeled decisions had more than one legal action.
The filtered run took **13.51 s** to fit and **50.89 s** for the full command;
the current-code unfiltered run took **35.66 s** and **72.99 s**. Both runs
verified all source replays. Thus fitting was **2.64× faster** and the full
command **1.43× faster** in this matched workload. A rerun of the unfiltered
command produced tensors identical to the original broader checkpoint.

On two unseen Phoenix Control/Dimension Fusion pairings, both deck
assignments and seats, seeds 19116–19123, the filtered child scored
**32–32** directly against the unfiltered child (paired 95% score interval
**39.1%–59.4%**). On matched seeds 19124–19131 versus Tactical-v14, the
filtered child scored **16–48** and the unfiltered child **21–43**. The
paired score difference was **−7.81 percentage points**, with a 95% interval
of **−20.31 to +4.69 points**. There is no demonstrated strength gain; the
unfiltered broader checkpoint remains the neural reference. The filtered
checkpoint is an experimental speed/learning-schedule variant, not a
promoted policy. Its SHA-256 is
`500b8ab02d577e7cd570f8d6f301b01d4636f12c08d49d0c57b64fdd29129111`.

The ignored training summaries are
`.cache/goat-ai/fv23_tactical_v14_broader_skip_forced_18500_18531.stdout.json`
(SHA-256 `aa6ca76ad6633edd37184a43f0736676ee034149e0b1ec142783e3341a346206`)
and `.cache/goat-ai/fv23_tactical_v14_broader_unfiltered_matched_18500_18531.stdout.json`
(`d11be67ace0db5bb1f9d7c2dbecc401d1102c40073b84f5438636a63e89281a1`).
The direct, filtered-versus-Tactical, and unfiltered-versus-Tactical reports
have SHA-256 values `f85d8c8dcacae2caba5b594ece9ac2cd60184e31a5d77a8386831d38bb7628f3`,
`a65f9fa3e5fb926a98fc62e7d494f5a40e4d75a779496353f9b97cf5733175ce`,
and `6cce3dac837f3a859b76efd396b2e6f7102c66e0b6c595043ae76ccc46169835`.
The report comparator verified the Tactical controls and local deck bytes.

An additional *uncommitted* Tactical-v14 candidate deferred Setting ordinary
Spells while a phase transition was available, but allowed Quick-Play Spells,
Traps, and a seven-card hand. Four sampled Tactical replays offered the
condition at 68 decisions and selected such a Set at 13. On two fresh
64-game, seat- and deck-swapped schedules, the candidate scored **32–32**
(Phoenix/Dimension Fusion) and **30–34** (Matt/Chaos and Jesse/Flip)
against Tactical-v14. This did not establish a competitive gain, so the
candidate code was discarded and the baseline/teacher version remains 14.
The ignored local reports have SHA-256 values
`3aa82048e2b5ee8633dc8f9ce6e85d3d6bba25bc3ec44a26296513223779a82d`
and `6900d91dcee93a168dabf62d5a2a4f63059f80cb84b51ce1dfc57297a0f102b1`.

### Preserving cloning batches while omitting forced forwards (27 October 2026)

`train_behavioral_clone.py --omit-forced-forward` keeps every replay label in
the original epoch shuffle or weighted sample, minibatch, loss denominator,
and Adam update. It omits one-legal-action examples from *mixed* batched
network forwards. An entirely forced minibatch still runs the ordinary
forward so that its optimizer step is preserved. The flag requires
`--batched-forward` and cannot be combined with `--skip-forced-training` or
parent-KL fitting. Full native replay verification and visibility auditing
still precede fitting. This changes batched floating-point order, so it does
not promise byte-identical weights.

On the same 32 Tactical-v14 replays and settings as the previous section,
the original and optimized paths both consumed **23,566 labels** in the same
optimizer schedule. The separate full-command runs measured **35.66 versus
24.84 seconds** fitting (**1.44×**) and **72.99 versus 62.43 seconds** total
(**1.17×**). Epoch losses differed by at most `1.9e-8`, and the largest
absolute final parameter difference was `0.00227`. These are CPU
measurements with one Torch thread, not a general throughput guarantee.

On fresh unseen Phoenix/Dimension Fusion pairings, both deck assignments and
seats, seeds 19132–19139, the optimized child scored **32–32** directly
against the original; the paired score interval was exactly **50%–50%**
on that schedule. On matched seeds 19140–19147 versus Tactical-v14, **both
children scored 20–43–1**. The report comparator found a paired score
difference of zero with a zero-width interval on this schedule. The evidence
supports a training-speed setting with no observed outcome difference here;
it does not establish a stronger policy or equivalence on other decks.
The original broader checkpoint remains the neural reference.

The optimized checkpoint SHA-256 is
`fd9016ef0f51f82a16172c946271d896411cdc1fbbe68edaafcc1091e8883bf0`.
The ignored training summary SHA-256 is
`0d04de37c3655a8e26ec8d87e91b069e84cab08bfce711c05eaf931f35bd307b`.
The direct, optimized-versus-Tactical, and original-versus-Tactical report
hashes are `1e601a57863fbfd43bc49e7e0d9e06e90e40759a964444e98f242cec9a51b29e`,
`2473cd621abbe936ed7293f9cee92287f0975437fcb9f1554d7eaa5e8d352aa6`,
and `b5625d8229a86a6e41c207d12e5f20a760c618711f4c7739829901ab81ca52f1`.

Reproduce the optimized training after native setup with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/tactical_v14_chaos_bazoo_18500_18515/seed_*.json \
  .cache/goat-ai/tactical_v14_lolmarcus_michael_18516_18531/seed_*.json \
  --engine experimental --feature-version 23 --width 32 --epochs 2 \
  --batch-size 16 --batched-forward --omit-forced-forward \
  --verification-workers 4 --learning-rate 0.0002 --seed 55 \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/fv23_tactical_v14_broader_omit_forward_18500_18531.pt
```

### Re-recording and retraining after the GOAT SEGOC core patch (27 October 2026)

The [GOAT-only native trigger-order patch](native_setup.md) changes the
`libocgcore.so` SHA-256 to
`df1774ae5d2f23e52ec2290bcd23e20713d908404539dfffc8f34e1c853e9a00`.
An older Tactical-v14 trajectory failed exact verification with `ReplayMismatch:
native assets differ from recorded trajectory: build/libocgcore.so`. This is
the expected provenance gate; old observations and actions were not silently
relabeled as if produced by the patched core.

Fresh Tactical-v14 demonstrations used Chaos Control versus Bazoo Return,
seeds 21000–21003, with Tactical on both seats; and Lolmarcus versus Michael
Goat Control, seeds 21004–21007, with Tactical against Combat v3. The
collector wrote **16 complete seat-swapped duels and 9,327 source decisions**.
Training replay-verified and visibility-audited all 16, then fit the 4,761
Tactical-seat decisions for two epochs from the unchanged feature-v23
reference. The `--omit-forced-forward` option kept the full optimizer schedule.
Measured wall time was **13.20 s**, including 4.18 s replay verification and
5.20 s fitting with four verification workers and one Torch thread. The
checkpoint is
`.cache/goat-ai/fv23_patched_core_continuation_21000_21007.pt` (SHA-256
`55831b93ed2c3599629708b2f24edd276557ced913dfd174f2a7e4d236177c20`).
The SHA-256 of the sorted `relative_path + space + file_sha256 + newline`
manifest for the 16 ignored trajectories is
`215dbb127285235bc1b71e53fea2eabc1313f1f975ff63f9e3144fc2c6f47404`.
All source decks are tracked under `examples/decks/`; no replay or checkpoint
was added to Git.

On **64 direct held-out duels** across both assignments and policy seats for
Roberto Martinez Phoenix Control versus the GoatFormat and WikiFormat
Dimension Fusion decks, seeds 21100–21107, the child scored **32–31–1**
against its parent. Its 50.8% score had a paired-bootstrap 95% interval of
39.1%–62.5%. The GoatFormat pair was 17–15; the WikiFormat pair was 15–16–1.
On separate matched seeds 21108–21115 versus Tactical-v14, the child scored
**18–46** and the parent **17–47** over 64 duels each. The paired score
difference was +1.6 percentage points with a 95% interval of **−10.9 to
+12.5 points**. The report comparator verified both pairs' native asset,
script, source-code, seed, opponent, and local deck controls. This sample does
not establish a policy-strength improvement; the unchanged parent remains the
neural reference, and the M4 self-play gain gate remains open. The child also
inherits pre-patch weights, so its full training lineage is not wholly
patched-core data.

The ignored direct reports are
`patched_core_child_vs_parent_phoenix_{goat,wiki}_df_21100_21107.json`, and
the four Tactical reports are
`patched_core_{child,parent}_vs_tactical_phoenix_{goat,wiki}_df_21108_21115.json`,
all under `.cache/goat-ai/`. Their checkpoint, replay-manifest, and report
hashes are recorded above or in the files. Reproduce the source and fit with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher tactical --opponent tactical \
  --deck-a examples/decks/chaos_control_insids_worlds_2022.ydk \
  --deck-b examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --seed 21000 --seeds 4 --max-decisions 3000 \
  --output-dir .cache/goat-ai/patched_core_tactical_chaos_bazoo_21000_21003
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_heuristic_demos.py \
  --engine experimental --teacher tactical --opponent combat_heuristic \
  --deck-a examples/decks/goat_control_lolmarcus_2020.ydk \
  --deck-b examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --seed 21004 --seeds 4 --max-decisions 3000 \
  --output-dir .cache/goat-ai/patched_core_tactical_lolmarcus_michael_21004_21007
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/patched_core_tactical_chaos_bazoo_21000_21003/seed_*.json \
  .cache/goat-ai/patched_core_tactical_lolmarcus_michael_21004_21007/seed_*.json \
  --engine experimental --feature-version 23 --width 32 --epochs 2 \
  --batch-size 16 --batched-forward --omit-forced-forward \
  --verification-workers 4 --learning-rate 0.0002 --seed 55 \
  --init-checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/fv23_patched_core_continuation_21000_21007.pt
```

For the direct evaluations, use `scripts/evaluate_policy.py` with
`--opponent-checkpoint` pointing to the parent; for both Tactical controls,
use `--opponent tactical`. In each arm use `--engine experimental
--both-deck-assignments --require-unseen-main-decks --workers 4
--max-decisions 3000 --seeds 8`, the named Phoenix/Dimension Fusion `--matchup`,
and the seed ranges above. Save each report under a distinct path. Run
`scripts/compare_tournament_reports.py --verify-local-decks` on each matched
child/parent Tactical pair before computing a combined paired difference.

### Patched-core PPO continuation and held-out check (27 October 2026)

The unchanged feature-v23 neural reference was continued on the patched GOAT
core with four-role, four-worker PPO self-play across Chaos Control/Bazoo
Return and the two Goat Control training decks. Seeds 21200–21231 produced
**32/32 terminal duels**, with **5,425 learner decisions**, no censored or
unsupported games, and a measured training wall time of **36.66 s** with one
Torch thread. The saved replay audit verified all 32 full trajectories and
listed 69 review candidates. The ignored checkpoint
`.cache/goat-ai/fv23_patched_core_ppo_21200_21231.pt` has SHA-256
`506d87a478fe17dc936d3cb3acd393be183a19587e2272b8c491adb08d40ba78`;
its replay-audit report has SHA-256
`4fb133fc3c0f8788e19b750948e4fdd27167ddb0660469f060f65005f1a42b6b`.

On fresh Phoenix Control versus GoatFormat and WikiFormat Dimension Fusion
decks, seeds 21300–21307 with both deck assignments and policy seats, the PPO
child scored **33–31** directly against its unchanged parent over 64 duels.
The paired-bootstrap 95% interval for its 51.6% score was **40.6%–64.1%**.
The split was **13–19** on the GoatFormat pair and **20–12** on the WikiFormat
pair. The direct report SHA-256 values were
`62c14d2835e2af71eb92dff870599a1a91a806d11cf810c1ae51fa37c1e886c2`
and `0674011f809b3d72b44c71f9897db60ffb5a33cb0ceb336a1539653d979e6953`.

Against Tactical-v14 on the matched but separate 21308–21315 schedule, the
child scored **12–52** and the parent **18–46** over 64 duels each. The paired
score difference was **−9.4 percentage points**, 95% interval **−21.9 to
+3.1 points**. The report comparator verified native assets, script and
source fingerprints, seed/opponent settings, and current local deck hashes for
each pair. The four ignored Tactical report SHA-256 values, in child Goat,
parent Goat, child Wiki, parent Wiki order, were
`c4736470bd25f57c4101f4dfc3a462caa3588611feae4391a0dc5dedca583caf`,
`00698ce1b7842b7960d5f16164dc957f1744aaae4372f5b29aff3ae0d3d16ad3`,
`ca2790704fa6c8625c8efd705247f3fda8cb10bd1f8b6522f637ff6854afe6a6`,
and `a13be52808deabbcac8edde181821cb176d6a62314197ad59e77e4ef50c8ecbf`.
This run does not establish a self-play strength gain. The unchanged parent
remains the reference; the child is an ignored experimental checkpoint.

Reproduce the self-play with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --engine experimental \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
            examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --schedule-mode four_roles --seed 21200 --games 32 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 --rollout-workers 4 \
  --ppo-rollout-weighting per_episode --ppo-epochs 3 --ppo-batch-size 16 \
  --ppo-clip-epsilon 0.2 --learning-rate 0.0001 --parent-kl-weight 0.5 \
  --baseline-scope learner_deck --snapshot-every 4 --max-snapshots 8 \
  --record-dir .cache/goat-ai/fv23_patched_core_ppo_21200_21231_replays \
  --output .cache/goat-ai/fv23_patched_core_ppo_21200_21231.pt
```

The direct arm used `scripts/evaluate_policy.py --opponent-checkpoint` with
the unchanged parent; the Tactical arms used `--opponent tactical` for each
checkpoint. All used `--engine experimental --both-deck-assignments
--require-unseen-main-decks --seeds 8 --max-decisions 3000 --workers 4` and
the Phoenix/Dimension Fusion pair named above. Set `--seed 21300` for the
direct arm and `--seed 21308` for the Tactical arms. Run
`scripts/audit_selfplay_replays.py` on the 32 recorded `episode_*.json` files.

### Lower-temperature PPO rollout diagnostic (27 October 2026)

The patched-core PPO schedule above was rerun from the same parent checkpoint,
training decks, seeds 21200–21231, four-role assignments, and update settings,
changing only learner sampling temperature from 1.0 to 0.5. The reference
finished all 32 games below its 3,000-decision cap. The 0.5 run recorded the
first eight complete games, then seed **21211** exceeded 3,000 decisions.
Raising only that run's decision cap to **10,000** still left the same seed
unfinished. These attempts produced no final checkpoint or held-out strength
comparison; lower temperature is rejected for this schedule rather than
promoted on the intuition that more confident actions are better. The
completed prefix had decision counts 2,221, 1,071, 758, 350, 764, 448,
1,506, and 2,406; those prefix files were not used for training claims.

The first failure also revealed that `EpisodeDecisionLimit` could not be
unpickled from a process worker, so the parent saw `BrokenProcessPool` instead
of the seed and limit. Its constructor arguments now survive serialization.
A spawned-process regression checks this boundary; rerunning the 3,000-decision
attempt reported `seed=21211` and the real cap. This changes error reporting,
not game outcomes. The attempted trajectories remain ignored under
`.cache/goat-ai/fv23_ppo_temp05_{capcheck,10000_21200_21231}_replays/`.

The capped seed was reproduced with one rollout worker. Its last 1,000
decisions all occurred in turn 6 Main Phase 1, alternating 500 `select_card`
and 500 `unselect_card` actions on the same card, with unchanged Life Points
and Deck counts. The ignored diagnostic summary is
`.cache/goat-ai/seed21211_cap_diagnostic.json`. This is a policy action cycle,
not a native engine hang or a slowly progressing duel.

### Selection-progress masking in sampled PPO rollouts (27 October 2026)

The greedy policy already avoids reversing a selected card while a legal
`select_card` or `finish_selection` action is available. Sampled self-play
previously bypassed that safeguard. Its learner and frozen neural opponent now
sample from the same static progress-filtered action set. The learner's PPO
decision records use that filtered set, so the update computes probabilities
under the distribution actually sampled. The saved trajectory still records
**all** native legal actions, preserving replay verification and the public
environment contract. The filter does not change native legality and allows
`unselect_card` when no forward selection or finish is offered. New checkpoints
record `selection_progress_mask: 1` in their self-play configuration.

With the otherwise same first 16 games of the lower-temperature schedule,
four process workers completed **16/16 terminal duels** under the original
3,000-decision cap. Seed 21211 now ended after **299 decisions**. The run
recorded **13,170 decisions**, **2,342** multi-option learner decisions,
and seven learner wins; all 16 complete trajectories passed fresh native
replay verification and the visibility audit. A separate batched-inference
run on the same inputs produced **16 byte-identical trajectories and identical
final model tensors**. This verifies that the two execution paths use the same
masked sampling/update semantics. The ignored checkpoints are
`.cache/goat-ai/fv23_ppo_temp05_masked_21200_21215.pt` and
`.cache/goat-ai/fv23_ppo_temp05_masked_batch_21200_21215.pt`; the replay audit
is `.cache/goat-ai/fv23_ppo_temp05_masked_21200_21215_audit.json`.
This establishes protocol progress and deterministic training behavior on a
specific schedule, **not** a held-out playing-strength improvement.

The complete 32-game masked continuation from the same parent and four-role
training schedule also terminated **32/32** times below 3,000 decisions,
recording **28,271** decisions and **5,162** multi-option learner decisions
in **34.02 seconds** of training wall time with one Torch thread. All 32
trajectories passed native replay verification and the visibility audit. Its
ignored checkpoint
`.cache/goat-ai/fv23_ppo_temp05_masked_21200_21231.pt` has SHA-256
`af3a2a139115f6e388148572aefc94811554155d6193796652500c6139ee6041`;
the replay audit is
`.cache/goat-ai/fv23_ppo_temp05_masked_21200_21231_audit.json`.

On the unseen Phoenix Control versus two Dimension Fusion matchups, both deck
assignments and seats, seeds 21300–21307 gave the child **26–35–3** directly
against its unchanged parent over 64 duels (42.97% of points; paired-bootstrap
95% interval **36.72%–50.00%**). On matched seeds 21308–21315 against
Tactical-v14, the child scored **14–50** versus the parent's **18–46**.
The report comparator verified matching opponent, seed schedule, deck hashes,
native assets, and source fingerprints; child-minus-parent paired score
difference was **−6.25 percentage points**, 95% interval **−14.06 to +1.56**.
The reports are ignored under `.cache/goat-ai/` with prefixes
`fv23_ppo_temp05_masked_vs_parent_21300_21307`,
`fv23_ppo_temp05_masked_vs_tactical_21308_21315`, and
`fv23_parent_vs_tactical_after_selection_mask_21308_21315`. The masked PPO
child is **not promoted**: avoiding a training loop did not produce a measured
competitive gain. A next self-play method needs better action valuation or
credit assignment, assessed on fresh held-out matchups.

### Automated visible-rule preference experiment (27 October 2026)

The 32 replay-verified patched-core PPO self-play duels above supplied
decision-level error candidates. `scripts/derive_visible_rule_preferences.py`
re-verified every duel and its visibility audit, then wrote **26 synthetic
preferences across 19 replays** under rule set `visible_audit_v1`: 7 Chaos
Sorcerer self-banish, 7 empty Thunder Dragon searches, 5 weak Flip Normal
Summons, 3 own-target Rings with a safe enemy option, 3 Black Luster Soldier
self-banish, and 1 Pot-before-Thunder choice. The ignored label manifest is
`.cache/goat-ai/patched_core_ppo_visible_rule_v1_21200_21231/manifest.json`,
SHA-256 `fee3f15bfe164859ec200b2b4e1bd5957f370a27ffb521c150c42f7a581636b4`.
These labels are automated, not human reviewed, and each preference only
asserts that a recorded visible legal alternative is worth trying.

A parent-KL preference fit started from the unchanged feature-v23 reference
`.cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt`. It used
100 updates at learning rate 0.0001, parent-KL weight 1.0, 26 preferences,
and 64 fresh preservation states from seeds 21000 and 21004. Preference loss
fell from 2.43848 to 0.422737; last preservation KL was 0.0275732. The
ignored child checkpoint is
`.cache/goat-ai/fv23_patched_core_visible_rule_pref_21200_21231.pt`, SHA-256
`3a7dc2955efb30ac5b9d7ff0668b22dce3b47c2cfb05a58ae3852848019f6f90`.
This fit proves only that the child learned the selected comparisons.

On untouched Phoenix Control versus GoatFormat and WikiFormat Dimension
Fusion decks, with both deck assignments and both seats, fresh seeds
21400–21415 gave the child **70–58** directly against its parent over 128
duels. Its 54.7% score had a paired-bootstrap 95% interval of **47.7%–61.7%**.
The four 32-game blocks were 18–14, 20–12, 17–15, and 15–17. Separate matched
seeds 21416–21423 against Tactical-v14 gave the child **14–50** and parent
**13–51** over 64 duels each. The paired score difference was **+1.6
percentage points**, 95% interval **−12.5 to +14.1 points**. The report
comparator verified native assets, scripts, source and local deck hashes for
both Tactical pairs. Reports are the eight ignored
`.cache/goat-ai/visible_rule_pref_*214*.json` files. All tournament arms used
`--engine experimental --both-deck-assignments --require-unseen-main-decks
--workers 4 --max-decisions 3000`. These results do not establish a
competitive improvement. The unchanged parent remains the reference.

### Distinct-opponent whitelist protocol sweep (27 October 2026)

The experimental GOAT adapter completed **20/20** newly seeded duels between
independently generated, whitelist-legal 40-card Main Decks. The 40 deck files
contained **1,036 distinct Main Deck IDs**; every opponent deck hash differed
from its paired deck hash. Seeds 30000–30019 used RandomAgent, a 3,000-decision
limit, and full native replay and player-visibility verification. All **21,078
decisions** replay-verified; game lengths ranged from 436 to 1,566 decisions.
The visibility audit counted 217 hidden-field, 1,174 opponent-field, and 18
opponent-hand choice references. There were no reported native-message errors
or censored games. The ignored report is
`.cache/goat-ai/whitelist_distinct_30000_30019/report.json`, SHA-256
`8208baa7f409fdad3141d21082e97eca567d1adaaf73339a8c6e27dccb347368`.
Reproduce it after native setup with:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/probe_random_decks.py \
  --seed 30000 --seeds 20 --max-decisions 3000 \
  --card-pool whitelist --distinct-opponents --verify-replays \
  --output .cache/goat-ai/whitelist_distinct_30000_30019
```

This is protocol coverage, not a historical correctness test for all 1,036
cards. Each generated deck has 40 distinct canonical Main Deck cards and no
Extra or Side Deck; such random lists are not competitive deck samples.

An opt-in `--repeat-seeds` reran each of those 20 games from a fresh native
environment and a newly seeded RandomAgent. The repeated trajectories had
identical player-visible decisions, selected actions, terminal observations,
and winners across **21,078 decisions**. Deck hashes, decision counts, and
outcomes also matched the earlier sweep. Replay verification and visibility
audits again passed for all 20 games. The ignored repeat report is
`.cache/goat-ai/whitelist_distinct_repeat_30000_30019/report.json`, SHA-256
`55118a331ea351fe97cf420be94d62eec1eeee49ecf6addfc95dd6c407a5b288`.
Use the command above with `--repeat-seeds` and a distinct output directory.
This tests determinism for these seeds, decks, and RandomAgent; it is not a
proof that every possible GOAT duel is deterministic or historically correct.

### Native field-summary query check (27 October 2026)

The field-summary observation path was already enabled. An AB/BA run compared
it with the full-query reference on three complete control/Chaos probe duels
per arm, seeds 12000–12002, with `RandomAgent` on both sides. Each arm made
**2,671 decisions**; both rounds had exactly matching complete trajectories,
and the benchmark replay-verified **5,342 optimized-arm decisions**. The
optimized path used **21,310** native location queries instead of **26,740**
(20.3% fewer). On the Intel Core i7-10700K, Linux 6.8.0 x86_64, with
`OMP_NUM_THREADS=1`, CPU time was **2.036 vs 1.900 seconds** in
reference-first order and
**1.923 vs 1.780 seconds** in optimized-first order: **1.072× and 1.080×**
for these duels. Peak process RSS was **123,332 KiB**. This measures a native
observation path in random play, not full neural training or a strength gain.

The ignored report is
`.cache/goat-ai/native_field_summary_20261027.json`, recorded from commit
`7743836` with a clean worktree; it includes core, deck, and source hashes.
Reproduce it after [native setup](native_setup.md) with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/benchmark_native_field_summary.py --games 3 --rounds 2 --seed 12000
```

The previously profiled neural duel spent about half its profiler-accounted
time building observations, while this narrow query reduction yielded only a
single-digit whole-duel speedup. Further observation changes should first
measure full training wall time and preserve exact trajectories and the
visibility audit. Feature encoding and replay verification are separate
candidates to profile before changing their semantics.

### Four-game self-play call profile (27 October 2026)

A single-process, four-game PPO training run from the unchanged feature-v23
reference used Jesse Goat Control versus Warrior, seeds 23000–23003, a
3,000-decision cap, one four-duel rollout, two update epochs, and minibatch
size 16. All four duels reached terminal after **2,650 decisions**; the
learner had **487** multi-option decisions. All **2,650** recorded decisions
replay-verified against the pinned native core and passed the visibility audit.
A second run with the same inputs and without `cProfile` produced four equal
loaded trajectories. Its CLI-reported wall time was **4.80 s**, versus **6.74 s**
with profiling enabled. These short-run times include startup and replay
writing and are not throughput predictions for a long training job.

The profiled run recorded **2,654** observation builds with **1.243 s**
cumulative Python profiler time, **1,360** feature encodes with **0.908 s**,
and **966** policy forwards with **1.293 s**. Four replay writes accumulated
only **0.062 s** in the same profile. These cumulative figures may overlap
their callers, omit native execution detail, and include profiling overhead;
they must not be summed into a wall-time breakdown. The next measured
optimization target is the per-decision observation/encoding/inference path,
with exact trajectory and visibility checks. Replay writing is lower priority
for this short schedule.

In a separate five-repeat microbenchmark over 370 multi-option decisions
from the first profiled duel, full feature encoding took **0.581 s** while
building only the initial Main Deck ID tensor took **0.020 s**. Caching that
duel-constant tensor has at most a small direct opportunity in this measured
encoder workload; its actual whole-training benefit was not tested.

The ignored profiler data, CLI report, and matching control report are
`.cache/goat-ai/full_train_profile_23000.pstats`,
`.cache/goat-ai/full_train_profile_23000.json`, and
`.cache/goat-ai/full_train_profile_23000_control.json`. Reproduce the
profiled arm after [native setup](native_setup.md) with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python -m cProfile \
  -o .cache/goat-ai/full_train_profile_23000.pstats \
  scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --seed 23000 --games 4 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 \
  --ppo-epochs 2 --ppo-batch-size 16 --snapshot-every 4 \
  --output .cache/goat-ai/full_train_profile_23000.pt
```

Use a distinct output and replay directory for each repeat. This profile is
diagnostic only; the four-game outcomes do not establish policy strength.

### PPO rollout feature-reuse check (27 October 2026)

The opt-in `--reuse-rollout-features` retains each learner feature tensor from
sampling and passes it to the PPO update, avoiding a second feature encode.
We compared that path with the ordinary re-encode path on eight Jesse Goat
Control versus Warrior duels, seeds 26000–26007, from the unchanged feature-v23
reference. Both used one process, two four-duel PPO rollouts, two update epochs,
minibatch 16, a 3,000-decision cap, and `OMP_NUM_THREADS=1`. The execution
order was ordinary, reuse, reuse, ordinary. CLI-reported wall times were
**7.318 and 7.202 seconds** for ordinary encoding and **7.166 and 7.214
seconds** for reuse. This small difference is within the variation of these
short runs; it does not establish a useful training-speed gain.

Every arm completed the same eight terminal games with **4,848 total decisions**
and **833 multi-option learner decisions**. All corresponding trajectory JSON
files were byte-identical across arms, and all final model tensors were
bit-identical. One eight-game arm passed full native replay verification and
the player-visibility audit for all 4,848 decisions. The retained feature
tensors add memory cost, which was not measured here. Keep reuse opt-in until
a longer, representative schedule shows a worthwhile wall-time gain.

The ignored outputs are `.cache/goat-ai/reuse_bench_{off_a,on_a,on_b,off_b}_26000.pt`
with JSON reports for all except the first ordinary arm, and
`.cache/goat-ai/reuse_bench_on_a_26000_audit.json`. Reproduce an arm after
[native setup](native_setup.md) with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --seed 26000 --games 8 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 \
  --ppo-epochs 2 --ppo-batch-size 16 --snapshot-every 4 \
  --reuse-rollout-features --output .cache/goat-ai/reuse_bench_on_a_26000.pt
```

Omit `--reuse-rollout-features` for the ordinary path and use a separate
output name for each run. Replay directories default beside each checkpoint.

### PPO rollout execution comparison (27 October 2026)

The same unchanged feature-v23 parent played Jesse Goat Control versus
Warrior on seeds 23010–23013, using one frozen four-game PPO rollout, two
update epochs, minibatch 16, and `OMP_NUM_THREADS=1`. Three supported
execution modes were compared in two orders: one process worker, one process
with batched learner inference, and four process workers. Every mode and
order produced the **same four complete trajectories**, **2,948 decisions**,
**502 learner decisions**, and bit-identical final model tensors. The four
one-worker source trajectories replay-verified against the pinned native
core and passed the player-visibility audit.

| Mode | Worker-first order wall time | Batch-first order wall time |
| --- | ---: | ---: |
| One process worker | 5.494 s | 5.282 s |
| Batched inference | 5.792 s | 5.273 s |
| Four process workers | 5.566 s | 4.839 s |

The two orders do not establish a stable throughput winner on this four-game
schedule. Longer multi-rollout jobs may amortize process startup differently;
the separately measured eight-game persistent-worker comparison above showed
a 1.23× gain for four workers on another matchup. Keep these execution modes
opt-in until a representative larger matched training benchmark supports a
default change. The ignored outputs have prefixes
`.cache/goat-ai/rollout_{worker1,batch,worker4}_23010` with `_b` for the
reversed order; the JSON reports contain deck and native asset fingerprints.

A later [16-game matched benchmark](benchmarks.md#sixteen-game-ppo-rollout-workers)
measured a 1.38× four-worker speedup on this host in both run orders, with
identical trajectories and final tensors. Four workers are a supported
throughput option for comparable CPU PPO schedules; the default remains
unchanged pending wider hardware and matchup measurements.

Reproduce each arm with the same checkpoint and command settings below,
changing the execution flag and output path; the first arm used
`--rollout-workers 1`, the second `--rollout-batch-inference`, and the third
`--rollout-workers 4`:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --seed 23010 --games 4 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 \
  --ppo-epochs 2 --ppo-batch-size 16 --snapshot-every 4 \
  --rollout-workers 1 --output .cache/goat-ai/rollout_worker1_23010.pt
```

### Frozen-rollout baseline ablation (27 October 2026)

The existing four-duel PPO rollout freezes policy weights but, in its default
`online` mode, updates the moving return baseline after each duel. An opt-in
`--ppo-baseline-timing frozen_rollout` uses the pre-rollout baseline for all
four advantage calculations. The learner and opponent still receive only their own
player-visible observations. Tests cover both timings and confirm identical
native results across serial, process-worker, and batched-inference rollouts.

The original frozen-rollout run below used a flawed moving-baseline update:
each game replaced the estimate using the same frozen pre-rollout value, so
only the last game's reward affected the estimate carried to the next rollout.
The implementation now accumulates every terminal reward while retaining the
frozen pre-rollout value for that rollout's advantages. The checkpoint and
measurements below remain reproducible historical results of the old update
rule; they are not evidence for the corrected update rule's strength.

Starting from the same unchanged feature-v23 reference and using the same
32-game post-patch PPO schedule and settings as the online run above, the
frozen-baseline child completed **32/32** terminal duels, with **5,542 learner
decisions** and measured training wall time **38.09 s** with one Torch thread.
All 32 saved trajectories replay-verified and passed the visibility audit;
the audit shortlisted 69 review candidates. The ignored checkpoint is
`.cache/goat-ai/fv23_patched_core_ppo_frozen_baseline_21200_21231.pt`, SHA-256
`504c32544be81daf831c26b8aeee41685000b986abf5b49cbfe257b7065a41f0`.
Its replay-audit report SHA-256 is
`17d23e974377a702296436f5a8fe7158c06b037e9387daa2615d94cd1e138b9f`.

On held-out Phoenix Control versus two separately sourced Dimension Fusion
decks, with both deck assignments and policy seats, seeds 21500–21507 gave
the frozen child **28–36** directly against the online-baseline PPO child over
64 games. Its score interval was **34.4%–51.6%**. A separate direct comparison
on seeds 21516–21523 gave the frozen child **31–33** against the unchanged
parent, with score interval **40.6%–56.2%**. On a matched Tactical-v14 schedule
at seeds 21508–21515, the frozen child scored **13–51**, the online child
**10–54**, and the unchanged parent **10–54** over 64 games each. The frozen
minus parent paired score difference was **+4.7 percentage points**, 95%
interval **−1.6 to +10.9 points**. Local-deck and native-asset report
comparisons passed for both Tactical deck pairs. The ignored reports are
`.cache/goat-ai/frozen_vs_online_ppo_phoenix_*.json`,
`.cache/goat-ai/frozen_ppo_vs_parent_phoenix_*.json`, and the matched
`*_ppo_vs_tactical_phoenix_*.json` files. All evaluations used
`--engine experimental --both-deck-assignments --require-unseen-main-decks
--max-decisions 3000`. The new timing has no established strength gain, and
neither PPO child is promoted.

### Corrected frozen-rollout baseline check (27 October 2026)

The frozen-rollout baseline now accumulates every terminal reward for future
rollouts while using a single pre-rollout value for the current four games.
The checkpoint records `baseline_accumulation=all_terminal_rewards_v2` to
distinguish it from the earlier experiment above. Starting from the selected
feature-v23 parent (`975d06284b3035bc8bf8dbafa041a8a25a80195574d1ff695f2fbd25d1c7ff45`),
32 four-role PPO games on seeds 46000–46031 used the two World Championship
2022 deck pairings documented in the post-patch PPO command above, four
process workers, four-game rollouts, per-episode weighting, learner-deck
baselines, three epochs, batch size 16, learning rate 0.0001, and parent KL
weight 0.5. All 32 games reached terminal; the learner had 4,268 decisions.
Measured training wall time was 26.67 s on this host with one Torch thread.
All 32 trajectories replay-verified against the pinned native assets and
passed the visibility audit, covering 24,014 total decisions. The audit
shortlisted 42 review candidates; these are not proven mistakes.

The ignored checkpoint is `.cache/goat-ai/fv23_fixed_frozen_ppo_46000_46031.pt`
(SHA-256 `373b99f92915cb1684d0bb2d8b3d3fa08032ac04da35eb9deae2bd014ac26814`);
the ignored audit is `.cache/goat-ai/fv23_fixed_frozen_ppo_46000_46031_audit.json`
(SHA-256 `c07d528798ff93cdc98572458a262d0b7ff2e1c7f2c6a2ece4bcd45a13b32b88`).
The checkpoint and its 32 source trajectories remain outside Git.

On unseen 2005 Rhymus Goat Control versus Charlotte Zombie Main Decks, both
deck assignments and seats, seeds 46100–46107, the child scored **14–18**
directly against the parent over 32 duels (paired-bootstrap 95% score interval
25.0–59.4%). Against Tactical v14 on the identical 32-game schedule, the
child scored **15–17**, the parent **16–16**, and their paired score
difference was **−3.1 percentage points** (95% interval −21.9 to +12.5).
The report comparator verified identical native assets and source hashes,
current local deck files, and that both Main Deck compositions are absent
from both checkpoints' training provenance. Ignored report SHA-256 values are
`9e2420b78a2b7a2921d14dc70f3c2e7428a5ed253dc8e0acf279f3485ac219f3`
(direct), `614e348e29f5c467dd771decdd737b54f158e52bd9785672862558ff09719441`
(child versus Tactical), and
`2d99852515a53eab9b079d8441426d93c6d39ce4ecc429909c8d99224f74bca0`
(parent versus Tactical). This schedule does not show a self-play gain; the
selected parent remains unchanged.

### Longer lower-KL PPO continuation (27 October 2026)

To test whether the earlier short rollouts were undertraining the policy, a
predeclared continuation used **128** four-role self-play games on seeds
47000–47127 from the selected feature-v23 parent. It kept the two 2022
training matchups, four process workers, four-game PPO rollouts, per-episode
weighting, learner-deck moving baselines, three epochs, batch size 16, and
learning rate 0.0001. It reduced the frozen-parent KL weight from 0.5 to 0.1.
The snapshot-pool probability was 0.75; the remaining games used RandomAgent.
All 128 games terminated within 3,000 decisions: 77 learner wins, 50 losses,
one draw, and 16,988 learner decisions. Measured training wall time was
108.34 s with `OMP_NUM_THREADS=1`. These training outcomes are not a strength
estimate. All 128 saved trajectories independently replay-verified against
the pinned native assets and passed the visibility audit, covering **96,181
decisions**. The audit shortlisted 222 possible mistakes, including 47
end-turn choices with an activatable Thunder Dragon and 38 own-only Nobleman
activations; the flags are review prompts, not expert labels.

The ignored checkpoint is
`.cache/goat-ai/fv23_ppo_128_kl01_47000_47127.pt` (SHA-256
`5f0eae50832978cfb576b138f569a4e3d33f1fa7f881abe3d47fcf4330818175`),
and its ignored replay audit is
`.cache/goat-ai/fv23_ppo_128_kl01_47000_47127_audit.json` (SHA-256
`1fccc399d90f7faeadd4837c6ca87bb3207eb383e6ba98433adab266755e4f7a`).

Two independently held-out families used both deck assignments, both policy
seats, and 16 new seeds each. Against the unchanged parent directly, the child
scored **35–29** on 2005 Rhymus Goat Control versus Charlotte Zombie and
**34–30** on Phoenix Control versus Dimension Fusion Turbo. Their paired
bootstrap 95% score intervals were **42.2–68.8%** and **42.2–64.1%**.
Against Tactical v14 on the same schedules, the child scored **22–40–2** and
**20–44**; the parent scored **23–40–1** and **26–38**. The verified paired
child-minus-parent score differences were **−0.8 points** (95% interval
−14.1 to +12.5) and **−9.4 points** (−26.6 to +6.3). The comparator checked
native and source fingerprints, unchanged local decks, and absence of both
evaluation Main Deck compositions from both checkpoints' training records.
The six ignored evaluation reports have SHA-256 values, in direct-child,
child-Tactical, parent-Tactical order: Rhymus/Zombie
`b5f53838e3c7488a2cff62ecfb88f3570f81f035126ff0951d7829a96e5e3d08`,
`7f983d999d5f7e39b3db5dbb13707940fe8168e0af5c57777f76347e62193ae7`,
`ee143774359e12b9378deaaad92e09df3d849e4ec574321298eb2d0337a9e62b`;
Phoenix/Dimension
`eba108a8b279f23a7a9626e5636dfc90b60ae74f7d268e9e19448fa39731e318`,
`95c6c06dc887e98d4973b67b6b19ed8e3f5462c8efada46b6fe30c564b18b38a`,
`cd5db5ab32105c57e1d1bfcfb154ac74ee9320ef37f4ab87ddab5c85d28878f2`.
This is not a demonstrated competitive gain; the parent remains selected.

Reproduce training with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --engine experimental \
  --matchup examples/decks/chaos_control_insids_worlds_2022.ydk \
            examples/decks/bazoo_return_weirdchamp_worlds.ydk \
  --matchup examples/decks/goat_control_lolmarcus_2020.ydk \
            examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --schedule-mode four_roles --seed 47000 --games 128 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 --rollout-workers 4 \
  --ppo-rollout-weighting per_episode --ppo-baseline-timing online \
  --ppo-epochs 3 --ppo-batch-size 16 --ppo-clip-epsilon 0.2 \
  --learning-rate 0.0001 --parent-kl-weight 0.1 --baseline-scope learner_deck \
  --snapshot-every 4 --max-snapshots 8 \
  --output .cache/goat-ai/fv23_ppo_128_kl01_47000_47127.pt
```

Use `scripts/audit_selfplay_replays.py` on all 128 `episode_*.json` files.
Evaluate with `scripts/evaluate_policy.py --engine experimental
--both-deck-assignments --require-unseen-main-decks --seeds 16 --workers 4
--max-decisions 3000`: seed 47200 for Rhymus/Zombie, seed 47300 for
Phoenix/Dimension, and either `--opponent-checkpoint` for direct comparison
or `--opponent tactical` for the two matched Tactical arms.

### Leave-one-out PPO rollout baseline (27 October 2026)

An opt-in `--ppo-baseline-timing leave_one_out` now centers each completed
duel's terminal reward against the *other* games in the same frozen-policy
rollout and learner-deck group. Its baseline cannot depend on that duel's
sampled actions or outcome. A singleton group uses the pre-rollout moving
estimate. Games with no learner policy choice still contribute their outcome
to other games' baselines. The moving estimates continue to accumulate every
terminal result for later singleton fallbacks. This changes training updates,
not agent-visible observations or the simulator. Unit tests cover paired
rewards, separate deck groups, empty learner records, and a final singleton;
native tests confirm serial, process-worker, and batched-inference modes
produce equal trajectories, reports, and model tensors.

A matched four-role, 32-game ablation used the same selected parent, training
decks, seeds 46000–46031, four workers, four-game PPO rollouts, per-episode
weighting, learner-deck scope, three epochs, batch size 16, learning rate
0.0001, and parent KL weight 0.5 as the corrected frozen-baseline check above.
Only `--ppo-baseline-timing leave_one_out` changed. All 32 games terminated:
17 learner wins, 15 losses, 4,064 learner decisions, 23,487 total decisions,
and measured training wall time 25.36 s with one Torch thread. All 32 saved
trajectories independently replay-verified and passed the visibility audit;
38 possible mistakes were shortlisted. The ignored checkpoint is
`.cache/goat-ai/fv23_loo_ppo_46000_46031.pt` (SHA-256
`054c40ee0a1d85cebbc7a53026c833f6bbbfd816f6db990dfb5b226147a82de0`),
and the ignored audit is
`.cache/goat-ai/fv23_loo_ppo_46000_46031_audit.json` (SHA-256
`52516cb28265fb377af51cb15c4ed96b5f429cb5922ad43a932fbd8d29719127`).

On unseen Rhymus Goat Control versus Charlotte Zombie, both deck assignments
and seats, seeds 46100–46107, the child scored **16–15–1** directly against
the matched frozen-baseline child (paired-bootstrap 95% score interval
39.1–64.1%) and **17–15** against the selected parent (31.3–68.8%). Against
Tactical v14, the leave-one-out and frozen-baseline children each scored
**15–17**, while the parent scored **16–16**. The verified paired child-minus-
parent Tactical score difference was **−3.1 points** (95% interval −15.6 to
+9.4); leave-one-out minus frozen baseline was **0 points** (−12.5 to +12.5).
The report comparator checked matched native/source fingerprints, current
local deck hashes, and absence of evaluation Main Deck compositions from
training provenance. Ignored evaluation report SHA-256 values are
`d96dbd7f3b8a84df6c80a1e7c4ec774140a748eba6510e3e5ff78b0de57d1352`
(direct versus frozen), `1a25ad64cd0de083880cf458fe01257df18d529899224c52e89091a3605e144a`
(direct versus parent), `2dc158a2e310339e5785e3e377fde331a5cbe602171e35781bb24d84c1be16c9`
(leave-one-out versus Tactical),
`f5814f252a5e72d6bec3fa17459fdbb6d28622c15f2734d658227a1a84bbd5e9`
(frozen versus Tactical), and
`0d4be5ae1e129ac3d1030d476159898b61fd1331003e3af92f8264e88db06c97`
(parent versus Tactical). This small held-out sample gives no basis to promote
the child; leave-one-out remains an opt-in research setting.

Reproduce training with the corrected frozen-baseline command above, changing
only `--ppo-baseline-timing leave_one_out` and the distinct output path to
`.cache/goat-ai/fv23_loo_ppo_46000_46031.pt`. Replay-audit all
`episode_*.json` files in its adjacent replay directory. Evaluate with
`scripts/evaluate_policy.py` and the Rhymus/Zombie matchup on seed 46100,
eight seeds, both deck assignments, both seats, and an unseen-Main-Deck gate.

### Visible-rule v2 preference ablation (27 October 2026)

The `visible_audit_v2` automated-label experiment adds two narrow categories
to v1: activating Nobleman of Crossout while only one's own set monsters are
visible, and choosing one's own card for Raigeki Break when a legal opposing
field target exists. For the first category the alternative is an offered
Battle Phase transition from Main Phase 1 (or End Phase from Main Phase 2);
for the second it is an offered opposing field target. These are synthetic
pairwise hypotheses, not human-reviewed optimal-play labels. The v1 rule set
remains unchanged and old v1 label files continue to validate against v1.

The old 21200–21231 replays failed current-asset verification because they
recorded the pre-correction Dark Balter script. A fresh 32-duel frozen-policy
rollout from the unchanged feature-v23 reference used control/Chaos probe
decks, seeds 24000–24031, one PPO rollout with four workers, and the current
experimental native core. All duels terminated after **24,509 decisions**,
including **4,034 learner decisions**. Full native replay verification and
visibility auditing of these source games produced **12 preferences from
eight replays**: four Chaos Sorcerer self-banish, four new Nobleman cases,
three weak Flip summons, and one BLS self-banish. No Raigeki Break case was
present in this sample. The label manifest SHA-256 is
`8bfbcc86ab6acc212cab5a1fe0a998e7fabdd3234426096a308f15881c9a3d39`.

A parent-KL fit used those 12 labels, 64 distinct current-asset preservation
states from seeds 23000–23003, 100 steps, learning rate 0.0001, and KL weight
1.0. Preference loss fell from 1.8301 to 0.2247; final preservation KL was
0.0454. The ignored child checkpoint
`.cache/goat-ai/fv23_visible_rule_v2_24000_24031.pt` has SHA-256
`ac23fd824a439769e0c1945aa36e404514abf56f64afa1018259e72cd01336a3`.
Learning those comparisons is not a competitive-strength result.

On unseen Phoenix Control versus the GoatFormat and WikiFormat Dimension
Fusion Main Decks, both deck assignments and seats, seeds 25000–25007 gave
the child **34–30** directly against the unchanged parent over 64 duels;
its paired-bootstrap score interval was **45.3%–62.5%**. On matched seeds
25008–25015 against Tactical-v14, the child scored **13–49–2** and the
parent **18–46** over 64 duels each. The report comparator checked identical
opponent, deck hashes, native assets, source code, and schedule, and estimated
a child-minus-parent score difference of **−6.25 percentage points** with a
95% interval of **−17.19 to +6.25 points**. The visible-rule v2 fit did not
establish a gain and is not promoted. The ignored reports have the
`v2_pref_*_25000_25007.json` and `v2_pref_*_25008_25015.json` names under
`.cache/goat-ai/`. This experiment also shows that a small batch of obvious
mistake labels can improve its own comparison loss without improving held-out
play; the next strength experiment needs broader, independently validated
decision feedback and outcome-sensitive evaluation.

Reproduce the source and label steps after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --engine experimental \
  --matchup examples/decks/control_probe.ydk examples/decks/chaos_probe.ydk \
  --seed 24000 --games 32 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 32 --rollout-workers 4 \
  --ppo-epochs 1 --ppo-batch-size 16 --snapshot-every 32 \
  --output .cache/goat-ai/v2_pref_source_24000_24031.pt
PYTHONPATH=src:. .venv/bin/python scripts/derive_visible_rule_preferences.py \
  .cache/goat-ai/v2_pref_source_24000_24031_replays/episode_*.json \
  --native-root .cache/goat-ai --rule-set visible_audit_v2 \
  --output-dir .cache/goat-ai/v2_pref_labels_24000_24031
```

The `train_review_preferences.py` command takes each of the eight matching
replay/label pairs with `--case`, four seed-23000–23003 current-asset replays
with `--preserve-current-trajectory`, then the fit hyperparameters above.
The held-out tournaments use `scripts/evaluate_policy.py` with
`--both-deck-assignments --require-unseen-main-decks --workers 4
--max-decisions 3000`, and either the unchanged parent checkpoint or
`--opponent tactical` as the opponent.

### PPO minibatch-32 speed pilot (27 October 2026)

The same 16-game, four-worker self-play schedule was trained with PPO
minibatches of 16 and 32. [The speed measurements](benchmarks.md#ppo-minibatch-16-versus-32-2026-10-27)
favor batch 32 on this schedule. Both settings were then evaluated on held-out
Main Deck compositions: Chaos Control/Bazoo Return and Dimension Fusion
Turbo/Phoenix Control, with both deck assignments and both seats on seeds
28100–28103. Batch 32 scored **17–15** directly against batch 16 over 32
duels (53.1%, paired 95% interval 43.8%–62.5%). Against Tactical on matched
seeds 28104–28107, batch 32 scored **7–25** and batch 16 scored **6–25–1**.
The paired Tactical score difference was +1.6 percentage points, with a 95%
interval of −4.7 to +9.4 points. The report comparator checked matching
source, native assets, seeds, and local deck hashes. Batch 32 is faster in
this pilot, but these outcomes do not establish a playing-strength gain or
close M4's competitive gate. It remains opt-in.

The ignored reports are `.cache/goat-ai/ppo_batch32_vs_16_28100.json`,
`ppo_batch16_vs_tactical_28104.json`, and
`ppo_batch32_vs_tactical_28104.json`; the Tactical report SHA-256 values are
`3a18742b77480dc767e477f704d2b6ffecd9367c9a3cb8dd7f9de9ae4e371b7a`
and `826f7354b8d80d256c22a6549145ad6822fc80a6c4fc3893f76d5d345369cf16`.
The direct report SHA-256 is
`4f42dac27427dd5eee4fd07f81d9fc333f3154fe56d2535313244a61d57dc53d`.

### Frozen-opponent frequency in PPO self-play (27 October 2026)

Two 64-duel continuations started from the unchanged feature-v23 reference
checkpoint. Both used the sourced Jesse Goat Control/Warrior pairing in all
four deck/seat roles, seeds 32000–32063, four rollout workers, four-game PPO
rollouts, two update epochs, minibatch 32, per-episode weighting, a per-deck
moving return baseline, parent KL weight 0.5, and the same native assets. The
sole planned difference was `--historical-probability`: **0.75** sampled a
frozen past policy in 48 games and RandomAgent in 16; **1.0** sampled a frozen
policy in all 64. The first run recorded 38–26 and
5,846 learner decisions in 27.281 seconds; the second recorded 29–35 and
5,633 learner decisions in 26.916 seconds. Training wins are against different
opponent mixtures and do not compare playing strength.

All 128 terminal training trajectories independently replay-verified against
the pinned experimental native engine and passed the visibility audit:
34,025 decisions for the 0.75 arm and 34,053 for the 1.0 arm. The checks used
four isolated processes and the existing `verify_training_trajectory` gate.
No game hit the 3,000-decision cap or an unsupported native request.

On held-out Chaos Control/Bazoo Return and Dimension Fusion Turbo/Phoenix
Control Main Decks, both assignments and seats, seeds 32100–32107, the 1.0
child scored **33–30–1** directly against the 0.75 child over 64 duels
(52.3%, paired 95% interval 46.9%–57.8%). On separate seeds 32108–32115,
the 0.75 child scored **30–34** and the 1.0 child **31–33** against the
unchanged parent. On matched seeds 32116–32123 against Tactical-v14, the
0.75 child scored **9–55**, the 1.0 child **7–56–1**, and the parent
**9–55**. The paired Tactical score differences versus the parent were
0.0 points (interval −9.4 to +9.4) and −2.3 points (interval −10.2 to +6.3),
respectively. The tournament report comparator confirmed matching source,
native assets, local deck hashes, opponent, and schedules for the matched
baseline arms. Neither child meets M4's held-out self-play gain gate; retain
the unchanged reference and prioritize better decision feedback or value
estimation over simply changing the opponent mixture.

The ignored checkpoints are `.cache/goat-ai/historical75_32000_32063.pt`
(SHA-256 `4eb9d85fffba7b6ad0be96cea4d3879dabeb5de033b0a43206e28c3f174b5a90`)
and `historical100_32000_32063.pt` (SHA-256
`7e54ac09f93c681c249b45cb9986e643a171488a304ae2f4d9835b634d5c66eb`).
Their replay directories share those stems. The direct child-vs-child report
is `historical100_vs_75_32100.json` (SHA-256
`62be4acf273dcab0530b84c99b00145ce5f1d68af3867fca9ac5ad277d7d4585`);
the parent and Tactical reports use `historical{75,100,parent}_vs_*_321*.json`
names in the same ignored cache.

Reproduce one training arm after [native setup](native_setup.md), changing
`PROBABILITY` between `0.75` and `1.0` and using a fresh output path:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --schedule-mode four_roles --seed 32000 --games 64 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 --ppo-epochs 2 \
  --ppo-batch-size 32 --ppo-rollout-weighting per_episode \
  --baseline-scope learner_deck --snapshot-every 4 --parent-kl-weight 0.5 \
  --historical-probability PROBABILITY --rollout-workers 4 \
  --output .cache/goat-ai/historical_PROBABILITY_reproduction.pt
```
### Fresh 64-duel current-core Tactical continuation (27 October 2026)

The earlier 64-duel Tactical-v14 imitation gain used trajectories recorded
before the GOAT SEGOC native-core correction. Its exact replay provenance
therefore cannot train a current-core checkpoint. A later 16-duel current-core
continuation had an inconclusive held-out result. To test whether fresh data
volume mattered, the unchanged feature-v23 neural reference was continued on
64 newly recorded native duels: 32 Chaos Control/Bazoo Return with Tactical-v14
on both seats (seeds 33000–33015), and 32 Lolmarcus/Michael Goat Control
with Tactical-v14 against Combat v3 (seeds 33016–33031). These produced
42,005 total decisions and 21,815 Tactical-seat decisions. The clone trainer
independently replay-verified all 64 complete duels and audited their
player-visible observations before fitting. These are synthetic teacher
demonstrations, not human play.

The width-32 continuation used two epochs, batch size 16, batched forward,
forced-forward omission, learning rate 0.0002, seed 55, and four verification
workers. Imitation loss fell from 0.170915 to 0.144211. Reported training
wall time was 55.99 seconds, including 13.22 seconds of verification and
23.42 seconds of fitting. The ignored checkpoint is
`.cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt` (SHA-256
`975d06284b3035bc8bf8dbafa041a8a25a80195574d1ff695f2fbd25d1c7ff45`).
The SHA-256 of the sorted `relative_path + space + file_sha256 + newline`
manifest for the 64 source trajectories is
`c86b0b770efcd3824a7e4b5060bfb1bd06039dc740128c8ca664fda8311c40c8`.

The held-out tournament used Phoenix Control against each of two Dimension
Fusion Turbo lists, both deck assignments and policy seats, seeds 33100–33107.
The evaluator rejected any training Main Deck composition or seed. The child
scored **33–30–1** directly against its parent over 64 games (52.3%; paired
95% interval 39.1%–65.6%), which does not establish a direct improvement.
On separate matched seeds 33108–33115 against Tactical-v14, the child scored
**20–44** and the parent **13–51**. Their paired score difference was **+10.9
percentage points** (95% interval **+1.6 to +20.3**). The child's assigned-deck
records were Phoenix 12–20, GoatFormat Dimension Fusion 5–11, and WikiFormat
Dimension Fusion 3–13; the parent scored 6–26, 5–11, and 2–14 respectively.
The report comparator verified matching native assets, card scripts, source
code, opponent, seeds, and local deck hashes.

An additional held-out Dimension Fusion Turbo mirror, without Phoenix,
tested both deck assignments and seats. Against Tactical-v14 on matched seeds
33120–33127, the child scored **11–21** and the parent **5–27**, a paired
**+18.8-point** difference (95% interval **+6.3 to +31.3**). Directly against
the parent on separate seeds 33128–33135, the child scored **17–15** over
32 games (paired 95% interval 43.8%–62.5%). This supports a Tactical-baseline
gain on a second matchup, while direct parent strength remains uncertain.
The child still loses decisively to Tactical-v14 overall, has no human-play
evaluation or self-play improvement, and is not promoted as the competitive
reference. M4 remains open.

The ignored training summary SHA-256 is
`7522a0b26b21768ba5d0eb5e8098b5bc1e608733a6600f8a2f6d297c304a5ba1`.
The six tournament report SHA-256 values, in the order described above, are
`b55c87c25d591a8092b6f8f24cd883e60f282565fb1b79e636ac2a85462b90d7`,
`c05cb27e068ca6345cfde9ad0cd57304db14ed10407e643ea61f2d724b40a8dc`,
`20140c0a1ab57f4690d7833127607596c1d5779b0d9979377909d8843ba3044f`,
`ff57a4ab8f52f6547f048b7050514825d32922329b120c73cf8c6aa171fa815e`,
`b6ebcfa48999fbdb04900a47301f2cd5566362ace2a790e71caec2e0c195d7ed`,
and `e674191b886be396a102d2d4e95f95882c884327fb5f2a37809304571b19c3a2`.
Reproduce the collection with `scripts/collect_heuristic_demos.py --engine
experimental --teacher tactical` using the two deck pairs and seed blocks
above, then train with `scripts/train_behavioral_clone.py --engine experimental
--feature-version 23 --width 32 --epochs 2 --batch-size 16 --batched-forward
--omit-forced-forward --verification-workers 4 --learning-rate 0.0002
--seed 55 --init-checkpoint
.cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt`. Evaluate
with `scripts/evaluate_policy.py --engine experimental
--both-deck-assignments --require-unseen-main-decks --workers 4 --seeds 8`
and the matchups, seeds, and opponents above. Use distinct ignored output
paths for each run.

### Self-play from the fresh current-core imitation child (27 October 2026)

To test whether the stronger Tactical-imitation starting point helps PPO, a
64-duel continuation began from the fresh current-core child above. It used
Jesse Goat Control versus Warrior in all four deck/seat roles, seeds
34000–34063, four process workers, four-game frozen rollouts, two PPO epochs,
minibatch 32, per-episode weighting, a learner-deck moving baseline, parent
KL weight 0.5, and 0.75 frozen-opponent probability. All **64 duels reached a
terminal result** with no decision-cap or unsupported-game exclusions. The
learner's 37–26–1 training record measures its sampled training opponents,
not improvement. The trainer reported 28.41 seconds and 5,623 learner
decisions. Independently replay-verifying every output and auditing
player-visible observations covered **34,755 decisions**. The 64-replay
manifest SHA-256 is
`258c72ec2e1608df86ea5c2169410e262ad910a72d142e559f3de1c567fc978a`.

On held-out Phoenix Control versus both Dimension Fusion Turbo lists, both
deck assignments and policy seats, the PPO child split **31–31–2** directly
against its imitation parent on seeds 34100–34107 (50.0% score; paired 95%
interval 42.2%–59.4%). On separate matched seeds 34108–34115 against
Tactical-v14, the PPO child scored **17–46–1** and the imitation parent
**21–42–1**. Their paired score difference was **−6.25 percentage points**
(95% interval **−13.3 to +1.6**). The report comparator confirmed matched
native assets, card scripts, source, local deck hashes, opponent, and seeds.
This run does not establish a self-play gain; retain the imitation child as an
experimental comparison and keep M4's self-play exit open.

The ignored PPO checkpoint
`.cache/goat-ai/current_broader_ppo_34000_34063.pt` has SHA-256
`d552bd5f5e7ff5a26cf5750e25da60039ed74c303d0da60323c7711029975007`.
Its training summary SHA-256 is
`5e222e19693d157f8cb67a52350aeb2a08c097cdba2e3841d1c4974266af093c`.
The direct, child-versus-Tactical, and parent-versus-Tactical report hashes
are `bec26169c9505ab2e6d66e17ffe74572f627b0d5a8dd0c21611c64644da9d1a8`,
`594179099eacc8cb279e661a3b1cfeef30df56e0858cac3eba6d4765d3ad112f`,
and `0e13a83aa5986b6edd04a50ac9a2ee4f43fbacb0888f61e4158eb458243f3232`.
Reproduce the training with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_self_play.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --schedule-mode four_roles --seed 34000 --games 64 --max-decisions 3000 \
  --policy-update clipped_ppo --ppo-rollout-games 4 --ppo-epochs 2 \
  --ppo-batch-size 32 --ppo-rollout-weighting per_episode \
  --baseline-scope learner_deck --snapshot-every 4 --parent-kl-weight 0.5 \
  --historical-probability 0.75 --rollout-workers 4 \
  --output .cache/goat-ai/current_broader_ppo_reproduction.pt
```

### Tactical baseline opponent in PPO (27 October 2026)

The self-play trainer now offers `--baseline-opponent tactical` for the
non-snapshot branch. A two-game worker smoke on control/Chaos probes completed
both duels against Tactical-v14. One- and two-worker runs wrote byte-identical
trajectories and equal model tensors; one 763-decision replay independently
verified against the pinned native engine and passed the visibility audit.

A matched 64-duel continuation used the same current-core imitation parent,
Jesse Goat Control/Warrior four-role schedule, seeds 34000–34063, four rollout
workers, four-game PPO rollouts, two update epochs, batch 32, per-episode
weighting, learner-deck baselines, parent KL 0.5, and 0.75 snapshot probability
as the preceding experiment. The only schedule change was replacing the
RandomAgent branch with Tactical-v14. Seventeen duels sampled Tactical and 47
sampled frozen snapshots. All 64 terminated below the 3,000-decision cap;
the sampled learner went 26–38, with 4,697 learner decisions. Reported trainer
time was **25.84 seconds** on this host. Every trajectory independently
replay-verified and passed visibility checks, covering **30,362 decisions**.
The ignored child checkpoint SHA-256 is
`e2a636bbf57cef01550eb15794061c98b2f1c1fc7f0bd79517473c1f5d1260cf`;
the 64-replay audit SHA-256 is
`422faf859070fb3b9ec144b12634cd1b8e122c27871a675c05af2a98de1f9fdf`.

On fresh Phoenix/Dimension Fusion Main Decks, both deck assignments and
policy seats, the child scored **34–28–2** directly against its parent over
64 games (54.7% score; paired 95% interval 46.9–62.5%). This does not
establish a direct strength gain. Against Tactical-v14 on a separate matched
64-game schedule, the child scored **13–48–3** and the unchanged parent
**21–42–1**. The report comparator independently checked unseen Main Deck
compositions and matching decks, seeds, native assets, scripts, source, and
opponent, then measured a child-minus-parent difference of **−10.9 percentage
points**, paired 95% interval **−19.5 to −1.6**. Thus Tactical exposure in
this small mixture worsened held-out Tactical performance. Keep the parent as
the neural reference; M4's self-play improvement gate remains open.

The ignored child-versus-parent, child-versus-Tactical, and
parent-versus-Tactical report hashes are respectively
`5703bced640c6c04d5ff1a94e3f559985f9f95ca687217d871b9444e548463d8`,
`37bcb0221834cf47c710b3ee4d4c23ff441a286310ae1929e9035c28e55a12fd`,
and `c2aa5bfff678dd66a21d2e49c62307e97b52fcf742a16a6243a402dfc8181c68`.
Reproduce the training with the preceding 64-duel PPO command, adding
`--baseline-opponent tactical`, a new output path, and the same seed block.
Use `scripts/evaluate_policy.py --both-deck-assignments
--require-unseen-main-decks --workers 4 --seeds 8` on the named holdouts and
seed blocks 34100–34107 and 34108–34115; compare the matched Tactical reports
with `scripts/compare_tournament_reports.py --require-unseen-main-decks`.

### Contemporary Charlotte Zombie holdout (27 October 2026)

The [preserved 2005 SJC Charlotte Top 8 article](https://www.goatformat.com/home/top-8-decklists5124684)
prints Jae Kim's 40-card Zombie Main Deck. The exact transcription is
`examples/decks/zombie_jae_kim_charlotte_2005.ydk` (SHA-256
`80dbb16071a314a333d6c6d8cf6365b712d2611a490ff96c41cd707d095a35ad`).
The published Side Deck is omitted because this experiment plays single duels;
no Fusion Deck was listed. A four-test fixture verifies card names, copy
counts, whitelist legality, and two seat-swapped native terminal duels against
2005 Phoenix Control, including exact replay verification and visibility audit.
This is protocol evidence, not a full card-by-card 2005 ruling audit.

The current-core Tactical-imitation child and its neural parent had never
trained on this Main Deck composition. On seeds 36100–36107 with both deck
assignments and agent seats, the child scored **33–31** directly against the
parent over 64 Zombie/Phoenix and Zombie/Wiki Dimension Fusion duels (51.56%;
paired 95% interval 43.75–60.94%). Against Tactical-v14 on matched seeds
36108–36115, the child scored **19–45**, versus **18–46** for the parent. The
paired difference was **+1.56 percentage points**, with a 95% interval of
**−10.94 to +14.06 points**. With Zombie assigned to the candidate, the
child scored 7–25 and the parent 10–22. The broader transfer gain seen on an
earlier Phoenix/Dimension Fusion schedule does not carry over convincingly to
this new Zombie pairing; neither policy is promoted. M4 remains open.

The three ignored reports are
`.cache/goat-ai/current_clone_zombie_vs_parent_36100_36107.json`,
`.cache/goat-ai/current_clone_zombie_vs_tactical_36108_36115.json`, and
`.cache/goat-ai/current_parent_zombie_vs_tactical_36108_36115.json`, with
SHA-256 values `72ac447adbbaad5b410a99b85269fd3105cfb0bf75f311e680029e97f6d02ef5`,
`73d588c8d8a81b9fc7563386c33946d1ddaba32e238f82a383321006ec2cd2fc`,
and `7d3e399bc6a2727e0de0b048c1f2dd7492eda733c6a8beeea3aaf79fdff66fdf`.
The evaluator required unseen Main Decks and bound the same native assets,
card scripts, source, local deck hashes, opponent, and seeds in the paired
Tactical comparison. All 192 tournament duels reached terminal; the fixture
tests, rather than the tournaments, recorded full replay-verified trajectories.

### Additional Tactical imitation and cross-family holdout (27 October 2026)

The current-core imitation child above was continued on **32 newly recorded
Tactical-v14 versus Tactical-v14 duels**: Daryl Gessler Gravekeepers versus
Cas Stomphorst Flip Control on seeds 36300–36307, and Matt Peddle Goat Control
versus Montague Warrior on seeds 36308–36315, with the demonstrator in both
seats. These are distinct from the Charlotte/Phoenix/Dimension Fusion
evaluation compositions. The 32 source trajectories contain **15,689 native
decisions** and **7,845 demonstrator decisions**. The clone trainer replay-
verified and visibility-audited every source duel before fitting. Two epochs,
width 32, minibatch 16, batched forward, omitted forced forwards, learning
rate `0.0002`, seed 56, and four verification workers reduced imitation loss
from 0.113257 to 0.100014. Reported total time was **20.37 seconds**, including
5.70 seconds of verification and 8.24 seconds of fitting. The ignored
checkpoint `.cache/goat-ai/fv23_current_diversity_36300_36315.pt` has SHA-256
`3afb14c8e11c3ed23fdf20b7e8d7b976309932dce7512e97071bae7b1304936f`.
The sorted `relative_path + space + SHA-256 + newline` manifest over all 32
source files hashes to
`f4361fd0de0ccda48e3c7285ccd3abc32a04afdc30a722bbcefaa022a880d303`.

On unseen Charlotte Zombie versus Phoenix and WikiFormat Dimension Fusion,
both deck assignments and policy seats, seeds 36400–36407, the child scored
**41–23** directly against its parent (paired 95% score interval
**57.8–71.9%**). By assigned deck it scored Zombie 21–11, Phoenix 12–4, and
Dimension Fusion 8–8. On matched seeds 36408–36415 against Tactical-v14, the
child scored **18–44–2** and its parent **20–44**. Their paired score
difference was **−1.6 points** (95% interval **−14.8 to +11.7**).

An independent unseen family, Phoenix versus both the WikiFormat and
GoatFormat Dimension Fusion lists, reversed the direct result: on seeds
36500–36507 the child scored **27–37** against its parent (paired interval
**34.4–51.6%**). On matched Tactical seeds 36508–36515, it scored **18–46**
versus the parent's **21–43**, a **−4.7-point** paired difference (95% interval
**−15.6 to +6.3**). Each Tactical comparator confirmed matching opponent,
seeds, native assets, card scripts, source, and local deck hashes. All **384
evaluation duels** reached terminal; these tournaments did not save full
trajectories. The child also retained the two own-resource activations in the
[Charlotte review](replay_audit.md#charlotte-zombie-holdout-review-27-october-2026).
It is an experimental matchup-dependent child, not a promoted reference or
evidence of broad competitive improvement. More synthetic Tactical labels
alone remain lower priority than independently reviewed decisions and a
stronger outcome signal.

The ignored direct reports are
`current_diversity_zombie_vs_parent_36400_36407.json` (SHA-256
`02853ed408fc90178602ff76b17bf984dc4cf35392a35a8717322b939bf365e8`)
and `current_diversity_phoenix_vs_parent_36500_36507.json`
(`4c928e8f1867df05af83c189f9ff24debdcbfde914beee64c02d7b6a100b4c56`).
The matched child/parent Tactical reports for Zombie are
`current_diversity_zombie_vs_tactical_36408_36415.json`
(`82ad9b547916c64759e78ec5a4fa9841264efb12bcaf9360ea3e9661646a6a9f`)
and `current_parent_zombie_vs_tactical_36408_36415.json`
(`fd757950ec17ec1fe3a9797748a9975b542b3445b3c5272fbd01dd952553a267`).
For Phoenix they are `current_diversity_phoenix_vs_tactical_36508_36515.json`
(`9a0c173234bc56ab59d980882e0b9b49dc2ff70255e909f144a01e27bee9edd4`)
and `current_parent_phoenix_vs_tactical_36508_36515.json`
(`6a54de27a0e82862cb5bc8a9ec7cb227a91e108cf78889e5aeaf5920060aad0c`),
all under `.cache/goat-ai/`. Reproduce the source duels with
`scripts/collect_heuristic_demos.py --engine experimental --teacher tactical
--opponent tactical --seeds 8` on each pairing and seed block above. Continue
the parent with `scripts/train_behavioral_clone.py --engine experimental
--feature-version 23 --width 32 --epochs 2 --batch-size 16 --batched-forward
--omit-forced-forward --verification-workers 4 --learning-rate 0.0002
--seed 56 --init-checkpoint
.cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt` and all 32
source replay paths. Evaluate with `scripts/evaluate_policy.py --engine
experimental --both-deck-assignments --require-unseen-main-decks --workers 4
--seeds 8 --max-decisions 3000` on the pairs and seed blocks above.

### Visible resource v3 counterfactual preference experiment (27 October 2026)

The saved-report comparator now has `--require-unseen-main-decks` for M4
comparisons. It verifies both local YDK files against their report hashes,
recomputes each Main Deck composition hash, and rejects a composition present
in either checkpoint's recorded training games. It fails closed for older
reports without composition provenance. On the existing 64-game Zombie
child/parent Tactical reports below, the gate passed and reproduced the
paired +14.06-point difference (95% interval +3.125 to +23.4375 points).
This verifies the exact Main Deck multisets, not archetype independence.

```bash
PYTHONPATH=src:. .venv/bin/python scripts/compare_tournament_reports.py \
  .cache/goat-ai/resource_v3_zombie_child_vs_tactical_36608_36615.json \
  .cache/goat-ai/resource_v3_zombie_parent_vs_tactical_36608_36615.json \
  --require-unseen-main-decks
```

The source was 64 current-core PPO self-play replays on seeds 34000–34063.
`scripts/derive_visible_rule_preferences.py --rule-set visible_resource_v3`
replay-verified and visibility-audited every duel before emitting **137
synthetic preferences from 25 replays**. Of these, 128 compared a recorded
safe choice with an offered resource loss; nine compared a recorded loss with
an offered phase transition. There were 44 Nobleman and 100 Heavy Storm
category occurrences; a decision can carry both categories. Repeated
near-identical resource contexts in one replay were deduplicated, though one
replay still contributed 38 preferences. The ignored manifest is
`.cache/goat-ai/visible_resource_v3_dedup_34000_34063/manifest.json`
(SHA-256 `ff7a0f0ddf8a025cd781219c2e55467294922b3864e216fde137ff35ffdb241c`).
These are narrow visible-card-trade hypotheses, not expert decisions.

Starting from the unchanged current-core parent, a 30-step parent-KL fit
used all 137 preferences plus 64 preservation states from four
parent-provenance Tactical replays on seeds 33016–33019. The fit used
preservation batch 8, KL weight 1, learning rate 0.0001, and seed 57.
Preference loss went from **0.1893 to 0.0969**; final preservation KL was
**0.00482**. These are fit diagnostics, not a playing-strength measure. The
ignored child checkpoint is `.cache/goat-ai/fv23_visible_resource_v3_34000_34063.pt`
(SHA-256 `2636e05b7b3c8df8c6f0e661c6a8f23735460ac8553e5f9ea8b8e64dca7fe1dd`).
On two previously flagged Zombie replay states, the child changed an
immediate Heavy Storm activation into a Set but still activated an own-only
Nobleman.

Fresh held-out evaluation used the experimental native engine, eight seeds
per block, both deck assignments and policy seats, unseen Main Decks, four
workers, and a 3000-decision cap. All **384 duels** reached terminal. On
Charlotte Zombie versus Phoenix and WikiFormat Dimension Fusion, the child
split **32–32** directly with its parent on seeds 36600–36607 (paired 95%
score interval 39.1–60.9%). Against Tactical-v14 on matched seeds
36608–36615, the child split **32–32** while the parent scored **23–41**:
paired child-minus-parent **+14.06 percentage points**, 95% interval
**+3.125 to +23.4375**. This is a deck-family-specific signal.

On independent Phoenix versus WikiFormat and GoatFormat Dimension Fusion
pairings, the child scored **36–28** directly against its parent on seeds
36700–36707 (paired 95% interval 43.75–68.75%). Against Tactical-v14 on
matched seeds 36708–36715, it scored **22–41–1** versus the parent's
**25–38–1**: paired difference **−4.69 points**, interval **−17.97 to
+9.38**. Both Tactical comparisons matched opponent, seeds, native assets,
card scripts, source, and local deck hashes. The child is not promoted: the
cross-family result is uneven and the Nobleman mistake persists. M4 remains
open.

The ignored direct report hashes for Zombie and Phoenix are respectively
`38a81b54a273a4b497048067d0afbd9adacdebf5bed8a9e993318812c8eeb283`
and `f05c5d61461573a5a690f2651439ba594c3677fcb89525f06aed73103771897b`.
Matched child/parent Tactical report hashes are respectively
`25d3da9f1a0d215b3e92339ed191f84a590e59cd5e38316345833edbf5cf0e11` /
`f72ce06ca6417f5188e2165f9456bf0d4797c63b89ea0eb47064dc56eaffdcc9`
for Zombie and
`42aa90084a0fc2daf4e53eca45acf3708d443a7c964d3e0396062b0b6af79bda` /
`17e5cef77f500f57c596c8e89d0b92abfe1615e92953fa17c1c25e5b77794461`
for Phoenix. The reports are under `.cache/goat-ai/` with the
`resource_v3_` prefix and seed ranges above.

### Optional fast trajectory reading for cloning (27 October 2026)

`read_trajectory(..., fast_json=True)` and the cloning CLI's
`--fast-trajectory-json` use optional `orjson` for source replay decoding.
The command still verifies every complete replay and audits player visibility.
On 16 PPO source replay files totaling 61.0 MB, four in-memory decode runs
had median times of **0.766 s** with standard `json` and **0.477 s** with
`orjson`; this measures JSON decoding only. A separate proposed split of
16-decision neural batches by legal-action count was discarded: on 512
recorded learner decisions it took **0.174 s** per pass versus **0.114 s**
for the existing batch despite reducing action padding. The maximum valid
logit difference in that diagnostic was `2.4e-7`.

For a full-command check, eight self-play replays on seeds 34000–34007
supplied **2,023 training decisions**. Each arm used the unchanged v23
current-core parent, one cloning epoch, width 32, minibatch 16, batched
forward, omitted forced forwards, seed 58, four native verification workers,
and one Torch thread. Runs were ordered standard, fast, fast, standard.
CLI-reported wall times were **5.777 / 5.651 s** for standard and
**5.670 / 5.527 s** for fast; the matched reductions were **0.107 / 0.124 s**.
All four runs had exactly the same loss (`0.1490818825`), source hashes,
and model tensors. The small speed difference is specific to this machine
and workload; it does not establish a general training-throughput gain.

The ignored checkpoints are `.cache/goat-ai/fast_read_{off_a,on_a,on_b,off_b}_34000_34007.pt`.
Reproduce one arm with `scripts/train_behavioral_clone.py` on the eight
`current_broader_ppo_34000_34063_replays/episode_0000[0-7]_seed_*.json`
files, `--engine experimental --init-checkpoint
.cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt --epochs 1
--batch-size 16 --batched-forward --omit-forced-forward
--verification-workers 4 --width 32 --feature-version 23
--learning-rate 0.0002 --seed 58`; add `--fast-trajectory-json` for the
fast arm and use a distinct ignored output path.

### Recorded-bad preference weight ablation (27 October 2026)

Schema-v2 resource feedback had 128 comparisons where the recorded policy
avoided a flagged loss and nine where it chose one. An opt-in
`--recorded-bad-weight 8` fit increased the latter comparisons' relative
pairwise-loss contribution while keeping the same 137 source preferences,
parent, 30 steps, 64 preservation states, seed 57, learning rate 0.0001,
and KL settings as the unweighted child. The preservation files were the
exact same four seed-33016–33019 seat-0 Tactical replays. The final weighted
preference loss was **0.2492** and final preservation KL **0.00496**; these
values use a different loss weighting and are not comparable to the
unweighted loss as a strength metric. The ignored checkpoint is
`.cache/goat-ai/fv23_visible_resource_v3_bad8_matched_34000_34063.pt`
(SHA-256 `7f0c1ba5c1fd31b8aaf08bceeb4c5af065ed5efdf550a984f670da49b8922a20`).

On fresh held-out seeds 36800–36807, both assignments and policy seats,
the weighted child scored **29–34–1** directly against the unweighted v3
child across Charlotte Zombie versus Phoenix and WikiFormat Dimension
Fusion (paired 95% score interval **39.8–51.6%**). On independent Phoenix
versus WikiFormat and GoatFormat Dimension Fusion pairings, seeds
36900–36907, it scored **34–30** (paired interval **50.0–57.8%**).
All 128 duels reached terminal before the 3000-decision cap. Neither family
shows a convincing gain; the inspected own-only Nobleman choice persists,
while the inspected Heavy Storm activation remains corrected to a Set. The
unweighted and weighted children both remain experimental. The direct
reports are `.cache/goat-ai/resource_v3_bad8_matched_vs_v3_zombie_36800_36807.json`
(SHA-256 `1101f2976556acff08371b4e7b3f9a57bd2cc1e5fe5c1b99c3bb06fce2f1a2a1`)
and `.cache/goat-ai/resource_v3_bad8_matched_vs_v3_phoenix_36900_36907.json`
(`4b5f8bdcebbb3cbd02deeaf057a31a7d92a04a9066796901ae29432e0a43aede`).

An earlier trial selected seat-1 preservation replays for two seeds and is
excluded from this ablation because preservation differed. Reproduce the
matched fit from the v3 manifest's 25 replay/preference path pairs, plus
`current_tactical_goat_mirror_33016_33031/seed_3301{6,7,8,9}_seat_0.json`,
with the parameters above and the new weight flag. Reproduce the direct
checks using `scripts/evaluate_policy.py --engine experimental
--opponent-checkpoint .cache/goat-ai/fv23_visible_resource_v3_34000_34063.pt
--both-deck-assignments --require-unseen-main-decks --workers 4 --seeds 8
--max-decisions 3000`, the named deck pairs, and the two seed blocks.

### Additional distinct-whitelist protocol sweep (27 October 2026)

Starting from source commit `dc7e3eb` and the pinned experimental native
assets, `scripts/probe_random_decks.py` generated 100 independently sampled
legal Main Deck pairs on seeds 30150–30249. Every duel reached terminal
before the 3000-decision cap (maximum **1,571** decisions), with no adapter
error. All **107,628** decisions replay-verified against fresh engines and
passed the player-visibility audit. The audit counted 1,085 hidden-field,
5,349 opponent-field, and 47 opponent-hand legal-choice contexts. The 200
generated decklists contained **1,616 distinct Main Deck IDs**. The run
loaded 1,302 native assets and offered 5,339 distinct source-card/action-kind
pairs; it selected 59 distinct chain-response/source pairs. These are
sampled protocol and information-boundary measurements, not historical
card-ruling or competitive-strength measurements.

Relative to the prior distinct-whitelist seeds 10356–10455 report, this
run loaded 11 previously unobserved official card scripts: D.D. Designator,
Gamble, Aussa the Earth Charmer, Monk Fighter, Kiseitai, Sword of the
Soul-Eater, Token Thanksgiving, Mystic Swordsman LV6, Koitsu, Final Flame,
and Total Defense Shogun. Loading a script does not establish that its
effects were exercised or that its 2005 behavior is correct. The ignored
report is `.cache/goat-ai/whitelist_distinct_30150_30249/report.json`
(SHA-256 `ba10153a4cd9674d8baf4cf7ec96ef1c4be8d4efaee881f3ca6b67bf6da3c131`).
Its asset hashes, deck hashes, rules profile, action counts, and per-game
outcomes are saved in that report. Reproduce after
[native setup](native_setup.md) with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/whitelist_distinct_30150_30249 \
  --seed 30150 --seeds 100 --max-decisions 3000 \
  --verify-replays --distinct-opponents --count-card-actions
```

### Exchanged Thunder Dragon native ruling fixture (27 October 2026)

The [period Thunder Dragon FAQ](https://www.goatformat.com/rulings7.html)
allows the controller of an opponent-owned copy obtained through Exchange to
discard it and search that controller's own Deck. The new seed-28 fixture
starts with Exchange in player 0's hand and two Thunder Dragons in player
1's hand. Exchange transfers one Dragon to player 0, who discards it and
selects two copies from their own Deck. Player 0's Deck falls from 34 to 32,
player 1's remains at 35, and the discarded card reaches player 1's
Graveyard. The opponent receives the two-card search reveal and remembers
both copies in the opponent-hand multiset. The scripted line is followed by
random legal play until terminal; the complete trajectory serializes,
replay-verifies, and passes the visibility audit. The focused Exchange and
Thunder Dragon native suite passed **5/5 tests**. This establishes the
specific pinned-core behavior, not every Exchange or banish-replacement
interaction.

Reproduce with pinned native assets:

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_historical_thunder_exchange.py \
  tests/test_historical_thunder_dragon.py \
  tests/test_historical_exchange.py
```

### Thunder Dragon under Banisher of the Light (27 October 2026)

The [period Thunder Dragon FAQ](https://www.goatformat.com/rulings7.html)
permits activating its effect even when Banisher of the Light redirects the
discard away from the Graveyard. A seed-3 native fixture Normal Summons
Banisher, discards GOAT Thunder Dragon, and selects two copies from its own
Deck. The discarded copy is face-up banished; none enters its controller's
Graveyard. Its Deck falls from 34 to 32, and only the opponent receives the
two-card search reveal and remembers both copies in hand. The scripted line
continues with random legal choices to a terminal result; the complete
trajectory serializes, replay-verifies, and passes the visibility audit.
The focused Thunder Dragon/Exchange native suite passed **5/5 tests**.
This validates the pinned engine's behavior for one replacement effect, not
all banishment or Exchange interactions.

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_historical_thunder_dragon.py \
  tests/test_historical_thunder_exchange.py
```

### SJC New Jersey Rhymus deck held-out check (27 October 2026)

The [preserved 2005 SJC New Jersey Top 8 list](https://www.goatformat.com/home/top-8-decklists)
prints Rhymus Lizo's 40-card Main Deck and eight-card Fusion Deck. The
[YDK transcription](../examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk)
keeps those exact counts and omits the Side Deck for single duels. Four
focused tests passed: published counts, source names and GOAT whitelist,
and two seat-swapped complete native duels against the Charlotte Zombie
fixture. Both test duels serialized, replay-verified, and passed the
player-visibility audit.

Both Main Deck composition hashes are absent from the current feature-v23
checkpoint's 12 recorded training compositions: Rhymus
`86dcdaea47d58fd7bd1eaaa8849fb6b2cb60aa17fc991d4df11f134bfa21ac00`,
Charlotte Zombie `f8e6e57b95f4eb3927202980931fe2efebbca8fb75a2fa08b76bbfff55eeba67`.
The unchanged checkpoint played Tactical-v14 across seeds 37100–37103,
both Main Deck assignments and policy seats. All **16 duels** reached terminal
before 3,000 decisions (maximum **888**). The policy scored **8–8–0**;
paired-bootstrap 95% score interval **25–75%**. It won **6/8** as first
player and **2/8** as second. This small sample supplies a reproducible
held-out baseline, not evidence of improvement over Tactical-v14.

The ignored report is
`.cache/goat-ai/rhymus_vs_zombie_current_37100_37103.json` (SHA-256
`03659a5f9892b020b5367d87c8e3032b6ef8d48882c41c6482c64569ecf0f3ea`).
Reproduce with pinned native assets:

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_2005_new_jersey_rhymus_deck.py
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --engine experimental \
  --matchup examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk \
    examples/decks/zombie_jae_kim_charlotte_2005.ydk \
  --both-deck-assignments --require-unseen-main-decks --opponent tactical \
  --seed 37100 --seeds 4 --workers 4 --max-decisions 3000 \
  --output .cache/goat-ai/rhymus_vs_zombie_current_37100_37103.json
```

### Separate player-card pools, feature v26 (27 October 2026)

The feature-v23 policy averages all visible state cards into one vector. An
opt-in v26 branch adds separate own/opponent visible-card means through a
zero-initialized residual projection. It uses the same v23 decision inputs,
preserves exact parent logits before training, and leaves hidden-card values
absent from the encoded inputs. A unit test checks exact warm-start logits,
batched-forward equivalence, and a strict parent-version gate.

Matched v23 control and v26 child continuations used the same feature-v23
parent, eight replay-verified fixed-policy games from seed 44000–44003,
437 Tactical-v14 labels on policy-visited states, one epoch, batch size 16,
seed 81, learning rate 0.0002, and identical optimizer settings. Their final
training losses were **0.6391** (v23) and **0.5974** (v26). This is a
training-set fit comparison, not a strength metric. The ignored checkpoints
are `.cache/goat-ai/v23_owner_pool_control_44000_44003.pt` (SHA-256
`852f5704062b65b85c35c0ba539456a12b45bacaba58e3293b97ad1b470e334c`)
and `.cache/goat-ai/v26_owner_pool_child_44000_44003.pt` (SHA-256
`38169149494acf547cc8009e688b357875ef4e39c95403db389677e463050a10`).

On Rhymus New Jersey versus Charlotte Zombie, both Main Deck assignments,
both policy seats, and held-out seeds 37200–37207, v26 scored **13–19**
directly against v23 over 32 terminal duels (paired-bootstrap 95% score
interval **31.25–46.875%**; maximum 873 decisions). It scored **4–12** as
first player and **9–7** as second. This does not justify promoting v26;
the tested continuation was weaker on this matchup. The ignored direct
report is `.cache/goat-ai/v26_owner_pool_vs_v23_rhymus_zombie_37200_37207.json`
(SHA-256 `c427082b577ab498b627e8e78cd7089c24f512947dbe6fe5dc60a8ce5c275a96`).
Neither deck composition occurs in either child's training provenance.

Reproduce the control and child with `scripts/train_behavioral_clone.py` on
`.cache/goat-ai/fixed_policy_value_44000_44015/matchup_00_seed_4400[0-3]_seat_*.json`
using `--on-policy-teacher tactical_v14 --engine experimental --init-checkpoint
.cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt --epochs 1
--batch-size 16 --batched-forward --omit-forced-forward --verification-workers 4
--width 32 --learning-rate 0.0002 --seed 81`; use `--feature-version 23`
for the control and `--feature-version 26 --upgrade-feature-23-to-26` for
the child, with distinct ignored output paths. Evaluate with
`scripts/evaluate_policy.py --engine experimental --opponent-checkpoint
.cache/goat-ai/v23_owner_pool_control_44000_44003.pt --matchup
examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk
examples/decks/zombie_jae_kim_charlotte_2005.ydk --both-deck-assignments
--require-unseen-main-decks --seed 37200 --seeds 8 --workers 4
--max-decisions 3000` and the v26 checkpoint as the positional argument.

### Action-conditioned visible-card attention, feature v27 (27 October 2026)

The current feature-v23 policy uses one mean of visible cards for every legal
action. An opt-in v27 branch lets each action attend to the player-visible
cards before scoring it. The residual output starts at zero, so loading the
selected v23 checkpoint preserves its exact initial logits; a unit test also
checks mixed-length padded batches after the attention weights become nonzero.
The branch reads only `encode_decision` inputs, with unknown opponent cards
still represented by unknown identities. It does not inspect native hidden
state or change the default inference policy.

A matched continuation used the same eight replay-verified fixed-policy games
and **437** Tactical-v14 labels as the [v23/v26 control](#separate-player-card-pools-feature-v26-27-october-2026), with one epoch,
batch size 16, seed 81, and learning rate 0.0002. The v27 training loss was
**0.6069**, versus **0.6391** for the prior matched v23 control. This measures
fit on synthetic teacher decisions only. The ignored checkpoint is
`.cache/goat-ai/v27_attention_child_44000_44003.pt` (SHA-256
`03d4ebd9880210c0f73f1a5442011a7a655b92eb086b98885794e60dca24ebbe`).

Against that exact v23 control on held-out Rhymus 2005 Goat Control/Charlotte
Zombie, seeds 37200–37207 with both deck assignments and seats, v27 scored
**13–19** over 32 terminal duels (paired-bootstrap 95% score interval
**31.25–50%**). On held-out Phoenix 2005 Control/WikiFormat Dimension Fusion
under the same balanced schedule, it scored **19–13** (interval
**46.875–71.875%**). The two point scores sum to 32–32, and each family's
interval includes 50%; the result does not establish a robust improvement.
The four exact Main Deck compositions are absent from both checkpoints'
training provenance; `load_report(..., require_unseen_main_decks=True)`
validated both reports. The local report hashes are respectively
`71b8c98e89c33eac7877c745d6675a2ecbacff19514af0b3989ab55ec1c78959`
and `c8b006dc32d45db63a5818ecbddb3c6b654e3beea6752ca84bbde875964f5bc7`.
This is a direct checkpoint comparison, not a claim that v27 beats Tactical.

Reproduce from the pinned native setup with `OMP_NUM_THREADS=1 PYTHONPATH=src:.`:

```bash
.venv/bin/python scripts/train_behavioral_clone.py \
  .cache/goat-ai/fixed_policy_value_44000_44015/matchup_00_seed_4400[0-3]_seat_*.json \
  --on-policy-teacher tactical_v14 --engine experimental \
  --init-checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --epochs 1 --batch-size 16 --batched-forward --omit-forced-forward \
  --verification-workers 4 --width 32 --learning-rate 0.0002 --seed 81 \
  --feature-version 27 --upgrade-feature-23-to-27 \
  --output .cache/goat-ai/v27_attention_child_44000_44003.pt
.venv/bin/python scripts/evaluate_policy.py \
  .cache/goat-ai/v27_attention_child_44000_44003.pt \
  --engine experimental \
  --opponent-checkpoint .cache/goat-ai/v23_owner_pool_control_44000_44003.pt \
  --matchup examples/decks/goat_control_rhymus_lizo_new_jersey_2005.ydk \
            examples/decks/zombie_jae_kim_charlotte_2005.ydk \
  --both-deck-assignments --require-unseen-main-decks \
  --seed 37200 --seeds 8 --workers 4 --max-decisions 3000 \
  --output .cache/goat-ai/v27_attention_vs_v23_rhymus_zombie_37200_37207.json
```

Repeat the evaluator with the Phoenix/WikiFormat deck paths and a distinct
output file for the second held-out family. Keep v23 selected pending a gain
across deck families and against baselines.

### Tournament-card private-draw differential (27 October 2026)

A native regression varies only one card at the seeded draw slot of player
1's 40-card Main Deck. The 59 candidates are distinct Main Deck IDs from the
project's sourced tournament-deck corpus absent from the shared Normal Monster
fixture. Seed 52 leaves that slot out of player 1's opening hand and draws it
privately on turn two. The test confirms the same opening hand in every
variant, the changed private hand after the draw, and equality of **every
player-0 observation and legal-action set** from the opening through player
0's turn-three Main Phase while both players take the same passive public
actions. All 59 variants passed on the pinned experimental adapter; the
measured pytest run took 2.84 s on this host.

This is a differential information-flow check across 59 competitive card IDs,
including GOAT-specific variants. It does not test those cards' effects,
choices after the public game diverges, or the opponent's own legal actions.
Reproduce it after native setup with:

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_historical_private_draw_pool.py
```
### Native worker scaling on sourced decks (27 October 2026)

Eight RandomAgent duels used Matt Peddle's sourced 2005 Goat Control Main Deck
against the sourced Riclar 2020 Chaos Turbo Main Deck, paired across seats on
seeds 49800–49803. The pinned experimental native adapter, identical decks and
assets, a 3,000-decision cap, and `OMP_NUM_THREADS=1` were held fixed. Runs
were sequential on an Intel Core i7-10700K with 16 logical CPUs and 46 GiB of
RAM. Every game reached terminal; all three worker counts produced the same
winners and **8,150 total decisions**, including identical per-game decision
counts. Wall time includes process spawn and shutdown.

| Spawned workers | Wall time | Duels/s | Decisions/s | Mean reset/duel | Sum of worker peak RSS |
|---:|---:|---:|---:|---:|---:|
| 2 | 2.691 s | 2.973 | 3,028 | 61.1 ms | 118,308 KiB |
| 4 | 1.518 s | 5.271 | 5,369 | 64.0 ms | 229,352 KiB |
| 8 | 1.125 s | 7.112 | 7,246 | 87.7 ms | 447,036 KiB |

The sums combine each worker's Linux `VmHWM`, so they are **not** simultaneous
machine-wide memory peaks. Parent peak RSS was 26,680, 26,568, and 26,388 KiB
respectively. These are single short runs, not confidence intervals for
throughput or a forecast for long training; they exclude neural inference,
trajectory writing, and verification. On this schedule eight workers were
2.39 times as fast as two, with 3.78 times the summed worker high-water
memory. Larger schedules and inference batching still need measurement.

Reproduce from the pinned native setup at commit `0d14fc1` with:

```bash
for workers in 2 4 8; do
  OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
    scripts/benchmark_parallel_native.py \
    --deck-a examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk \
    --deck-b examples/decks/chaos_turbo_riclar_2020.ydk \
    --seed 49800 --games 8 --workers "$workers" \
    --output ".cache/goat-ai/parallel_2005_matt_chaos_49800_${workers}w.json"
done
```

The ignored report SHA-256 values, in worker-count order, are
`5008ead844418a40da0197e1b829dc167187486363072fafa158da2109e09ac6`,
`cffec29a48b0c911fca20f6eb7e63d0b12d2b375dd2c35d918b5d127cbda3cdb`,
and `2d21a57a4e7f0467579a04f0191595be3fc937c40349e2e2fc393587986790a4`.
### Four versus eight cloning verification workers (27 October 2026)

The [native duel scaling pilot](#native-worker-scaling-on-sourced-decks-27-october-2026)
measured pure RandomAgent simulation. This check measures the **actual cloning
command** on eight replay-verified current-core self-play trajectories from
seeds 34000–34007 (2,023 fit decisions). Each arm started from the same
feature-v23 checkpoint, used one epoch, width 32, batch size 16, batched
forward, omitted forced forwards, learning rate 0.0002, seed 58, and one
Torch thread. Four runs were ordered 4, 8, 8, 4 verification workers to
reduce simple order bias. Source replays and their labels were unchanged.

| Run | Verification workers | External wall time | CLI verification time | CLI fitting time |
|---:|---:|---:|---:|---:|
| 1 | 4 | 7.031 s | 2.552 s | 1.775 s |
| 2 | 8 | 7.143 s | 2.791 s | 1.591 s |
| 3 | 8 | 7.047 s | 2.724 s | 1.572 s |
| 4 | 4 | 6.913 s | 2.611 s | 1.571 s |

The two 4-worker runs averaged **6.972 s** externally; the 8-worker runs
averaged **7.095 s**. Verification itself averaged 2.582 versus 2.758 s.
The observed 0.123-second external difference is small and from two runs
per arm, so it is a workload-specific point result, not a general scaling
law. All four checkpoints recorded the same `0.14908188252774301` epoch
loss, identical source hashes, and byte-equal values for all 38 model-state
tensors. More verification workers did not change the policy. Four remains
the measured choice for this eight-replay job; a larger corpus might have
a different optimum. This check does not measure playing strength.

The ignored logs and checkpoints are in
`.cache/goat-ai/verify_workers_34000_34007/`. Reproduce each arm from the
pinned native setup with the eight
`current_broader_ppo_34000_34063_replays/episode_0000[0-7]_seed_*.json`
files and:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/train_behavioral_clone.py \
  .cache/goat-ai/current_broader_ppo_34000_34063_replays/episode_0000[0-7]_seed_*.json \
  --engine experimental \
  --init-checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --epochs 1 --batch-size 16 --batched-forward --omit-forced-forward \
  --verification-workers 4 --width 32 --feature-version 23 \
  --learning-rate 0.0002 --seed 58 \
  --output .cache/goat-ai/verify_workers_34000_34007/reproduction.pt
```

Change only `--verification-workers` and the output path for the other arm.
The four saved log SHA-256 values, in run order, are
`70349e2183af9dd5077725a904fdba339701bc9534930543d954d9613bfa5257`,
`94adf784254eb1e470efcb974c96dfd3f53393bb46cb09233f6a0df4d27f7686`,
`ab3a92f193dc9691f3f793d0c86d022828afbad6b19a20c5873d840ad982e1b0`,
and `b46bf5a7fbc7223de91065096df8a59dbdf82b0892e871a49bbd89a918b8ae3a`.
### Current-core 32-game on-policy Tactical continuation (27 October 2026)

The selected feature-v23 policy had 32 current-core policy-versus-Tactical-v14
replays on Jesse Twohig 2005 Goat Control versus Montague Warrior, both policy
seats and seeds 44000–44015. These decks occurred in the parent training
provenance, but these **policy-visited states** were new to that checkpoint.
The trainer independently replay-verified all 32 full duels, audited
player-visible observations, and assigned Tactical-v14 choices at **2,293
multi-option decisions**. The synthetic teacher is a baseline, not a human
demonstrator. A single unweighted continuation used two epochs, batch size
16, feature v23, width 32, learning rate 0.0001, seed 82, batched forward,
forced-forward omission, and four native verification workers. The two epoch
losses were **0.6311** and **0.4295**; CLI wall time was 13.48 seconds,
including 4.85 seconds of verification and 3.72 seconds of fitting. The
ignored child checkpoint is
`.cache/goat-ai/fv23_current_on_policy_jw_44000_44015.pt` (SHA-256
`9696034b14bd07638555ef80ca499c28e3cf1976b397a462238a74f8a3f00de6`).

Held-out evaluation used two independent deck pairs absent from both
checkpoints' Main Deck composition provenance, both deck assignments and
policy seats, four workers, the same native assets, and a 3,000-decision cap.
Every duel reached terminal. The child scored **16–14–2** directly against
the unchanged parent on Rhymus 2005 Goat Control/Charlotte 2005 Zombie,
seeds 49900–49907; its paired 95% score interval was 35.9375–71.875%. On
Phoenix 2005 Control/WikiFormat Dimension Fusion, seeds 50000–50007, the
child scored **14–18**, interval 34.375–56.25%. Neither direct comparison
establishes an improvement.

Against Tactical-v14 on matched fresh seeds 49908–49915, the child and
parent each scored **9–23** on Rhymus/Zombie. The paired child-minus-parent
score difference was zero, with a 95% interval of −9.375 to +9.375 points.
On Phoenix/Dimension Fusion, seeds 50008–50015, the child scored **6–26**
and the parent **9–23**; the paired difference was −9.375 points, interval
−21.875 to +3.125. The saved-report comparator verified the matching
opponent, assets, scripts, source, seeds, local deck hashes, and unseen Main
Deck compositions. More fitting of this synthetic teacher on these states
did not transfer into a measured competitive gain. Retain the unchanged v23
parent; this child is an experimental negative result, not a self-play
improvement.

Reproduce the child with the current native setup:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/train_behavioral_clone.py \
  .cache/goat-ai/fixed_policy_value_44000_44015/matchup_00_seed_440*_seat_*.json \
  --engine experimental --on-policy-teacher tactical_v14 \
  --init-checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --epochs 2 --batch-size 16 --batched-forward --omit-forced-forward \
  --verification-workers 4 --width 32 --feature-version 23 \
  --learning-rate 0.0001 --seed 82 \
  --output .cache/goat-ai/fv23_current_on_policy_jw_44000_44015.pt
```

The six ignored tournament reports use prefix `current_on_policy_jw_` in
`.cache/goat-ai/`; their SHA-256 values are
`4297ca6e7d6a76baaecc07b92a4370f6ea8af6889ea4e8dc0e522e2a7db751a5`
and `0f34fba244f633f4e8b8e7e3778bf1a2119d741dc6b050ca277b41d11652db1c`
for the direct Rhymus and Phoenix comparisons; and, in child/parent order,
`ce842eeec36791d1e853ce9298118d09ebb5d52c411697986096916e2f1535e0` /
`614060791a0499a9bc6a44ebd5b6b6c9d7deccf7e13bef7c005954637d25ca02`
for Rhymus Tactical, and
`c5dd5a07e5cf90df09e54d685f75411a5de4796705c6e98535e8740e9b2b528e` /
`c1d6cde278c953b21d467b5572411089b08eb4e5be01b936f76f2d7bc146ca4b`
for Phoenix Tactical.

### Strict Heavy Storm card-advantage ablation (27 October 2026)

The existing opt-in `tactical_card_advantage` variant filters Heavy Storm when
its visible opposing backrow count does not exceed the friendly cards it
would destroy. Its other decisions use Tactical v14. On the 64 previously
replay-verified current-core policy duels at
`.cache/goat-ai/fixed_policy_value_44000_44015/`, Heavy Storm was a legal
activation in 311 of 31,729 recorded decisions; the strict guard changed
Tactical's selected action in 48 decisions across 16 duels. This is an
offline disagreement count on policy-visited states, not a win-rate result.

In a predeclared head-to-head evaluation against unchanged Tactical v14, the
variant scored **119 wins, 119 losses, and 2 draws** over 240 terminal games:
all 15 pairings of six sourced tournament Main Decks, both deck assignments,
both seats, and seeds 55000–55003. Its score was **50.0%**, with a paired
bootstrap 95% interval of **48.75–51.25%**. First-seat score was 58.75%; the
second-seat score was 41.25%, illustrating the seat effect rather than a
guard advantage. There were 100,780 decisions, maximum 1,425 in one game.
The four-worker tournament took a measured 15.687 seconds on the logged
Linux x86_64 host. These sampled experimental-core games do not establish a
playing-strength gain or historical-ruling correctness. Keep the guard
opt-in and do not promote it as the demonstration teacher.

The evaluator initially mislabeled the named Tactical variant as teacher
version 1. Its report metadata now records both sides as base Tactical v14;
the variant name distinguishes the extra guard. Rerunning after that fix
produced exactly the same 240 game records. The corrected ignored report is
`.cache/goat-ai/card_advantage_vs_tactical_55000_55003_corrected.json`
(SHA-256 `5cc7f681af3e90ee307977925c3cae3711652de989ab055a92f90a579fd082da`).
It includes the source, native asset, script-tree, deck, and schedule hashes.
Reproduce from the pinned native setup with:

```bash
GOAT_AI_NATIVE_ROOT=.cache/goat-ai OMP_NUM_THREADS=1 PYTHONPATH=src:. \
  .venv/bin/python scripts/evaluate_native.py \
  --native-root .cache/goat-ai --engine experimental \
  --tournament-corpus --both-deck-assignments \
  --agent-a tactical_card_advantage --agent-b tactical \
  --seed 55000 --seeds 4 --workers 4 --max-decisions 3000 \
  --output .cache/goat-ai/card_advantage_vs_tactical_55000_55003_corrected.json
```

### Further distinct-whitelist protocol sweep (27 October 2026)

Starting from project commit `f1814a3`, a new full GOAT-whitelist sample used
100 independent Main Deck pairs on seeds 30250–30349. All **100/100** native
duels reached terminal below the 3,000-decision cap, with a maximum of 1,873
decisions. Every one of the **106,181** decisions replay-verified against a
fresh engine; the player-visible action audit checked all 100 games, including
868 hidden-field, 4,782 opponent-field, and 118 opponent-hand choice contexts.
The 200 generated Main Decks had distinct hashes and covered 1,624 distinct
card IDs. The report records 1,309 loaded native assets. Relative to the
immediately preceding seeds 30150–30249 report, 15 official card scripts
were newly loaded, including Dark Mirror Force, Fusion Gate, Good Goblin
Housekeeping, and The Creator. Loading a script is not proof that its effects
or historical rulings were exercised correctly.

The ignored report is
`.cache/goat-ai/whitelist_distinct_30250_30349/report.json` (SHA-256
`305f592678684f329cb460c35be5f4bbddf585a603fe92587f96cd6d5cf51135`).
Its deck, asset, rules-profile, action-count, and per-game outcome fields
support reproduction with the pinned native setup. The probe script SHA-256
was `cf66160dfc23d00c75de3b55f8b4f278c49d80141d35d4aa138a3934539dd044`.
This is sampled M1 protocol evidence, not a certificate of arbitrary-deck
completeness, GOAT card-ruling correctness, or agent strength.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/whitelist_distinct_30250_30349 \
  --seed 30250 --seeds 100 --max-decisions 3000 \
  --verify-replays --distinct-opponents --count-card-actions
```

### Current-core imitation child on a different 2005 holdout (27 October 2026)

The current-core feature-v23 Tactical imitation child from seeds 33000–33031
was compared with its unchanged parent on a different 2005 deck family:
Rhymus Lizo's New Jersey Goat Control Main Deck versus Jae Kim's Charlotte
Zombie Main Deck. Both Main Deck compositions were excluded from both
checkpoints' training provenance. The direct tournament used both deck
assignments and policy seats, seeds 56000–56015, four workers, and the pinned
experimental core. All 64 games reached terminal below 3,000 decisions.
The child scored **33–29–2** against its parent, a 53.1% score with paired
95% interval **40.6–64.8%**. Its assigned-deck split was 20–10–2 on Rhymus
and 13–19 on Zombie. The direct interval includes 50%, so this is not a
demonstrated direct strength gain.

On separate matched seeds 56016–56031 against Tactical-v14, the child scored
**29–35** and the parent **22–42** over 64 games each. The paired child-minus-
parent score difference was **+10.9 percentage points**, with 95% interval
**−4.7 to +28.1 points**. The report comparator checked identical native
assets, card scripts, source code, opponent, seeds, local deck hashes, and
unseen Main Deck compositions. The child improved from 18–14 to 22–10 on
Rhymus and from 4–28 to 7–25 on Zombie, but the paired interval still
includes zero. Together with the earlier Phoenix/Dimension Fusion results,
this supports further evaluation of the imitation child; it does not close
M4's cross-family direct or self-play gain gates. The selected reference is
unchanged.

The three ignored reports are
`.cache/goat-ai/current_child_vs_parent_rhymus_zombie_56000_56015.json`,
`.cache/goat-ai/current_child_vs_tactical_rhymus_zombie_56016_56031.json`,
and `.cache/goat-ai/current_parent_vs_tactical_rhymus_zombie_56016_56031.json`.
Their SHA-256 values are respectively
`fb8c07c3685259277c0b74f91d8a08a37d28967750bbeb870d40da214ad1d8e1`,
`8d503100fe0f13ca5ed51dd47bdfe08690d3bf7470e6f6b5b33c18cab1ec46e5`,
and `1384482cc878cde617a73acb28bf89ef81e3f78e8927a057b657f240de5d81e5`.
Reproduce with `scripts/evaluate_policy.py --engine experimental
--both-deck-assignments --require-unseen-main-decks --workers 4
--max-decisions 3000`, the named checkpoints and matchup, seeds 56000/56016
with `--seeds 16`, and respectively `--opponent-checkpoint` or
`--opponent tactical`. Compare the matched Tactical reports with
`scripts/compare_tournament_reports.py --require-unseen-main-decks`.

## On-policy Tactical labels on mixed tournament cards (28 October 2026)

To address the distribution mismatch of the four-duel off-policy imitation
trial, a new collection let the selected feature-v23 policy play Tactical-v14
on eight independently generated, legal tournament-card deck pairs (source
deck seeds 11020–11027). Duel seeds 61000–61001 and both policy seats produced
**32 complete, native replay-verified and visibility-audited duels with 16,708
decisions**. The ignored manifest is
`.cache/goat-ai/on_policy_mix_11020_11027_61000_61001/manifest.json` (SHA-256
`c5c71389359aac1664d4392780506351d1b375cea70ebb0a50e661af7958d001`).
The policy-visited states were labeled by the synthetic Tactical-v14 teacher,
not by a human. The cloning trainer replay-verified them again and fit **3,018
multi-option teacher decisions** for one epoch (feature v23, width 32,
batch 16, learning rate 0.0001, seed 61000). The experimental checkpoint is
`.cache/goat-ai/fv23_on_policy_mix_61000_61001.pt` (SHA-256
`988c1b409462be6a514223e772932307c2d125671ed6d00678e5dbf60a04cfa7`).

A separate set of ten generated deck pairs (source seeds 11010–11019) had
**20 distinct Main Deck compositions absent from both checkpoints' training
provenance**. Across both deck assignments, both seats, and duel seeds
62000–62001, the child scored **36–44** directly against its frozen parent
(paired score interval **33.8–56.3%**). On matched duel seeds 62002–62003,
the child scored **21–59** against Tactical and the parent **17–63**. The
validated paired child-minus-parent Tactical score difference was **+5.0
percentage points**, 95% interval **−5.0 to +15.0 points**. Neither check
establishes a gain; the child is not promoted. More synthetic teacher labels
on policy-visited states alone have not closed M4's strength gate.

The ignored direct, child-versus-Tactical, and parent-versus-Tactical reports
are respectively
`.cache/goat-ai/fv23_on_policy_mix_direct_62000_62001.json` (SHA-256
`99b82522b072fd7db6399509f9dbda69eb531654b59fed45dfdbeeef189a7c38`),
`.cache/goat-ai/fv23_on_policy_mix_child_tactical_62002_62003.json` (SHA-256
`01c4896c74c934f9271e00694f6eab34c17af4d3af828e6409916d908cd687b9`),
and `.cache/goat-ai/fv23_on_policy_mix_parent_tactical_62002_62003.json`
(SHA-256 `53a88f8fbd67a903fae19c696eb9283d2109ba54f84eb079bef3a51994891c45`).
Collection used `scripts/collect_policy_matches.py --opponent tactical
--seed 61000 --seeds 2 --workers 4 --max-decisions 3000` with eight
`--matchup` pairs from the isolated probe and the selected v23 checkpoint.
Training used `scripts/train_behavioral_clone.py` on those 32 trajectory
files with `--engine experimental --on-policy-teacher tactical_v14
--init-checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt
--feature-version 23 --width 32 --epochs 1 --batch-size 16 --batched-forward
--skip-forced-training --verification-workers 4 --learning-rate 0.0001
--seed 61000`. Evaluation used `scripts/evaluate_policy.py --engine
experimental --both-deck-assignments --require-unseen-main-decks --seeds 2
--workers 4 --max-decisions 3000` with the ten held-out `--matchup` pairs
above, followed by `scripts/compare_tournament_reports.py
--require-unseen-main-decks` for the matched Tactical arms.

### Action-conditioned attention on the same on-policy labels (28 October 2026)

The opt-in feature-v27 action-attention policy was trained on the **same 32
replay-verified games, 3,018 Tactical-v14 labels, one epoch, batch size 16,
seed, and learning rate** as the feature-v23 child above. Its v23 weights
were imported through the zero-output attention upgrade. Its training loss
was **0.5648**, versus **0.5783** for the matched v23 child, but this is
synthetic-teacher fit, not playing strength. The ignored v27 checkpoint is
`.cache/goat-ai/fv27_on_policy_mix_61000_61001.pt` (SHA-256
`4b4da683197090054c1e9746996d1cb1bf04fb28eb47d637f3ca05a21191efdf`).

On the same 20 training-unseen mixed Main Deck compositions with fresh duel
seeds 63000–63001, v27 scored **36–44** directly against its matched v23
child (paired score interval **37.5–52.5%**). On separate matched Tactical
seeds 63002–63003, v27 scored **23–57** and v23 **22–56–2**, both a **28.75%**
score. The validated paired v27-minus-v23 Tactical score difference was
**0.0 points**, 95% interval **−5.0 to +6.25 points**. The attention branch
does not establish a competitive gain on this schedule and remains
experimental; neither child replaces the selected v23 parent.

The ignored direct, v27-versus-Tactical, and v23-versus-Tactical reports are
`.cache/goat-ai/fv27_vs_v23_on_policy_mix_direct_63000_63001.json` (SHA-256
`c7e4351041734c0966dd231a9cd6a9a2d1aecefd35866b837f1619f70369b112`),
`.cache/goat-ai/fv27_on_policy_mix_tactical_63002_63003.json` (SHA-256
`26163d6138e60d896f040924ea3fa7086fc251d548a1c9d2d9399a8b72442e88`),
and `.cache/goat-ai/fv23_on_policy_mix_tactical_63002_63003.json` (SHA-256
`6724b0213ec846bdc700d118491bf52c36d1d6d7876de68b313d6314755ce1f1`).
Reproduce the v27 fit with the preceding cloning command, replacing
`--feature-version 23` by `--feature-version 27
--upgrade-feature-23-to-27`, and evaluate with the same ten held-out deck
pairs, both assignments and seats, and the fresh seeds above. The matched
Tactical reports passed `scripts/compare_tournament_reports.py
--require-unseen-main-decks`.

### Longer fit on the same on-policy Tactical labels (28 October 2026)

To test whether the one-epoch result was simply underfit, feature v23 was
retrained from the same selected parent and the same 32 verified policy-visited
duels for **three epochs**. The 3,018 multi-option synthetic Tactical-v14
labels and all other training settings were unchanged. Epoch losses were
**0.5783, 0.4796, and 0.4480**. The experimental checkpoint is ignored local
data at `.cache/goat-ai/fv23_on_policy_mix_3epoch_61000_61001.pt` (SHA-256
`5ace8a82f250c42a00de858032cb2e34287648b72a967cb65282c9364c393991`).

On the same 20 Main Deck compositions absent from both checkpoints' training
provenance, but fresh duel seeds 64000–64001, the three-epoch child scored
**42–38** directly against the selected parent over 80 games (paired score
interval **45.0–58.75%**). On a separate matched Tactical-v14 schedule with
seeds 64002–64003, the child scored **24–55–1** and the parent **27–53**.
`compare_tournament_reports.py --verify-local-decks
--require-unseen-main-decks` validated the schedule and reported a paired
child-minus-parent score difference of **−3.125 percentage points**, 95%
interval **−12.5 to +5.625 points**. Lower teacher-label loss did not
establish a competitive improvement; the selected parent stays unchanged.

The ignored direct, child-versus-Tactical, and parent-versus-Tactical reports
have SHA-256 values `44710600aaa6043f5f0ebc1c170fe345f865e13e3144e5c13951f89e510ae952`,
`6628ec161e92a33c41f09fe4d4401e0851318f2f0e62bcea1f7cdd4583dbb83f`, and
`093dd23092c967dc95e448d208b2337183a72effc784610b335d4e0df96955b4`
respectively. To reproduce the fit, use the preceding on-policy cloning
command with `--epochs 3`, the same 32 trajectory files, and the checkpoint
path above. Evaluate the ten generated deck pairs from source seeds
11010–11019 with both deck assignments and seats, two duel seeds per pair,
and `--require-unseen-main-decks`; use seeds 64000–64001 for the direct parent
match and 64002–64003 for both Tactical arms. This remains an automated
teacher experiment, not human imitation data.

### Half-Tactical PPO continuation from the current-core child (27 October 2026)

A new clipped-PPO trial began from the current-core Tactical-imitation child,
using the same Jesse Goat Control/Warrior four-role training family but new
seeds 57000–57127. Compared with the earlier 64-duel trial, this one used
128 games, a 50% frozen-snapshot probability, a Tactical-v14 opponent in the
other 50%, and learning rate 0.00005. It retained four-game frozen rollouts,
four workers, two PPO epochs, batch 32, per-episode weighting, learner-deck
baseline, and parent KL weight 0.5. Exactly 64 games sampled Tactical and 64
sampled historical policy snapshots. All 128 reached terminal below 3,000
decisions, with no censored or unsupported games. The sampled learner went
47–80–1 over those mixed training opponents; this is not a strength estimate.
The trainer reported 45.45 seconds and 9,962 learner decisions. Independent
native replay verification and player-visible auditing passed all 128 saved
trajectories, covering **63,275 decisions**.

Held-out evaluation used two Main Deck pairings absent from both checkpoints'
training compositions: Rhymus Goat Control/Charlotte Zombie and Phoenix
Control/WikiFormat Dimension Fusion. It covered both deck assignments and
policy seats, four workers, seeds 57200–57215 for the direct match and
57216–57231 for matched Tactical-v14 comparisons. Every game reached terminal.
The PPO child scored **61–66–1** directly against its parent over 128 games,
a 48.0% score with paired 95% interval **42.6–52.7%**. Against Tactical, the
child scored **46–81–1** and the parent **44–84** on 128 matched games each.
The validated paired child-minus-parent difference was **+2.0 percentage
points**, interval **−2.3 to +6.3**. The direct and matched intervals include
no gain. This trial does not satisfy M4's self-play improvement gate, and the
selected checkpoint stays unchanged. Increasing Tactical exposure in this
mixture did not produce a measured held-out gain.

The ignored PPO checkpoint is
`.cache/goat-ai/current_ppo_half_tactical_57000_57127.pt` (SHA-256
`9076728d82a8b4aa82548eddd4dd34daead456b84c6d60c1fc9f55f0c6ab9706`).
The 128-replay audit at
`.cache/goat-ai/current_ppo_half_tactical_57000_57127_audit.json` has SHA-256
`5c38d933dab6bc41e427016f8eda38fdd9837bf31a007a392a00a5545a5b0fe3`.
The direct, child-versus-Tactical, and parent-versus-Tactical report SHA-256
values are respectively
`1e46ba053374011da000dc98196cf91845155c7d203c1906ed1fbaf24ccae2a9`,
`d2f07bbda6eda2dd847d510004efec74f455b78316e9c1784d3a4908e4e88288`,
and `6bf78eec4d35f4a3cac142d190ebcd600f3c5174706a7b7236bee5a7dfd0c43c`.
Reproduce training with `scripts/train_self_play.py` and the parent above,
`--engine experimental --schedule-mode four_roles --seed 57000 --games 128
--max-decisions 3000 --policy-update clipped_ppo --ppo-rollout-games 4
--ppo-epochs 2 --ppo-batch-size 32 --ppo-rollout-weighting per_episode
--baseline-scope learner_deck --snapshot-every 4 --parent-kl-weight 0.5
--historical-probability 0.5 --baseline-opponent tactical --rollout-workers 4
--learning-rate 0.00005`, and the Jesse/Warrior matchup named above. Audit
with `scripts/audit_selfplay_replays.py`, then evaluate with
`scripts/evaluate_policy.py --both-deck-assignments --require-unseen-main-decks
--workers 4 --seeds 16` on the named holdouts and seed blocks. Compare the
two Tactical reports with `scripts/compare_tournament_reports.py
--require-unseen-main-decks`.

## Additional distinct-opponent GOAT protocol sweep (27 October 2026)

On project commit `55f0df3` and the pinned native assets, RandomAgent completed
50/50 further GOAT-whitelist duels on seeds 10456–10505, each against an
independently generated legal 40-card opponent deck. No duel hit the
3,000-decision cap or raised an adapter error; the longest took 1,497
decisions. Fresh-engine replay verification and the player-visible audit
passed for all 48,741 decisions, including 412 hidden-field choices and 24
opponent-hand choices. The run loaded 1,182 native assets and offered 3,967
card-source/action-kind pairs. Compared with the prior local 100-duel
whitelist report for seeds 10356–10455, it loaded ten previously unobserved
official card scripts, including D.D. Designator and Mystic Swordsman LV6.

The ignored report is
`.cache/goat-ai/whitelist_distinct_10456_10505/report.json` (SHA-256
`42ebe730b011d3c9e44e63cccef0046f434c85a39d043352fac44d7d157ccbaa`).
It records every generated Deck hash, the GOAT rules profile, core/database
hashes, and each loaded script hash. Reproduce after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/whitelist_distinct_10456_10505 \
  --seed 10456 --seeds 50 --max-decisions 3000 \
  --verify-replays --distinct-opponents --count-card-actions
```

This extends M1 protocol evidence only. Random decks and random decisions do
not validate each card's historical ruling or establish playing strength.

## Chain-order native protocol sweep (27 October 2026)

A fresh 50-duel GOAT-whitelist sweep on seeds 10506–10555 initially stopped at
seed 10527 after 606 decisions. The pinned core emitted `MSG_SORT_CHAIN` (21)
for a two-way ordering of Dark Elf's and Toll's attack payments; no chain
links were present at that decision. The adapter had decoded `MSG_SORT_CARD`
(25) but not this same-layout ordering request. The native decoder now exposes both orders as structured
`sort_cards` actions, and the visibility audit checks any opponent cards in
those ordered choices. Both order choices reach terminal in a focused
seed-10527 fixture; their full trajectories replay-verify and pass the
player-visible audit. Both orders pay 1,500 LP in total, from 3,300 to 1,800.
This is protocol support, not a historical ruling claim about every simultaneous
cost or trigger.

After the change, **50/50** duels reached native terminal outcomes without
errors or the 3,000-decision cap. All **50,084** decisions replay-verified and
passed the visibility audit, including 528 hidden-field choices and 28
opponent-hand choices. The longest duel took 1,463 decisions; seed 10527
completed in 715. The report records 1,201 loaded native assets and 4,100
card-source/action-kind pairs. The ignored report is
`.cache/goat-ai/whitelist_distinct_10506_10555_sort_fixed/report.json` (SHA-256
`fb7b6142f90745606afc34cfc1c3e856762964a48f485bfe23adb5442d44dd31`).
Reproduce after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/whitelist_distinct_10506_10555_sort_fixed \
  --seed 10506 --seeds 50 --max-decisions 3000 \
  --verify-replays --distinct-opponents --count-card-actions
```

## Local full-suite and lint gate (27 October 2026)

On commit `3cb3c6b` with `GOAT_AI_NATIVE_ROOT=.cache/goat-ai`, Python 3.12.3,
PyTorch 2.5.1+cpu, and the pinned native assets, the documented full command
`PYTHONPATH=src:. .venv/bin/python -m pytest -q` finished with **1,296 passed**
in **909.17 seconds**. It emitted six PyTorch `TracerWarning` messages from
three traced-rollout tests and no test failures. The run does not prove all
historical card rulings or competitive policy strength.

The next local lint command, `.venv/bin/ruff check .`, found 30 existing
findings across import ordering, closure capture, exception style, and simple
control flow. After safe formatting and contract-preserving fixes, the same
lint command passed. The 66 tests covering the touched files and related
scripts passed in 58.66 seconds with the pinned native assets. The full
1,296-test suite was not repeated after these lint-only edits; this section
keeps the two verification scopes distinct.

## Further distinct-whitelist protocol sweep (27 October 2026)

On the current adapter, seeds 10556–10605 paired 50 independently generated,
whitelist-legal 40-card Main Decks with 50 different opponent decks. All
**50/50** games reached native terminal outcomes without an adapter error or
the 3,000-decision cap. All **56,827** decisions replay-verified against fresh
pinned engines and passed the player-visible information audit. The longest
duel took 1,731 decisions. The audit observed 579 hidden-field choices, 2,814
opponent-field choices, and 14 opponent-hand choices. The report records 1,198
loaded native assets, 4,282 card-source/action-kind pairs, and 35 selected
chain-response pairs. Its ignored artifact is
`.cache/goat-ai/whitelist_distinct_10556_10605/report.json` (SHA-256
`ce1afbd533b67ec634d5a152eaa637727ee51a427ee3633d2e19332afd1cc7c9`).
Compared with the preceding 10506–10555 sweep, this run loaded 102 previously
unseen native assets and offered 1,237 new card-source/action-kind pairs. The
combined two-sweep totals are 1,303 loaded assets and 5,337 such pairs;
all shared loaded-asset hashes agree. No new action kind appeared.
Reproduce after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/whitelist_distinct_10556_10605 \
  --seed 10556 --seeds 50 --max-decisions 3000 \
  --verify-replays --distinct-opponents --count-card-actions
```

This is additional M1 protocol and observation evidence from random decks and
random decisions. It does not validate every sampled card's historical ruling
or measure competitive playing strength.

## Third consecutive distinct-whitelist protocol sweep (27 October 2026)

Seeds 10606–10655 paired 50 independently generated, whitelist-legal
40-card Main Decks with 50 different opponent decks. All **50/50** games
reached native terminal outcomes below the 3,000-decision cap. All **52,875**
decisions replay-verified and passed the player-visible information audit.
The longest game took 1,551 decisions. The audit counted 538 hidden-field,
2,652 opponent-field, and 36 opponent-hand choices. This report has 1,204
loaded native assets, 4,042 card-source/action-kind pairs, and 24 selected
chain-response pairs. It exercised `disable_zones` again; it found no
previously unsupported action kind. Compared with the preceding sweep, 109
loaded assets and 1,084 card-source/action-kind pairs were new. Across the
three consecutive sweeps, 1,316 distinct assets and 5,748 distinct
card-source/action-kind pairs were observed, with no shared asset-hash
conflicts.

The ignored report is
`.cache/goat-ai/whitelist_distinct_10606_10655/report.json` (SHA-256
`adcf78a2152ea8e0363a4d119815f2435661cbf3df7b2e155fde545281314df0`).
Rerunning the exact command produced the same report hash:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/whitelist_distinct_10606_10655 \
  --seed 10606 --seeds 50 --max-decisions 3000 \
  --verify-replays --distinct-opponents --count-card-actions
```

This measures native protocol and observation coverage under random play.
It does not certify the sampled cards' historical rulings or measure playing
strength.

## Synthetic maximum counter menu benchmark (27 October 2026)

`scripts/benchmark_counter_allocation.py` constructs a protocol-only
`MSG_SELECT_COUNTER` prompt with two visible cards, 32,767 counters on each,
and a cost of 32,767. The first staged decision has **32,768** legal amount
choices. This is the representable maximum for a single card in the current
signed 16-bit native response; it is not a witnessed GOAT duel state. A
width-32, feature-v28 PyTorch policy scored every choice with finite logits.

On Linux 6.8, an Intel Core i7-10700K, PyTorch 2.5.1+cpu, and one Torch
thread, three repeats gave median times of **0.019 s** to decode the native
prompt, **0.361 s** to build public actions, **0.807 s** to encode features,
and **0.038 s** for policy inference. Peak process RSS was **381.5 MiB**;
this includes the Python and PyTorch runtime and is not the incremental
memory attributable only to the counter decision. The ignored JSON report is
`.cache/goat-ai/counter_allocation_benchmark_20261027.json` (SHA-256
`7c5a6bd735b0d19d016bcfee8b87e760d5a9744413bcff7227d6c28f535c500b`).
Reproduce the same synthetic workload after installing the `ml` extra:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/benchmark_counter_allocation.py \
  --cards 2 --available 32767 --total 32767 --width 32 --repeats 3
```

The elapsed times will vary by machine. This measures the worst single-card
choice menu, not complete-duel speed or competitive strength. Multiple such
menus in parallel workers could create a material memory load; the project
has no observed native frequency estimate for this extreme prompt.

## Cross-pairing holdout for the half-Tactical PPO child (27 October 2026)

The half-Tactical PPO checkpoint from seeds 57000–57127 was checked on two
new pairings of four Main Decks already used separately in its earlier
holdout: Rhymus Goat Control versus Roberto Martinez Phoenix Control, and
Jae Kim Zombie versus WikiFormat Dimension Fusion. All four Main Deck
compositions are absent from both checkpoints' training provenance, as
enforced by `--require-unseen-main-decks`. These are new matchups and seeds,
not new deck families. The evaluation used both deck assignments and both
policy seats, the pinned experimental engine, four workers, and a 3,000
decision cap. Every one of the 128 direct games and 256 Tactical games
reached terminal.

On direct seeds 57300–57315, the PPO child scored **66–60–2** against its
imitation parent: **52.3%** with paired 95% interval **46.1–58.6%**. On
matched Tactical-v14 seeds 57316–57331, the child scored **43–85** and the
parent **44–83–1**. The validated paired child-minus-parent score difference
was **−1.2 percentage points**, interval **−5.5 to +3.1 points**. Neither
comparison establishes a gain. The child is not promoted; M4's self-play
strength gate remains open.

The ignored direct, child-versus-Tactical, and parent-versus-Tactical reports
are respectively
`.cache/goat-ai/ppo_half_tactical_cross_pair_direct_57300_57315.json`,
`.cache/goat-ai/ppo_half_tactical_cross_pair_child_tactical_57316_57331.json`,
and `.cache/goat-ai/ppo_half_tactical_cross_pair_parent_tactical_57316_57331.json`.
Their SHA-256 hashes are respectively
`1295fa24215b658252cf03737ee445e197b7f3089e750abfed2956405c0065de`,
`9527d10d757583fcdd959b71b1bc373552b0ba63583113f2cb7491a52af2c0d1`,
and `390731b081da4ef2ddfc766b6e5b15bd913af4b7b44093b8baa49c4d03222979`.
Reproduce the three reports with `scripts/evaluate_policy.py --engine
experimental --both-deck-assignments --require-unseen-main-decks --workers 4
--seeds 16 --max-decisions 3000`, the two matchups above, and respectively
`--opponent-checkpoint` with the parent or `--opponent tactical` for each
checkpoint. Use seeds 57300 and 57316 as above. Compare the Tactical reports
with `scripts/compare_tournament_reports.py --require-unseen-main-decks`.

## Random Fusion Deck protocol sweep (27 October 2026)

`scripts/probe_random_decks.py --random-extra` now gives each independently
sampled whitelist Main Deck a deterministic 15-card Fusion Deck. The original
Main Deck seed sequence is unchanged. On seeds 10700–10749, 50/50 duels
reached terminal; 55,685/55,685 decisions replay-verified and passed the
visibility audit. These random Main Decks offered **zero Fusion card actions**,
so their successful loading of 1,266 assets did not test Fusion decisions.
The ignored report is
`.cache/goat-ai/whitelist_random_extra_10700_10749/report.json` (SHA-256
`4b3f360b41f1e0ff6ccf6178011f90047e0fb00a0e228b7d410dc9c2cd490280`).

The opt-in `--fusion-stress` composition includes three Scapegoats, three
Metamorphoses, and Thousand-Eyes Restrict. Ten initial seeds 10750–10759
reached terminal with 10,119/10,119 replay-verified and visibility-audited
decisions. This sample selected real Thousand-Eyes Restrict actions. Its
ignored report is
`.cache/goat-ai/whitelist_fusion_stress_10750_10759/report.json` (SHA-256
`464e3e1acaa97fa4634431e8f66e5164b86d120c2f2db9f9bcde53bf43d8c0d2`).

The next 40 seeds initially exposed two failures. Seed 10786 activated Last
Turn during an attack; its forced battle cleared the shared native attacker,
and the interrupted battle command dereferenced a null pointer. A
checksum-verified core patch now restarts that interrupted command at either
response window. A smaller seed-100 fixture reproduced the second window and
verified Last Turn's End Phase winner after the forced battle. Seed 10772
activated Morale Boost; when an Equip Card left the field, its pinned script
used the card's current controller to identify who takes damage. That value
can be absent after the move. A hash-guarded in-memory script correction uses
the previous field controller. Both formerly failing seeds now complete and
replay-verify in subprocess regressions. The corrections change the core or
loaded-script fingerprints, so the earlier two reports above describe their
own pre-correction assets and should be regenerated before use as exact
current-build training evidence.

On the corrected build, seeds 10760–10799 reached **40/40 terminal** with
**39,677/39,677 decisions** replay-verified and visibility-audited. The run
selected 111 Metamorphosis activations and offered 50 Thousand-Eyes Restrict
activations, selecting eight. It loaded 1,122 distinct native assets. The
ignored report is
`.cache/goat-ai/whitelist_fusion_stress_10760_10799_final/report.json`
(SHA-256
`71a4a3196d11ee0f4a3230a8ccbbe82b59a4ee1e8cfb790aec6d3dab31e774bb`).
Its native library SHA-256 is
`48763d36b1beba3ce37782d7d41cbee58fefe8f65573ab53090e319674bc5358`.
Reproduce from a full-card-scripts native setup:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/probe_random_decks.py --native-root .cache/goat-ai \
  --output .cache/goat-ai/whitelist_fusion_stress_10760_10799_final \
  --seed 10760 --seeds 40 --max-decisions 3000 \
  --random-extra --fusion-stress --distinct-opponents \
  --verify-replays --count-card-actions
```

This probes native protocol coverage under random play. It neither validates
the historical rulings of every sampled card nor establishes arbitrary-deck
completeness or playing strength. A separate Morale Boost fixture checks the
1,000 LP gain from Snatch Steal being equipped and the 1,000 LP loss after MST
removes it, then replay-verifies the complete duel. The Last Turn fixture
replay-verifies its forced-battle outcome; other rulings for both cards remain
untested.

## Tournament-card mix protocol sweep (28 October 2026)

Forty distinct-opponent duels on seeds 10800–10839 used independently sampled,
legal 40-card Main Decks assembled from the six sourced tournament lists.
Their Extra Decks came from those lists. On the corrected native build, **40/40
duels reached terminal**, and **38,452/38,452 decisions** replay-verified and
passed the trajectory visibility audit. The audit included 536 hidden-field,
2,002 opponent-field, and 204 opponent-hand choices. The sweep loaded 103
distinct native assets. The ignored report is
`.cache/goat-ai/tournament_mix_10800_10839/report.json` (SHA-256
`de2f786ed9693fde93bc785e9f16f2776863cb52a8164c17a1956d40fc79b144`),
using core library SHA-256
`48763d36b1beba3ce37782d7d41cbee58fefe8f65573ab53090e319674bc5358`.
Reproduce with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/probe_random_decks.py --native-root .cache/goat-ai \
  --output .cache/goat-ai/tournament_mix_10800_10839 \
  --seed 10800 --seeds 40 --max-decisions 3000 \
  --card-pool tournament --distinct-opponents \
  --verify-replays --count-card-actions
```

This tests seeded native execution and replay/visibility integrity for mixed
high-use cards under random decisions. It is neither a historical-rulings
certification nor a playing-strength result. Probe initialization failures
now retain a per-game error report even when replay verification was requested;
the probe regression test exercises that failure path.

## Verified 2005 Tactical demonstration collection (28 October 2026)

`scripts/collect_heuristic_demos.py --verify-replays` now verifies every
decision against a fresh native engine and audits player-visible legal actions
before writing a demonstration. It saves a hidden `.manifest.json` beside the
trajectory files with run settings, source-deck hashes, per-replay hashes, and
verification counts. The hidden filename keeps `*.json` trajectory input globs
from accidentally including the manifest.

Two current-core, seat-swapped Tactical-v14 mirror collections used published
2005 deck files. Cas Stomphorst Flip Control versus Daryl Gessler Gravekeeper
on seeds 10900–10901 produced **4 terminal games, 2,493 verified and
visibility-audited decisions**, including 1,261 decisions from the designated
demonstrator seats. Its ignored manifest is
`.cache/goat-ai/tactical_2005_verified_cas_daryl_10900_10901/.manifest.json`
(SHA-256 `125fad52682da49be8f15dcd11ccef6d7bddce172c47e8a9600f3b211c91eefb`).
Rhymus Lizo Goat Control versus Jae Kim Zombie on seeds 10902–10903 produced
**4 terminal games, 2,155 verified and visibility-audited decisions**, including
1,053 demonstrator-seat decisions. Its ignored manifest is
`.cache/goat-ai/tactical_2005_verified_rhymus_zombie_10902_10903/.manifest.json`
(SHA-256 `050bd3541b1ac1c6d46ad700ab444993191493766650ce8cde3945dbf2901888`).
All eight replay hashes matched their manifests after collection.

Reproduce a collection with `OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python
scripts/collect_heuristic_demos.py --native-root .cache/goat-ai --engine
experimental --teacher tactical --opponent tactical --deck-a DECK_A --deck-b
DECK_B --seed FIRST_SEED --seeds 2 --max-decisions 3000 --verify-replays
--output-dir OUTPUT_DIR`, substituting the named deck files and seed ranges
above. These are **synthetic Tactical choices**, not human demonstrations or
new evidence of a stronger policy. Any checkpoint trained on them must exclude
these exact Main Deck compositions and seeds from its held-out evaluation.

## Four-duel 2005 behavioral-cloning transfer check (28 October 2026)

An experimental feature-v23 child continued the selected current-core policy
from the four replay-verified Rhymus Goat Control/Jae Kim Zombie Tactical-v14
mirror games above. Those two Main Deck compositions were absent from the
parent's training provenance. The trainer replay-verified all **2,155** source
decisions, selected **1,053** designated teacher-seat decisions, and fit the
**314** non-forced choices for one epoch (batch 16, learning rate 0.0001,
seed 10902). Its ignored checkpoint is
`.cache/goat-ai/fv23_rhymus_zombie_bc_10902_10903.pt` (SHA-256
`baef5d76f5320a673acb91e1a09b2b99f5833bd68739b0a89b2d04b3ce6d6c8f`).

On Phoenix Control versus WikiFormat Dimension Fusion, which are unseen Main
Deck compositions for **both** checkpoints, the child scored **35–28–1**
directly against its frozen parent over 64 seat-swapped, both-assignment duels
on seeds 59000–59015. Its paired score interval was **47.7–64.1%**, including
50%. On separate seeds 59016–59031, it scored **18–46** against Tactical-v14;
the parent scored **17–46–1** on the identical schedule. The validated paired
child-minus-parent Tactical score difference was **+0.8 percentage points**,
95% interval **−5.5 to +6.3 points**. This does not establish a competitive
gain. The parent remains selected, and M4's separate self-play gain gate is
still open.

The ignored direct, child-versus-Tactical, and parent-versus-Tactical reports
are respectively
`.cache/goat-ai/fv23_rhymus_zombie_bc_vs_parent_phoenix_df_59000_59015.json`
(SHA-256 `b019d3a6335f1417201f5128515061fba3dc1c49c69c49f93a38c97bc1a39aeb`),
`.cache/goat-ai/fv23_rhymus_zombie_bc_vs_tactical_phoenix_df_59016_59031.json`
(SHA-256 `c0751653cfa3b8c997431bfa4403e9b013cb502ad9b0576e39a15e985c1faff5`),
and `.cache/goat-ai/fv23_parent_vs_tactical_phoenix_df_59016_59031.json`
(SHA-256 `189fd3944f98746fc663f089ba5eab5e2be6b6d65afa217fdaa3320f6a38d12c`).
All tournament commands used `scripts/evaluate_policy.py --engine experimental
--both-deck-assignments --require-unseen-main-decks --workers 4 --seeds 16
--max-decisions 3000` with the Phoenix/WikiFormat pairing above. Reproduce
the clone with `scripts/train_behavioral_clone.py` and the four
`seed_*.json` files from the Rhymus/Zombie collection, `--engine experimental
--init-checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt
--feature-version 23 --width 32 --epochs 1 --batch-size 16 --batched-forward
--skip-forced-training --learning-rate 0.0001 --seed 10902`, writing to a new
ignored checkpoint path.

## Isolated native deck probe (28 October 2026)

The random-deck probe now has opt-in `--isolate-games`. Each seed runs in a
separate Python process. A native crash is recorded as a failed game with its
worker exit code and any generated decklist hashes, while later seeds still
run. Successful child reports contribute their replay, visibility, card-action,
and loaded-asset counts to one top-level report; each child report remains
under `OUTPUT/isolated/seed_N/report.json`. The output directory must be empty
before starting, which prevents a stale child report from being mistaken for
the current run. The CLI still exits nonzero if any game failed.

A regression simulates a worker exit of `-11` after writing both decklists,
checks their retained hashes, and confirms the next seed reaches terminal and
replay-verifies. A real four-seed tournament-card run on seeds 10800–10803
completed **4/4 terminal**, **3,330/3,330 replay-verified and visibility-audited
decisions**. Seed, deck hashes, decision count, terminal result, action kinds,
error, and verified-decision count match the corresponding four games from
the earlier single-process 40-seed sweep. The ignored combined report is
`.cache/goat-ai/tournament_mix_isolated_10800_10803/report.json` (SHA-256
`eb6cc6b0c6a4fd6a91f421a3d4d3eb79daa85e26b901682cf98de422fbb24f5b`).
Reproduce with the [tournament-card probe command above](#tournament-card-mix-protocol-sweep-28-october-2026),
using a fresh output directory, `--seed 10800 --seeds 4 --isolate-games`.
Process isolation makes failure triage possible; it does not repair a native
crash or certify historical card behavior.

## Tactical-agent tournament-card protocol sweep (28 October 2026)

The isolated random-deck probe now accepts `--agent tactical` as well as its
original RandomAgent default. Tactical-v14 receives the same player-visible
observation and legal actions as the policy; its card metadata is loaded from
the pinned databases. Each seat has its own agent instance. A seeded fixture
repeats a Tactical duel and checks identical decisions and outcome, then
checks that an isolated worker records the same result and agent version.

On seeds 10990–11029, independently generated legal tournament-card Main
Decks faced distinct independently generated opponents. All **40/40 Tactical
duels reached terminal**; all **17,819 decisions** replay-verified and passed
the visibility audit. The run loaded 103 native assets and selected 1,910
source-card actions, including 359 attacks and 35 position changes. The
ignored report is
`.cache/goat-ai/tactical_tournament_isolated_10990_11029/report.json`
(SHA-256 `e6f17f03a05ba8f86cfec90c420e62295690ef077ceb779bf0a39944e3c35867`).

A matched RandomAgent protocol run used exactly the same 40 seed/deck pairs:
**40/40 terminal**, **36,830/36,830 replay-verified and visibility-audited
decisions**, with 337 attacks and 1,056 position changes. Its ignored report
is `.cache/goat-ai/random_tournament_isolated_10990_11029/report.json`
(SHA-256 `d7f8ac02237cf2180ba8d4efbd8bb5692088b3b9d8be0415583fde6bd5cc2727`).
The deck hashes match pairwise, while all 40 decision counts and 20 winners
differ. These are **separate self-play protocol probes**, with each agent
controlling both seats; their action counts and outcomes are not a competitive
head-to-head comparison or a historical-correctness validation.

Reproduce either run with `scripts/probe_random_decks.py --native-root
.cache/goat-ai --card-pool tournament --seed 10990 --seeds 40
--max-decisions 3000 --distinct-opponents --verify-replays
--count-card-actions --isolate-games --agent AGENT --output OUTPUT`, setting
`AGENT` to `tactical` or `random` and using a fresh output directory.

## Neural policy on unseen tournament-card mixes (28 October 2026)

Ten legal, independently generated deck pairs from the Tactical probe above
(seeds 10990–10999) formed a broader held-out policy test. Both the selected
feature-v23 parent and the four-duel Rhymus/Zombie imitation child had **zero
Main Deck composition overlap** with these 20 generated decks. Each policy
faced Tactical-v14 on both deck assignments, both seats, and two fresh duel
seeds (60000–60001): 80 games per policy. The evaluator's strict unseen-Main-
Deck gate passed for both checkpoint reports.

The selected parent scored **24–55–1**, or **30.6%** score (paired 95% interval
**21.3–40.6%**). The imitation child scored **23–57**, or **28.8%** (interval
**21.3–37.5%**). The validated paired child-minus-parent score difference was
**−1.9 percentage points**, 95% interval **−10.6 to +6.3 points**. The child
therefore remains experimental; this additional deck-diversity check gives no
reason to promote it. Both policies remain well behind this synthetic Tactical
baseline on the measured schedule. These decks combine cards from sourced
tournament lists but are not published historical decklists, and this
tournament did not independently replay-verify its neural games or audit every
card-specific ruling. It measures current native-game outcomes, not human-level
competitive strength.

The ignored parent and child reports are respectively
`.cache/goat-ai/fv23_parent_vs_tactical_mix_60000_60001.json` (SHA-256
`ebd85ebae716fe4374820b3450262e498d45cf37d11ba234657942525c70881c`)
and `.cache/goat-ai/fv23_child_vs_tactical_mix_60000_60001.json` (SHA-256
`65530ab904f6eecf1807baf6a2495d8e8c9faedb8e91a07faf5c927bbb3d1cda`).
Reproduce with `scripts/evaluate_policy.py --engine experimental --opponent
tactical --both-deck-assignments --require-unseen-main-decks --seed 60000
--seeds 2 --workers 4 --max-decisions 3000`, adding ten `--matchup` pairs
from the isolated probe's `seed_10990` through `seed_10999` deck files and
using the named checkpoint for each run. Validate the matched reports with
`scripts/compare_tournament_reports.py --require-unseen-main-decks`.
## Additional independent whitelist and Fusion protocol sample (28 October 2026)

An isolated RandomAgent probe paired 20 independently sampled, whitelist-legal
40-card Main Decks with 20 different opponent Main Decks on seeds 11100–11119.
Each deck received a deterministic 15-card Fusion Deck. All **20/20 duels**
reached terminal within the 3,000-decision cap. All **19,282 decisions**
replay-verified and passed the player-visibility audit, which observed 129
hidden-field, 963 opponent-field, and 18 opponent-hand choices. The run loaded
61 script paths absent from the earlier 50-game random-Fusion sample on seeds
10700–10749; loading a script does not prove every effect branch was used.
No protocol failure was found in this sample.

Two of these seeds were rerun with deterministic trace checking. Both terminal
duels reproduced all **1,587 decisions** and passed replay and visibility
checks. The full report is ignored local data at
`.cache/goat-ai/protocol_whitelist_11100_11119/report.json` (SHA-256
`da08e64294d96376a5093d72962213cfb323528090c486fd93a1ba293147e37c`).
The repeat report is
`.cache/goat-ai/protocol_whitelist_repeat_11100_11101/report.json` (SHA-256
`2d24487a2a653e9b1af5591bd9f86a41b16faa87a130c7d33e6820fe007b4cae`).

```bash
PYTHONPATH=src:. OMP_NUM_THREADS=1 .venv/bin/python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/protocol_whitelist_11100_11119 \
  --seed 11100 --seeds 20 --max-decisions 3000 --card-pool whitelist \
  --distinct-opponents --random-extra --isolate-games --verify-replays

PYTHONPATH=src:. OMP_NUM_THREADS=1 .venv/bin/python scripts/probe_random_decks.py \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/protocol_whitelist_repeat_11100_11101 \
  --seed 11100 --seeds 2 --max-decisions 3000 --card-pool whitelist \
  --distinct-opponents --random-extra --isolate-games --verify-replays \
  --repeat-seeds
```

This is native protocol and observation coverage. Random play and a sampled
card pool cannot establish historical GOAT correctness for the loaded cards.
