# Baseline evaluation log

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
