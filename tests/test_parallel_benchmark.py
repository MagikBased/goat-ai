"""The benchmark must keep seat pairs and count each worker's peak once."""

import pytest

from scripts.benchmark_parallel_native import schedule, worker_memory


def test_parallel_benchmark_pairs_seats_for_each_seed():
    assert schedule(9700, 6) == (
        (9700, 0), (9700, 1), (9701, 0), (9701, 1), (9702, 0), (9702, 1))
    for games in (0, 1, 3, -2):
        with pytest.raises(ValueError):
            schedule(9700, games)


def test_parallel_benchmark_sums_each_worker_high_water_only_once():
    games = (
        {"pid": 2, "worker_initial_peak_rss_kb": 20,
         "worker_peak_rss_kb": 80},
        {"pid": 1, "worker_initial_peak_rss_kb": 10,
         "worker_peak_rss_kb": 40},
        {"pid": 2, "worker_initial_peak_rss_kb": 80,
         "worker_peak_rss_kb": 100},
    )
    assert worker_memory(games) == {
        "workers_observed": 2,
        "worker_processes": [
            {"pid": 1, "games": 1, "initial_peak_rss_kb": 10,
             "peak_rss_kb": 40},
            {"pid": 2, "games": 2, "initial_peak_rss_kb": 20,
             "peak_rss_kb": 100},
        ],
        "sum_worker_peak_rss_kb": 140,
    }
