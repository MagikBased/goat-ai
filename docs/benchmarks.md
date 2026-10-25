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
