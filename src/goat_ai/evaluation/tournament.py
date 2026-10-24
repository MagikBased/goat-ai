"""Seat-swapped, seeded duels and decisive-win confidence intervals."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import sqrt
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
        return {
            "overall": summarize(self.games),
            "a_first": summarize([g for g in self.games if g.a_seat == 0]),
            "a_second": summarize([g for g in self.games if g.a_seat == 1]),
            "matchups": [
                {"deck_a": a, "deck_b": b,
                 **summarize([g for g in self.games if (g.deck_a, g.deck_b) == (a, b)])}
                for a, b in matchups
            ],
        }


def bootstrap_score_interval(games: Sequence[GameResult],
                             resamples: int = 4096) -> tuple[float, float]:
    """Percentile bootstrap, resampling each matchup/seed as one paired unit."""
    if not games:
        return (0.0, 1.0)
    if resamples < 1:
        raise ValueError("resamples must be positive")
    clusters: dict[tuple[str, str, int], list[GameResult]] = {}
    for game in games:
        clusters.setdefault((game.deck_a, game.deck_b, game.seed), []).append(game)
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


def run_tournament(
    matchups: Sequence[tuple[str, str]], seeds: Sequence[int],
    agent_a: Callable[[int], Agent], agent_b: Callable[[int], Agent],
    engine_factory: Callable[[], RulesEngine], max_decisions: int = 5000,
) -> TournamentReport:
    """Run each matchup/seed twice, with candidate A in each seat once."""
    if not matchups or not seeds or max_decisions < 1:
        raise ValueError("nonempty matchups/seeds and positive max_decisions required")
    games = []
    for deck_a, deck_b in matchups:
        for seed in seeds:
            for a_seat in (0, 1):
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
                            games.append(GameResult(deck_a, deck_b, seed, a_seat,
                                                    env.result(), decision_count))
                            break
                    else:
                        raise RuntimeError(
                            f"duel exceeded {max_decisions} decisions: "
                            f"decks={decks}, seed={seed}, A seat={a_seat}")
    return TournamentReport(tuple(games))
