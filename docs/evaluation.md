# Baseline evaluation log

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
