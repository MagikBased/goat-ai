"""Episodic policy-gradient experiments against frozen checkpoint opponents."""

import copy
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

import torch

from goat_ai.agents import Agent, RandomAgent
from goat_ai.engine import RulesEngine
from goat_ai.engine.protocol import SimulatorUnavailable
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import DecisionRecord, Trajectory
from goat_ai.training.policy import CardVocabulary, LegalActionPolicy, encode_decision


@dataclass(frozen=True)
class EpisodeResult:
    seed: int
    learner_seat: int
    winner: int | None
    decisions: int
    learner_records: tuple[DecisionRecord, ...]
    trajectory: Trajectory

    @property
    def reward(self) -> float:
        if self.winner is None:
            return 0.0
        return 1.0 if self.winner == self.learner_seat else -1.0


class EpisodeDecisionLimit(RuntimeError):
    """A duel did not terminate within the declared decision budget."""

    def __init__(self, seed: int, max_decisions: int) -> None:
        self.seed = seed
        self.max_decisions = max_decisions
        super().__init__(f"self-play duel exceeded {max_decisions} decisions: seed={seed}")


def episode_schedule(matchups: Sequence[tuple[str, str]],
                     seeds: Sequence[int]) -> tuple[tuple[int, tuple[str, str], int], ...]:
    """Cycle matchups after both learner seats have been assigned."""
    if not matchups:
        raise ValueError("at least one matchup required")
    schedule = []
    for index, seed in enumerate(seeds):
        a, b = matchups[(index // 2) % len(matchups)]
        seat = index % 2
        decks = (a, b) if seat == 0 else (b, a)
        schedule.append((seed, decks, seat))
    return tuple(schedule)


def sample_legal_action(model: LegalActionPolicy, vocabulary: CardVocabulary,
                        observation, legal_actions, generator: torch.Generator,
                        temperature: float = 1.0):
    """Sample from visible legal options, with no native-state access."""
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    features = encode_decision(observation, legal_actions, vocabulary, model.feature_version)
    device = next(model.parameters()).device
    with torch.no_grad():
        logits = model(features.to(device)) / temperature
        probabilities = torch.softmax(logits, dim=0).cpu()
        index = int(torch.multinomial(probabilities, 1, generator=generator).item())
    return legal_actions[index]


class SamplingPolicyAgent:
    def __init__(self, model: LegalActionPolicy, vocabulary: CardVocabulary,
                 generator: torch.Generator) -> None:
        self.model = model
        self.vocabulary = vocabulary
        self.generator = generator

    def select_action(self, observation, legal_actions):
        return sample_legal_action(self.model, self.vocabulary, observation,
                                   legal_actions, self.generator)


def run_learning_episode(
    model: LegalActionPolicy, vocabulary: CardVocabulary, opponent: Agent,
    decks: tuple[str, str], seed: int, learner_seat: int,
    engine_factory: Callable[[], RulesEngine], generator: torch.Generator,
    max_decisions: int = 5000, learner_temperature: float = 1.0,
) -> EpisodeResult:
    if learner_seat not in (0, 1) or max_decisions < 1 or learner_temperature <= 0:
        raise ValueError("invalid learner seat or decision cap")
    records = []
    with GoatEnvironment(*decks, seed=seed, engine=engine_factory()) as env:
        observation = env.reset()
        for count in range(1, max_decisions + 1):
            legal_actions = env.legal_actions()
            if observation.acting_player == learner_seat:
                action = sample_legal_action(model, vocabulary, observation,
                                             legal_actions, generator,
                                             temperature=learner_temperature)
                if len(legal_actions) > 1:
                    records.append(DecisionRecord(observation, legal_actions, action))
            else:
                action = opponent.select_action(observation, legal_actions)
            observation = env.step(action)
            if env.is_terminal():
                trajectory = replace(env.trajectory(), source="self_play_rl",
                                     skill_metadata={"learner_seat": learner_seat})
                return EpisodeResult(seed, learner_seat, env.result(), count,
                                     tuple(records), trajectory)
    raise EpisodeDecisionLimit(seed, max_decisions)


def policy_gradient_update(model: LegalActionPolicy, vocabulary: CardVocabulary,
                           records: Sequence[DecisionRecord], reward: float,
                           baseline: float, optimizer: torch.optim.Optimizer,
                           entropy_coefficient: float = 0.0,
                           max_gradient_norm: float = 1.0,
                           temperature: float = 1.0) -> float:
    """Apply one terminal-return score-function update; return mean loss."""
    if (not records or entropy_coefficient < 0 or max_gradient_norm <= 0
            or temperature <= 0):
        raise ValueError("update needs decisions, positive temperature, and valid regularization")
    optimizer.zero_grad()
    device = next(model.parameters()).device
    advantage = reward - baseline
    total = 0.0
    for record in records:
        features = encode_decision(record.observation, record.legal_actions,
                                   vocabulary, model.feature_version).to(device)
        logits = model(features) / temperature
        log_probabilities = torch.log_softmax(logits, dim=0)
        probabilities = log_probabilities.exp()
        selected = record.legal_actions.index(record.selected_action)
        entropy = -(probabilities * log_probabilities).sum()
        loss = -advantage * log_probabilities[selected] - entropy_coefficient * entropy
        loss.backward()
        total += float(loss.detach())
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_gradient_norm)
    optimizer.step()
    return total / len(records)


def train_against_snapshot_pool(
    model: LegalActionPolicy, vocabulary: CardVocabulary,
    matchups: Sequence[tuple[str, str]], seeds: Sequence[int],
    engine_factory: Callable[[], RulesEngine], *, learning_rate: float = 1e-4,
    historical_probability: float = 0.75, snapshot_every: int = 4,
    max_snapshots: int = 8, entropy_coefficient: float = 0.001,
    max_decisions: int = 5000, random_seed: int = 0,
    learner_temperature: float = 1.0,
    skip_capped_games: bool = False,
    skip_unsupported_games: bool = False,
    record_episode: Callable[[int, EpisodeResult], None] | None = None,
) -> tuple[dict, ...]:
    """Train one learner seat per duel against random or frozen past policies.

    Frozen snapshots prevent the opponent from changing within an episode.
    This is an initial REINFORCE-style experiment, not PPO or league training.
    """
    if (not matchups or not seeds or learning_rate <= 0 or snapshot_every < 1
            or max_snapshots < 1 or learner_temperature <= 0
            or not 0 <= historical_probability <= 1):
        raise ValueError("invalid self-play schedule or hyperparameters")
    rng = random.Random(random_seed)
    generator = torch.Generator(device="cpu").manual_seed(random_seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    snapshots = [copy.deepcopy(model.state_dict())]
    baseline = 0.0
    reports = []
    for index, (seed, decks, learner_seat) in enumerate(episode_schedule(matchups, seeds)):
        if rng.random() < historical_probability:
            snapshot_index = rng.randrange(len(snapshots))
            frozen = LegalActionPolicy(vocabulary.size, width=model.card.embedding_dim,
                                       feature_version=model.feature_version)
            frozen.load_state_dict(snapshots[snapshot_index])
            frozen.eval()

            opponent: Agent = SamplingPolicyAgent(frozen, vocabulary, generator)
            opponent_name = f"snapshot_{snapshot_index}"
        else:
            opponent = RandomAgent(seed)
            opponent_name = "random"
        try:
            episode = run_learning_episode(model, vocabulary, opponent, decks, seed,
                                           learner_seat, engine_factory, generator,
                                           max_decisions, learner_temperature)
        except EpisodeDecisionLimit:
            if not skip_capped_games:
                raise
            reports.append({"seed": seed, "learner_seat": learner_seat,
                            "decks": decks, "opponent": opponent_name,
                            "status": "decision_limit", "decisions": max_decisions,
                            "learner_decisions": 0, "policy_loss": None})
            continue
        except SimulatorUnavailable as exc:
            if not skip_unsupported_games:
                raise
            reports.append({"seed": seed, "learner_seat": learner_seat,
                            "decks": decks, "opponent": opponent_name,
                            "status": "simulator_unavailable", "error": str(exc),
                            "learner_decisions": 0, "policy_loss": None})
            continue
        if record_episode is not None:
            record_episode(index, episode)
        loss = (policy_gradient_update(model, vocabulary, episode.learner_records,
                                       episode.reward, baseline, optimizer,
                                       entropy_coefficient,
                                       temperature=learner_temperature)
                if episode.learner_records else None)
        baseline = 0.95 * baseline + 0.05 * episode.reward
        reports.append({"seed": seed, "learner_seat": learner_seat,
                        "decks": decks, "opponent": opponent_name,
                        "status": "terminal",
                        "deck_sha256": episode.trajectory.deck_sha256,
                        "asset_sha256": episode.trajectory.asset_sha256,
                        "rules_profile": episode.trajectory.rules_profile,
                        "winner": episode.winner, "reward": episode.reward,
                        "decisions": episode.decisions,
                        "learner_decisions": len(episode.learner_records),
                        "policy_loss": loss})
        if (index + 1) % snapshot_every == 0:
            snapshots.append(copy.deepcopy(model.state_dict()))
            if len(snapshots) > max_snapshots:
                snapshots.pop(1)  # keep the initial teacher in the pool
    return tuple(reports)
