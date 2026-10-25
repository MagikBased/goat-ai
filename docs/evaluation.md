# Baseline evaluation log

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
