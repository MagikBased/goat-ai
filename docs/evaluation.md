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
