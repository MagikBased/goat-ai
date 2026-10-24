import math
import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.evaluation import GameResult, run_tournament, wilson_interval
from goat_ai.evaluation.tournament import bootstrap_score_interval


def test_wilson_interval_handles_edges_and_balanced_results():
    assert wilson_interval(0, 0) == (0.0, 1.0)
    low, high = wilson_interval(2, 4)
    assert math.isclose(low, 0.15003898915214947)
    assert math.isclose(high, 0.8499610108478506)
    assert wilson_interval(0, 4)[0] == 0.0
    assert wilson_interval(4, 4)[1] == 1.0
    with pytest.raises(ValueError):
        wilson_interval(3, 2)


def test_paired_bootstrap_scores_complete_wins_and_draws():
    wins = [GameResult("a", "b", seed, seat, seat, 10)
            for seed in range(4) for seat in (0, 1)]
    assert bootstrap_score_interval(wins) == (1.0, 1.0)
    draws = [GameResult("a", "b", seed, seat, None, 10)
             for seed in range(4) for seat in (0, 1)]
    assert bootstrap_score_interval(draws) == (0.5, 0.5)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_native_tournament_swaps_seats_and_reproduces_results():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    matchup = [(str(decks / "vanilla_probe.ydk"), str(decks / "vanilla_reverse.ydk"))]

    def run():
        return run_tournament(matchup, [42, 43], RandomAgent, RandomAgent,
                              lambda: RestrictedOcgcoreEngine(root))

    report = run()
    assert report == run()
    assert len(report.games) == 4
    assert [(game.seed, game.a_seat) for game in report.games] == [
        (42, 0), (42, 1), (43, 0), (43, 1),
    ]
    summary = report.summary()
    assert summary["overall"]["games"] == 4
    assert summary["a_first"]["games"] == summary["a_second"]["games"] == 2
    assert summary["overall"]["wins"] + summary["overall"]["losses"] == 4
