# Native benchmark log

The benchmark runs the real pinned ocgcore through `RestrictedOcgcoreEngine` with two normal-monster fixture decks and two seeded `RandomAgent` seats. It measures wall time around reset, action selection, steps, and teardown. It is a narrow protocol baseline, not a measure of general GOAT gameplay or training throughput. Run it with `python scripts/benchmark_native.py --games 3 --seed 42` after [native setup](native_setup.md).

| Date | Platform | Games | Decisions | Elapsed | Duels/s | Decisions/s | Peak process RSS |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-10-24 | Linux 6.8.0-146-generic x86_64 | 3 | 3876 | 2.403 s | 1.248 | 1612.72 | 54,340 KiB |
| 2026-10-24 (GOAT database attached) | Linux 6.8.0-146-generic x86_64 | 3 | 3876 | 2.315 s | 1.296 | 1674.56 | 54,972 KiB |

This run used core commit `baa3881d0bae48e9994f915f5c931be53c1ba8ef`, seed start 42, and produced winners `[1, 1, 1]`. Total reset time was 0.135 s; average decisions per duel was 1,292. The bridge shuffled both decks deterministically from the seed before insertion. The process had an 18,156 KiB high-water mark before the timed loop. Memory is read from Linux `/proc/self/status` `VmHWM`; `resource.ru_maxrss` returned an implausible 5,950,868 KiB for an empty interpreter in this environment, so it is not used. These are measurements from one run, without uncertainty estimates. The earlier unshuffled run is excluded because all seeds saw the same opening deck order.

The second row uses the same core and fixture after attaching pinned `goat-entries.cdb` and loading selected GOAT scripts. Its reset time was 0.135 s, initial peak RSS 16,964 KiB, and winners `[1, 1, 1]`. These one-run differences do not establish a speed change.
