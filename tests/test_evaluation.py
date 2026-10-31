import math
import os
from functools import partial
from pathlib import Path

import pytest

from goat_ai.agents import HeuristicAgent, RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.evaluation import (
    GameResult,
    TournamentReport,
    both_deck_assignments,
    paired_score_difference,
    run_tournament,
    run_tournament_parallel,
    wilson_interval,
)
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


def test_both_deck_assignments_deduplicates_reverse_pairs():
    assert both_deck_assignments((("goat", "chaos"), ("chaos", "goat"),
                                  ("warrior", "warrior"))) == (
        ("goat", "chaos"), ("chaos", "goat"), ("warrior", "warrior"))


def test_summary_reports_candidate_deck_splits_across_opponents_and_seats():
    report = TournamentReport((
        GameResult("goat", "chaos", 1, 0, 0, 10),
        GameResult("goat", "chaos", 1, 1, 0, 20),
        GameResult("goat", "warrior", 2, 0, None, 30),
        GameResult("chaos", "goat", 1, 1, 1, 40),
    ))
    splits = {entry["deck_a"]: entry for entry in report.summary()["by_deck_a"]}
    assert (splits["goat"]["games"], splits["goat"]["wins"],
            splits["goat"]["losses"], splits["goat"]["draws"]) == (3, 1, 1, 1)
    assert splits["goat"]["score_rate"] == 0.5
    assert (splits["chaos"]["games"], splits["chaos"]["wins"]) == (1, 1)


def test_paired_bootstrap_scores_complete_wins_and_draws():
    wins = [GameResult("a", "b", seed, seat, seat, 10)
            for seed in range(4) for seat in (0, 1)]
    assert bootstrap_score_interval(wins) == (1.0, 1.0)
    draws = [GameResult("a", "b", seed, seat, None, 10)
             for seed in range(4) for seat in (0, 1)]
    assert bootstrap_score_interval(draws) == (0.5, 0.5)
    one_seed = [GameResult(a, b, 1, seat, seat, 10)
                for a, b in (("goat", "chaos"), ("chaos", "goat"))
                for seat in (0, 1)]
    assert bootstrap_score_interval(one_seed) == (0.0, 1.0)


def test_paired_score_difference_preserves_mirrored_deck_and_seat_schedule():
    candidate = [GameResult(a, b, seed, seat, seat, 10)
                 for seed in (1, 2) for a, b in (("a", "b"), ("b", "a"))
                 for seat in (0, 1)]
    control = [GameResult(g.deck_a, g.deck_b, g.seed, g.a_seat,
                          1 - g.a_seat, 10) for g in reversed(candidate)]
    assert paired_score_difference(candidate, control) == (1.0, 1.0, 1.0)
    assert paired_score_difference(candidate, candidate) == (0.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="schedules differ"):
        paired_score_difference(candidate, control[:-1])
    with pytest.raises(ValueError, match="duplicate tournament game"):
        paired_score_difference(candidate + candidate[:1], control)


def test_parallel_runner_rejects_unpickleable_factories():
    with pytest.raises(TypeError, match="agent_a must be pickleable"):
        run_tournament_parallel([("a", "b")], [42], lambda seed: RandomAgent(seed),
                                RandomAgent, RandomAgent, workers=2)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_native_tournament_swaps_seats_and_reproduces_results():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    matchup = [(str(decks / "vanilla_probe.ydk"), str(decks / "vanilla_reverse.ydk"))]

    def run():
        return run_tournament(matchup, [42, 43], RandomAgent, RandomAgent,
                              partial(RestrictedOcgcoreEngine, root))

    report = run()
    assert report == run()
    assert report == run_tournament_parallel(
        matchup, [42, 43], RandomAgent, RandomAgent,
        partial(RestrictedOcgcoreEngine, root), workers=2)
    assert len(report.games) == 4
    assert [(game.seed, game.a_seat) for game in report.games] == [
        (42, 0), (42, 1), (43, 0), (43, 1),
    ]
    assert all(game.decision_trace_sha256 is None for game in report.games)
    summary = report.summary()
    assert summary["overall"]["games"] == 4
    assert summary["a_first"]["games"] == summary["a_second"]["games"] == 2
    assert summary["overall"]["wins"] + summary["overall"]["losses"] == 4


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_native_tournament_opt_in_replay_and_visibility_verification():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    matchup = [(str(decks / "vanilla_probe.ydk"), str(decks / "vanilla_reverse.ydk"))]
    args = (matchup, [842], RandomAgent, RandomAgent,
            partial(RestrictedOcgcoreEngine, root))
    serial = run_tournament(*args, verify_replays=True)
    parallel = run_tournament_parallel(*args, workers=2, verify_replays=True)
    assert serial == parallel
    assert len(serial.games) == 2
    assert all(game.replay_verified_decisions == game.decisions
               and game.visibility_audited_decisions == game.decisions
               and isinstance(game.decision_trace_sha256, str)
               and len(game.decision_trace_sha256) == 64
               for game in serial.games)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sourced_goat_chaos_tournament_reproduces_seat_swaps():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    matchup = [(str(decks / "goat_control_lolmarcus_2020.ydk"),
                str(decks / "chaos_turbo_riclar_2020.ydk"))]

    def run():
        return run_tournament(matchup, [7000], lambda _seed: HeuristicAgent(),
                              RandomAgent, partial(ExperimentalOcgcoreEngine, root),
                              max_decisions=3000)

    report = run()
    assert report == run()
    assert [(game.seed, game.a_seat) for game in report.games] == [
        (7000, 0), (7000, 1)]
    assert all(game.decisions > 100 for game in report.games)
    assert report.summary()["overall"]["games"] == 2
