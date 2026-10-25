"""Seat-swapped, seeded duels and decisive-win confidence intervals."""

import pickle
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from itertools import repeat
from math import sqrt
from multiprocessing import get_context
from random import Random

from goat_ai.agents import Agent
from goat_ai.engine import RulesEngine
from goat_ai.environments import GoatEnvironment


@dataclass(frozen=True)
class GameResult:
    deck_a: str
    deck_b: str
    seed: int
    a_seat: int
    winner: int | None
    decisions: int

    @property
    def a_outcome(self) -> str:
        if self.winner is None:
            return "draw"
        return "win" if self.winner == self.a_seat else "loss"


def wilson_interval(wins: int, games: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """95% binomial Wilson interval by default; draws must be excluded."""
    if games < 0 or not 0 <= wins <= games:
        raise ValueError("wins must be between zero and games")
    if games == 0:
        return (0.0, 1.0)
    p = wins / games
    z2 = z * z
    denominator = 1 + z2 / games
    center = (p + z2 / (2 * games)) / denominator
    margin = z * sqrt(p * (1 - p) / games + z2 / (4 * games * games)) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


@dataclass(frozen=True)
class TournamentReport:
    games: tuple[GameResult, ...]

    def summary(self) -> dict:
        def summarize(games: Sequence[GameResult]) -> dict:
            wins = sum(game.a_outcome == "win" for game in games)
            losses = sum(game.a_outcome == "loss" for game in games)
            draws = len(games) - wins - losses
            decisive = wins + losses
            low, high = wilson_interval(wins, decisive)
            return {
                "games": len(games), "wins": wins, "losses": losses, "draws": draws,
                "score_rate": (wins + draws / 2) / len(games) if games else None,
                "score_rate_95pct_paired_bootstrap": list(bootstrap_score_interval(games)),
                "decisive_win_rate": wins / decisive if decisive else None,
                "decisive_win_rate_95pct_wilson": [low, high],
                "average_decisions": sum(game.decisions for game in games) / len(games)
                if games else None,
            }

        matchups = sorted({(game.deck_a, game.deck_b) for game in self.games})
        decks_a = sorted({game.deck_a for game in self.games})
        return {
            "overall": summarize(self.games),
            "a_first": summarize([g for g in self.games if g.a_seat == 0]),
            "a_second": summarize([g for g in self.games if g.a_seat == 1]),
            "by_deck_a": [
                {"deck_a": deck, **summarize([g for g in self.games
                                              if g.deck_a == deck])}
                for deck in decks_a
            ],
            "matchups": [
                {"deck_a": a, "deck_b": b,
                 **summarize([g for g in self.games if (g.deck_a, g.deck_b) == (a, b)])}
                for a, b in matchups
            ],
        }


def both_deck_assignments(
    matchups: Sequence[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    """Run each unordered deck pair with each agent assigned each deck once."""
    expanded: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for deck_a, deck_b in matchups:
        for pair in ((deck_a, deck_b), (deck_b, deck_a)):
            if pair not in seen:
                expanded.append(pair)
                seen.add(pair)
    return tuple(expanded)


def bootstrap_score_interval(games: Sequence[GameResult],
                             resamples: int = 4096) -> tuple[float, float]:
    """Percentile bootstrap, resampling each matchup/seed as one paired unit."""
    if not games:
        return (0.0, 1.0)
    if resamples < 1:
        raise ValueError("resamples must be positive")
    clusters: dict[tuple[str, str, int], list[GameResult]] = {}
    for game in games:
        unit = (*sorted((game.deck_a, game.deck_b)), game.seed)
        clusters.setdefault(unit, []).append(game)
    units = tuple(clusters.values())
    if len(units) == 1:
        return (0.0, 1.0)
    rng = Random(0)
    samples = []
    for _ in range(resamples):
        chosen = [units[rng.randrange(len(units))] for _ in units]
        wins = sum(game.a_outcome == "win" for unit in chosen for game in unit)
        draws = sum(game.a_outcome == "draw" for unit in chosen for game in unit)
        count = sum(len(unit) for unit in chosen)
        samples.append((wins + draws / 2) / count)
    samples.sort()
    return (samples[int(0.025 * (resamples - 1))],
            samples[int(0.975 * (resamples - 1))])


def paired_score_difference(
    candidate: Sequence[GameResult], control: Sequence[GameResult],
    resamples: int = 4096,
) -> tuple[float, float, float]:
    """Candidate minus control score with a paired, matchup-seed bootstrap.

    Each unordered deck pair and seed is one unit, keeping both deck
    assignments and seats together when the schedule includes them.
    """
    if not candidate or resamples < 1:
        raise ValueError("nonempty games and positive resamples required")

    def keyed(games: Sequence[GameResult]) -> dict[tuple[str, str, int, int], float]:
        result = {}
        for game in games:
            key = (game.deck_a, game.deck_b, game.seed, game.a_seat)
            if key in result:
                raise ValueError(f"duplicate tournament game: {key}")
            result[key] = 1.0 if game.a_outcome == "win" else (
                0.5 if game.a_outcome == "draw" else 0.0)
        return result

    left, right = keyed(candidate), keyed(control)
    if left.keys() != right.keys():
        raise ValueError("candidate and control schedules differ")
    clusters: dict[tuple[str, str, int], list[float]] = {}
    for (deck_a, deck_b, seed, _seat), score in left.items():
        unit = (*sorted((deck_a, deck_b)), seed)
        clusters.setdefault(unit, []).append(score - right[deck_a, deck_b, seed, _seat])
    units = tuple(clusters.values())
    point = sum(sum(unit) for unit in units) / len(candidate)
    if len(units) == 1:
        return point, -1.0, 1.0
    rng = Random(0)
    samples = []
    for _ in range(resamples):
        chosen = [units[rng.randrange(len(units))] for _ in units]
        samples.append(sum(sum(unit) for unit in chosen) /
                       sum(len(unit) for unit in chosen))
    samples.sort()
    return (point, samples[int(0.025 * (resamples - 1))],
            samples[int(0.975 * (resamples - 1))])


def run_tournament(
    matchups: Sequence[tuple[str, str]], seeds: Sequence[int],
    agent_a: Callable[[int], Agent], agent_b: Callable[[int], Agent],
    engine_factory: Callable[[], RulesEngine], max_decisions: int = 5000,
) -> TournamentReport:
    """Run each matchup/seed twice, with candidate A in each seat once."""
    if not matchups or not seeds or max_decisions < 1:
        raise ValueError("nonempty matchups/seeds and positive max_decisions required")
    schedule = ((a, b, seed, seat) for a, b in matchups
                for seed in seeds for seat in (0, 1))
    return TournamentReport(tuple(_play_game(job, agent_a, agent_b, engine_factory,
                                             max_decisions) for job in schedule))


def _play_game(job: tuple[str, str, int, int],
               agent_a: Callable[[int], Agent], agent_b: Callable[[int], Agent],
               engine_factory: Callable[[], RulesEngine],
               max_decisions: int) -> GameResult:
    deck_a, deck_b, seed, a_seat = job
    decks = (deck_a, deck_b) if a_seat == 0 else (deck_b, deck_a)
    a, b = agent_a(seed), agent_b(seed)
    agents = (a, b) if a_seat == 0 else (b, a)
    with GoatEnvironment(*decks, seed=seed, engine=engine_factory()) as env:
        observation = env.reset()
        for decision_count in range(1, max_decisions + 1):
            action = agents[observation.acting_player].select_action(
                observation, env.legal_actions())
            observation = env.step(action)
            if env.is_terminal():
                return GameResult(deck_a, deck_b, seed, a_seat,
                                  env.result(), decision_count)
    raise RuntimeError(f"duel exceeded {max_decisions} decisions: "
                       f"decks={decks}, seed={seed}, A seat={a_seat}")


def run_tournament_parallel(
    matchups: Sequence[tuple[str, str]], seeds: Sequence[int],
    agent_a: Callable[[int], Agent], agent_b: Callable[[int], Agent],
    engine_factory: Callable[[], RulesEngine], max_decisions: int = 5000,
    workers: int = 2,
) -> TournamentReport:
    """Run independent games in spawned processes, preserving schedule order.

    Agent and engine factories must be pickleable top-level callables or
    ``functools.partial`` instances. Spawn avoids inheriting live native duels.
    """
    if not matchups or not seeds or max_decisions < 1 or workers < 1:
        raise ValueError("nonempty matchups/seeds and positive limits/workers required")
    for name, factory in (("agent_a", agent_a), ("agent_b", agent_b),
                          ("engine_factory", engine_factory)):
        try:
            pickle.dumps(factory)
        except (pickle.PicklingError, TypeError, AttributeError) as exc:
            raise TypeError(f"{name} must be pickleable for process workers") from exc
    schedule = tuple((a, b, seed, seat) for a, b in matchups
                     for seed in seeds for seat in (0, 1))
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
        games = tuple(executor.map(_play_game, schedule, repeat(agent_a),
                                   repeat(agent_b), repeat(engine_factory),
                                   repeat(max_decisions)))
    return TournamentReport(games)
