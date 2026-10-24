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
