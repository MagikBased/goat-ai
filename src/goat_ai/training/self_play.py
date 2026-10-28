"""Episodic policy-gradient experiments against frozen checkpoint opponents."""

import copy
import random
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass, replace
from math import isfinite
from multiprocessing import get_context

import torch
from torch import nn

from goat_ai.actions import Action
from goat_ai.agents import Agent, RandomAgent, TacticalHeuristicAgent
from goat_ai.engine import RulesEngine
from goat_ai.engine.protocol import SimulatorUnavailable
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import DecisionRecord, Trajectory
from goat_ai.training.policy import (
    CHAIN_TARGET_FEATURE_VERSIONS,
    PHASES,
    POSITIONS,
    ZONES,
    CardVocabulary,
    DecisionFeatures,
    LegalActionPolicy,
    encode_decision,
)
from goat_ai.training.resource_value import FrozenResourceRidge


class VisibleStateValue(nn.Module):
    """Estimate learner outcome from the same player-visible contract as the policy."""

    def __init__(self, vocabulary_size: int, state_number_width: int,
                 width: int = 32, *, architecture: str = "v1",
                 card_number_width: int = 5) -> None:
        super().__init__()
        if architecture not in ("v1", "v2"):
            raise ValueError("unsupported visible-state critic architecture")
        self.architecture = architecture
        self.card = nn.Embedding(vocabulary_size, width, padding_idx=0)
        self.zone = nn.Embedding(len(ZONES) + 1, width, padding_idx=0)
        self.owner = nn.Embedding(3, width, padding_idx=0)
        self.position = nn.Embedding(len(POSITIONS) + 1, width, padding_idx=0)
        self.phase = nn.Embedding(len(PHASES) + 1, width, padding_idx=0)
        self.numbers = nn.Sequential(nn.Linear(state_number_width, width), nn.ReLU(),
                                     nn.Linear(width, width))
        if architecture == "v2":
            self.card_numbers = nn.Sequential(nn.Linear(card_number_width, width), nn.ReLU(),
                                              nn.Linear(width, width))
            self.deck_projection = nn.Linear(width, width)
            self.resource_counts = nn.Linear(14, width)
        self.value = nn.Sequential(nn.Linear(width * (4 if architecture == "v2" else 1),
                                             width), nn.ReLU(),
                                   nn.Linear(width, 1), nn.Tanh())

    def forward(self, features: DecisionFeatures) -> torch.Tensor:
        cards = features.state_cards
        visible = (self.card(cards[:, 0]) + self.zone(cards[:, 1])
                   + self.owner(cards[:, 2]) + self.position(cards[:, 3]))
        if self.architecture == "v2":
            visible = visible + self.card_numbers(features.state_card_numbers)
            own_mask = ((cards[:, 1] != 0) & (cards[:, 2] == 1)).unsqueeze(1)
            opposing_mask = ((cards[:, 1] != 0) & (cards[:, 2] == 2)).unsqueeze(1)
            own = (visible * own_mask).sum(0) / own_mask.sum().clamp(min=1)
            opposing = ((visible * opposing_mask).sum(0)
                        / opposing_mask.sum().clamp(min=1))
            counts = torch.stack([
                ((cards[:, 2] == owner) & (cards[:, 1] == zone)).sum() / 10
                for owner in (1, 2) for zone in range(1, 8)
            ]).to(visible.dtype)
            deck_mask = (features.deck_cards != 0).unsqueeze(1)
            deck = (self.card(features.deck_cards) * deck_mask).sum(0) / (
                deck_mask.sum().clamp(min=1))
            context = (self.phase(features.phase) + self.numbers(features.state_numbers)
                       + self.resource_counts(counts))
            return self.value(torch.cat((own, opposing, context,
                                         self.deck_projection(deck)))).squeeze()
        mask = (cards[:, 1] != 0).unsqueeze(1)
        pooled = (visible * mask).sum(0) / mask.sum().clamp(min=1)
        return self.value(pooled + self.phase(features.phase)
                          + self.numbers(features.state_numbers)).squeeze()

    def forward_batch(self, decisions: Sequence[DecisionFeatures]) -> torch.Tensor:
        """Score visible states together, padding only card and Deck sequences."""
        if not decisions:
            raise ValueError("critic batch requires decisions")
        pad = torch.nn.utils.rnn.pad_sequence
        cards = pad([item.state_cards for item in decisions], batch_first=True)
        card_numbers = pad([item.state_card_numbers for item in decisions],
                           batch_first=True)
        numbers = torch.stack([item.state_numbers for item in decisions])
        phases = torch.stack([item.phase for item in decisions])
        visible = (self.card(cards[:, :, 0]) + self.zone(cards[:, :, 1])
                   + self.owner(cards[:, :, 2]) + self.position(cards[:, :, 3]))
        context = self.phase(phases) + self.numbers(numbers)
        if self.architecture == "v2":
            visible = visible + self.card_numbers(card_numbers)
            own_mask = ((cards[:, :, 1] != 0) & (cards[:, :, 2] == 1)).unsqueeze(2)
            opposing_mask = ((cards[:, :, 1] != 0) & (cards[:, :, 2] == 2)).unsqueeze(2)
            own = (visible * own_mask).sum(1) / own_mask.sum(1).clamp(min=1)
            opposing = ((visible * opposing_mask).sum(1)
                        / opposing_mask.sum(1).clamp(min=1))
            counts = torch.stack([
                ((cards[:, :, 2] == owner) & (cards[:, :, 1] == zone)).sum(1) / 10
                for owner in (1, 2) for zone in range(1, 8)
            ], dim=1).to(visible.dtype)
            decks = pad([item.deck_cards for item in decisions], batch_first=True)
            deck_mask = (decks != 0).unsqueeze(2)
            deck = (self.card(decks) * deck_mask).sum(1) / deck_mask.sum(1).clamp(min=1)
            context = context + self.resource_counts(counts)
            return self.value(torch.cat((own, opposing, context,
                                         self.deck_projection(deck)), dim=1)).squeeze(1)
        mask = (cards[:, :, 1] != 0).unsqueeze(2)
        pooled = (visible * mask).sum(1) / mask.sum(1).clamp(min=1)
        return self.value(pooled + context).squeeze(1)


@dataclass(frozen=True)
class EpisodeResult:
    seed: int
    learner_seat: int
    winner: int | None
    decisions: int
    learner_records: tuple[DecisionRecord, ...]
    trajectory: Trajectory
    learner_features: tuple[DecisionFeatures, ...] = ()

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

    def __reduce__(self):
        """Preserve constructor arguments when a rollout worker raises this."""
        return (type(self), (self.seed, self.max_decisions))


def make_tactical_opponent(_seed: int, flip_codes: frozenset[int],
                           card_races: dict[int, int],
                           card_facts: dict[int, tuple[int, int, int]]) -> Agent:
    """Build a fresh visible-state Tactical agent for one native duel."""
    return TacticalHeuristicAgent(flip_codes, card_races, card_facts=card_facts)


def episode_schedule(matchups: Sequence[tuple[str, str]],
                     seeds: Sequence[int], *,
                     mode: str = "paired_seats") -> tuple[tuple[int, tuple[str, str], int], ...]:
    """Assign learner decks and seats without changing previous schedules."""
    if not matchups or mode not in ("paired_seats", "four_roles"):
        raise ValueError("at least one matchup and a supported schedule mode required")
    schedule = []
    for index, seed in enumerate(seeds):
        if mode == "four_roles":
            a, b = matchups[(index // 4) % len(matchups)]
            role = index % 4
            seat = role % 2
            decks = (a, b) if role in (0, 3) else (b, a)
        else:
            a, b = matchups[(index // 2) % len(matchups)]
            seat = index % 2
            decks = (a, b) if seat == 0 else (b, a)
        schedule.append((seed, decks, seat))
    return tuple(schedule)


def sample_legal_action(model: LegalActionPolicy, vocabulary: CardVocabulary,
                        observation, legal_actions, generator: torch.Generator,
                        temperature: float = 1.0):
    action, _, _ = _sample_legal_action_with_features(
        model, vocabulary, observation, legal_actions, generator, temperature)
    return action


def _selection_progress_actions(legal_actions: Sequence[Action]) -> tuple[Action, ...]:
    """Avoid reversible unselection while a legal forward choice is available."""
    actions = tuple(legal_actions)
    if any(action.kind in ("select_card", "finish_selection") for action in actions):
        return tuple(action for action in actions if action.kind != "unselect_card")
    return actions


def _sample_legal_action_with_features(
    model: LegalActionPolicy, vocabulary: CardVocabulary,
    observation, legal_actions, generator: torch.Generator,
    temperature: float = 1.0,
    scorer: Callable[[DecisionFeatures], torch.Tensor] | None = None,
) -> tuple[Action, DecisionFeatures | None, tuple[Action, ...]]:
    """Sample from visible legal options, with no native-state access."""
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    policy_actions = _selection_progress_actions(legal_actions)
    if len(policy_actions) == 1:
        # A forced choice needs neither feature encoding nor a neural forward
        # pass. It also need not consume the policy's sampling generator.
        return policy_actions[0], None, policy_actions
    features = encode_decision(observation, policy_actions, vocabulary,
                               model.feature_version)
    device = next(model.parameters()).device
    with torch.inference_mode():
        logits = (scorer(features.to(device)) if scorer is not None
                  else model(features.to(device))) / temperature
        probabilities = torch.softmax(logits, dim=0).cpu()
        index = int(torch.multinomial(probabilities, 1, generator=generator).item())
    return policy_actions[index], features, policy_actions


class _FlatPolicy(nn.Module):
    """Expose the existing scorer's tensor inputs to TorchScript tracing."""

    def __init__(self, model: LegalActionPolicy) -> None:
        super().__init__()
        self.model = model

    def forward(self, *inputs: torch.Tensor) -> torch.Tensor:
        return self.model(DecisionFeatures(*inputs))


class TracedRolloutScorer:
    """Trace a frozen policy once, on its first player-visible decision."""

    def __init__(self, model: LegalActionPolicy) -> None:
        if model.feature_version != 23 or model.training:
            raise ValueError("traced rollout inference requires an eval-mode v23 policy")
        self.model = model
        self.traced = None

    def __call__(self, features: DecisionFeatures) -> torch.Tensor:
        inputs = tuple(features.__dict__.values())
        if self.traced is None:
            self.traced = torch.jit.trace(_FlatPolicy(self.model), inputs,
                                          check_trace=False)
            if not torch.equal(self.model(features), self.traced(*inputs)):
                raise RuntimeError("traced policy changed initial action scores")
        return self.traced(*inputs)


class SamplingPolicyAgent:
    def __init__(self, model: LegalActionPolicy, vocabulary: CardVocabulary,
                 generator: torch.Generator) -> None:
        self.model = model
        self.vocabulary = vocabulary
        self.generator = generator

    def select_action(self, observation, legal_actions):
        return sample_legal_action(self.model, self.vocabulary, observation,
                                   legal_actions, self.generator)


def independent_opponent_generator(seed: int) -> torch.Generator:
    """Give a frozen opponent its own deterministic action-sampling stream."""
    return torch.Generator(device="cpu").manual_seed(
        (seed ^ 0x9E3779B97F4A7C15) & ((1 << 64) - 1))


def run_learning_episode(
    model: LegalActionPolicy, vocabulary: CardVocabulary, opponent: Agent,
    decks: tuple[str, str], seed: int, learner_seat: int,
    engine_factory: Callable[[], RulesEngine], generator: torch.Generator,
    max_decisions: int = 5000, learner_temperature: float = 1.0,
    collect_features: bool = False,
    rollout_scorer: TracedRolloutScorer | None = None,
) -> EpisodeResult:
    if learner_seat not in (0, 1) or max_decisions < 1 or learner_temperature <= 0:
        raise ValueError("invalid learner seat or decision cap")
    records = []
    learner_features = []
    if rollout_scorer is not None:
        model.eval()
    with GoatEnvironment(*decks, seed=seed, engine=engine_factory()) as env:
        observation = env.reset()
        for count in range(1, max_decisions + 1):
            legal_actions = env.legal_actions()
            if observation.acting_player == learner_seat:
                action, features, policy_actions = _sample_legal_action_with_features(
                    model, vocabulary, observation, legal_actions, generator,
                    temperature=learner_temperature, scorer=rollout_scorer)
                if len(policy_actions) > 1:
                    records.append(DecisionRecord(observation, policy_actions, action))
                    if collect_features:
                        assert features is not None
                        learner_features.append(features)
            else:
                action = opponent.select_action(observation, legal_actions)
            observation = env.step(action)
            if env.is_terminal():
                trajectory = replace(env.trajectory(), source="self_play_rl",
                                     skill_metadata={"learner_seat": learner_seat,
                                                     "demonstrator_seat": learner_seat})
                return EpisodeResult(seed, learner_seat, env.result(), count,
                                     tuple(records), trajectory, tuple(learner_features))
    raise EpisodeDecisionLimit(seed, max_decisions)


def run_batched_learning_episodes(
    model: LegalActionPolicy, vocabulary: CardVocabulary,
    games: Sequence[tuple[Agent, tuple[str, str], int, int, torch.Generator]],
    engine_factory: Callable[[], RulesEngine], *, max_decisions: int = 5000,
    learner_temperature: float = 1.0,
    collect_features: bool = False,
) -> tuple[EpisodeResult, ...]:
    """Run independent native duels together and batch only learner inference.

    Each duel keeps its own engine, observation, and sampling generator. No
    hidden simulator state is shared with or passed to the policy.
    """
    if (not games or max_decisions < 1 or learner_temperature <= 0
            or model.feature_version < 10
            or model.feature_version in CHAIN_TARGET_FEATURE_VERSIONS
            or any(seat not in (0, 1) for _, _, _, seat, _ in games)):
        raise ValueError("batched rollout requires v10+ policy and valid games")
    with ExitStack() as stack:
        environments = [stack.enter_context(GoatEnvironment(
            *decks, seed=seed, engine=engine_factory()))
            for _, decks, seed, _, _ in games]
        observations = [env.reset() for env in environments]
        counts = [0] * len(games)
        records: list[list[DecisionRecord]] = [[] for _ in games]
        feature_records: list[list[DecisionFeatures]] = [[] for _ in games]
        results: list[EpisodeResult | None] = [None] * len(games)
        remaining = set(range(len(games)))

        def advance(index: int, action) -> None:
            _, _, seed, seat, _ = games[index]
            env = environments[index]
            legal = env.legal_actions()
            observation = observations[index]
            policy_actions = (_selection_progress_actions(legal)
                              if observation.acting_player == seat else ())
            if len(policy_actions) > 1:
                records[index].append(DecisionRecord(observation, policy_actions, action))
            counts[index] += 1
            observations[index] = env.step(action)
            if env.is_terminal():
                trajectory = replace(env.trajectory(), source="self_play_rl",
                                     skill_metadata={"learner_seat": seat,
                                                     "demonstrator_seat": seat})
                results[index] = EpisodeResult(seed, seat, env.result(), counts[index],
                                               tuple(records[index]), trajectory,
                                               tuple(feature_records[index]))
                remaining.remove(index)

        while remaining:
            ready = []
            for index in sorted(remaining):
                opponent, _, seed, seat, _ = games[index]
                env = environments[index]
                while index in remaining:
                    if counts[index] >= max_decisions:
                        raise EpisodeDecisionLimit(seed, max_decisions)
                    legal = env.legal_actions()
                    observation = observations[index]
                    policy_actions = (_selection_progress_actions(legal)
                                      if observation.acting_player == seat else ())
                    if len(policy_actions) > 1:
                        ready.append(index)
                        break
                    action = (policy_actions[0] if observation.acting_player == seat
                              else opponent.select_action(observation, legal))
                    advance(index, action)
            if not ready:
                continue
            policy_actions = [_selection_progress_actions(
                environments[index].legal_actions()) for index in ready]
            features = [encode_decision(observations[index], actions,
                                        vocabulary, model.feature_version)
                        for index, actions in zip(ready, policy_actions, strict=True)]
            if collect_features:
                for index, features_for_index in zip(ready, features, strict=True):
                    feature_records[index].append(features_for_index)
            device = next(model.parameters()).device
            with torch.inference_mode():
                if len(ready) == 1:
                    logits = [model(features[0].to(device))]
                else:
                    batch, _ = model.forward_batch(
                        [item.to(device) for item in features])
                    logits = [batch[row, :len(actions)]
                              for row, actions in enumerate(policy_actions)]
                chosen = []
                for index, scores, actions in zip(ready, logits, policy_actions,
                                                   strict=True):
                    generator = games[index][4]
                    probabilities = torch.softmax(scores / learner_temperature,
                                                  dim=0).cpu()
                    choice = int(torch.multinomial(probabilities, 1,
                                                   generator=generator).item())
                    chosen.append(actions[choice])
            for index, action in zip(ready, chosen, strict=True):
                advance(index, action)
        return tuple(result for result in results if result is not None)


def _parallel_rollout_worker(task):
    """Collect one CPU duel with a per-episode sampling stream."""
    (model_state, vocabulary, width, feature_version, opponent_state, decks,
     seed, learner_seat, engine_factory, max_decisions, temperature,
     generator_seed, baseline_opponent_factory, independent_opponent_rng) = task
    torch.set_num_threads(1)
    model = LegalActionPolicy(vocabulary.size, width=width,
                              feature_version=feature_version)
    model.load_state_dict(model_state)
    model.eval()
    generator = torch.Generator(device="cpu").manual_seed(generator_seed)
    if opponent_state is None:
        opponent: Agent = baseline_opponent_factory(seed)
    else:
        frozen = LegalActionPolicy(vocabulary.size, width=width,
                                   feature_version=feature_version)
        frozen.load_state_dict(opponent_state)
        frozen.eval()
        opponent = SamplingPolicyAgent(
            frozen, vocabulary,
            (independent_opponent_generator(generator_seed)
             if independent_opponent_rng else generator))
    return run_learning_episode(model, vocabulary, opponent, decks, seed,
                                learner_seat, engine_factory, generator,
                                max_decisions, temperature)


def policy_gradient_update(model: LegalActionPolicy, vocabulary: CardVocabulary,
                           records: Sequence[DecisionRecord], reward: float,
                           baseline: float, optimizer: torch.optim.Optimizer,
                           entropy_coefficient: float = 0.0,
                           max_gradient_norm: float = 1.0,
                           temperature: float = 1.0,
                           state_baselines: Sequence[float] | None = None,
                           reduction: str = "sum",
                           parent_model: LegalActionPolicy | None = None,
                           parent_kl_weight: float = 0.0,
                           batch_size: int = 1) -> float:
    """Apply one terminal-return score-function update; return mean loss."""
    if (not records or entropy_coefficient < 0 or max_gradient_norm <= 0
            or batch_size < 1
            or temperature <= 0 or reduction not in ("sum", "mean")):
        raise ValueError("update needs decisions, positive temperature, and valid regularization")
    if batch_size > 1 and (model.feature_version < 10
                           or model.feature_version in (14, 15)):
        raise ValueError("batched REINFORCE requires a supported v10+ feature version")
    if (not isfinite(parent_kl_weight) or parent_kl_weight < 0
            or parent_kl_weight > 0 and parent_model is None):
        raise ValueError("parent KL needs a frozen parent and nonnegative weight")
    if (state_baselines is not None
            and (len(state_baselines) != len(records)
                 or any(not isfinite(value) for value in state_baselines))):
        raise ValueError("state baselines must be finite and match decisions")
    optimizer.zero_grad()
    device = next(model.parameters()).device
    total = 0.0
    if batch_size > 1:
        for start in range(0, len(records), batch_size):
            batch = records[start:start + batch_size]
            features = [encode_decision(record.observation, record.legal_actions,
                                        vocabulary, model.feature_version).to(device)
                        for record in batch]
            logits, _ = model.forward_batch(features)
            log_probs = torch.log_softmax(logits / temperature, dim=1)
            probabilities = log_probs.exp()
            choices = torch.tensor([
                record.legal_actions.index(record.selected_action) for record in batch],
                dtype=torch.long, device=device)
            chosen = log_probs.gather(1, choices[:, None]).squeeze(1)
            advantages = torch.tensor([
                reward - (state_baselines[start + index]
                          if state_baselines is not None else baseline)
                for index in range(len(batch))], dtype=chosen.dtype, device=device)
            entropy = -(probabilities * log_probs).sum(1)
            losses = -advantages * chosen - entropy_coefficient * entropy
            if parent_kl_weight:
                with torch.no_grad():
                    parent_logits, _ = parent_model.forward_batch(features)
                    parent_log_probs = torch.log_softmax(
                        parent_logits / temperature, dim=1)
                    parent_probs = parent_log_probs.exp()
                losses = losses + parent_kl_weight * (
                    parent_probs * (parent_log_probs - log_probs)).sum(1)
            (losses.sum() / len(records) if reduction == "mean"
             else losses.sum()).backward()
            total += float(losses.detach().sum())
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_gradient_norm)
        optimizer.step()
        return total / len(records)
    for index, record in enumerate(records):
        advantage = reward - (state_baselines[index]
                              if state_baselines is not None else baseline)
        features = encode_decision(record.observation, record.legal_actions,
                                   vocabulary, model.feature_version).to(device)
        logits = model(features) / temperature
        log_probabilities = torch.log_softmax(logits, dim=0)
        probabilities = log_probabilities.exp()
        selected = record.legal_actions.index(record.selected_action)
        entropy = -(probabilities * log_probabilities).sum()
        loss = -advantage * log_probabilities[selected] - entropy_coefficient * entropy
        if parent_kl_weight:
            with torch.no_grad():
                parent_log_probs = torch.log_softmax(parent_model(features) / temperature, 0)
                parent_probs = parent_log_probs.exp()
            loss = loss + parent_kl_weight * (
                parent_probs * (parent_log_probs - log_probabilities)).sum()
        (loss / len(records) if reduction == "mean" else loss).backward()
        total += float(loss.detach())
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_gradient_norm)
    optimizer.step()
    return total / len(records)


def clipped_surrogate(ratio: torch.Tensor, advantage: torch.Tensor,
                      clip_epsilon: float) -> torch.Tensor:
    """PPO's pessimistic per-decision clipped probability-ratio objective."""
    if not 0 < clip_epsilon < 1:
        raise ValueError("PPO clip epsilon must be between zero and one")
    return torch.minimum(ratio * advantage,
                         ratio.clamp(1 - clip_epsilon, 1 + clip_epsilon) * advantage)


def terminal_gae_advantages(values: Sequence[float], reward: float,
                            trace_lambda: float) -> tuple[float, ...]:
    """Undiscounted GAE over learner decisions with a terminal-only reward.

    Opponent and forced actions occur between these decision states. The frozen
    visible-state predictions are evaluated before the policy update. With
    lambda=1 this reduces exactly to the existing reward-minus-value baseline.
    """
    if (not values or not isfinite(reward) or not isfinite(trace_lambda)
            or not 0 <= trace_lambda <= 1
            or any(not isfinite(value) for value in values)):
        raise ValueError("GAE needs finite values, reward, and lambda in [0, 1]")
    result = [0.0] * len(values)
    advantage = 0.0
    for index in range(len(values) - 1, -1, -1):
        next_value = values[index + 1] if index + 1 < len(values) else 0.0
        immediate_reward = reward if index + 1 == len(values) else 0.0
        delta = immediate_reward + next_value - values[index]
        advantage = delta + trace_lambda * advantage
        result[index] = advantage
    return tuple(result)


def ppo_clipped_update(
    model: LegalActionPolicy, vocabulary: CardVocabulary,
    records: Sequence[DecisionRecord], reward: float, baseline: float,
    optimizer: torch.optim.Optimizer, *, epochs: int = 2,
    batch_size: int = 16, clip_epsilon: float = 0.2,
    entropy_coefficient: float = 0.0, max_gradient_norm: float = 1.0,
    temperature: float = 1.0,
    state_baselines: Sequence[float] | None = None,
    parent_model: LegalActionPolicy | None = None,
    parent_kl_weight: float = 0.0,
    random_seed: int = 0,
    advantages: Sequence[float] | None = None,
    sample_weights: Sequence[float] | None = None,
    encoded_features: Sequence[DecisionFeatures] | None = None,
) -> float:
    """Reuse on-policy visible decisions with a clipped objective.

    The pre-update policy supplies fixed action log probabilities. Callers
    may supply per-decision advantages from several frozen-policy duels.
    """
    if (not records or epochs < 1 or batch_size < 1 or temperature <= 0
            or entropy_coefficient < 0 or max_gradient_norm <= 0
            or not isfinite(reward) or not isfinite(baseline)
            or not isfinite(parent_kl_weight) or parent_kl_weight < 0
            or parent_kl_weight > 0 and parent_model is None):
        raise ValueError("PPO update needs valid decisions, rewards, and regularization")
    if (model.feature_version < 10 or model.feature_version in (14, 15)):
        raise ValueError("PPO batching requires a supported v10+ feature version")
    if (state_baselines is not None
            and (len(state_baselines) != len(records)
                 or any(not isfinite(value) for value in state_baselines))):
        raise ValueError("state baselines must be finite and match decisions")
    if (advantages is not None
            and (len(advantages) != len(records)
                 or any(not isfinite(value) for value in advantages))):
        raise ValueError("advantages must be finite and match decisions")
    if (sample_weights is not None
            and (len(sample_weights) != len(records)
                 or any(not isfinite(weight) or weight <= 0
                        for weight in sample_weights))):
        raise ValueError("sample weights must be positive, finite, and match decisions")
    if encoded_features is not None and len(encoded_features) != len(records):
        raise ValueError("encoded features must match decisions")
    if not 0 < clip_epsilon < 1:
        raise ValueError("PPO clip epsilon must be between zero and one")
    device = next(model.parameters()).device
    features = ([encode_decision(record.observation, record.legal_actions,
                                 vocabulary, model.feature_version).to(device)
                 for record in records]
                if encoded_features is None else
                [item.to(device) for item in encoded_features])
    selected = [record.legal_actions.index(record.selected_action) for record in records]
    old_log_probs = []
    parent_log_prob_rows: list[torch.Tensor] = []
    parent_prob_rows: list[torch.Tensor] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(records), batch_size):
            batch = features[start:start + batch_size]
            logits, _ = model.forward_batch(batch)
            choices = torch.tensor(selected[start:start + batch_size],
                                   dtype=torch.long, device=device)
            log_probs = torch.log_softmax(logits / temperature, dim=1)
            old_log_probs.extend(log_probs.gather(1, choices[:, None]).squeeze(1).tolist())
            if parent_kl_weight:
                parent_logits, _ = parent_model.forward_batch(batch)
                parent_log_probs = torch.log_softmax(parent_logits / temperature, dim=1)
                for row, record in zip(parent_log_probs, records[start:start + batch_size],
                                       strict=True):
                    trimmed = row[:len(record.legal_actions)].clone()
                    parent_log_prob_rows.append(trimmed)
                    parent_prob_rows.append(trimmed.exp())
    model.train()
    rng = random.Random(random_seed)
    total_loss = 0.0
    updates = 0
    for _ in range(epochs):
        order = list(range(len(records)))
        rng.shuffle(order)
        for start in range(0, len(order), batch_size):
            indices = order[start:start + batch_size]
            logits, _ = model.forward_batch([features[index] for index in indices])
            log_probs = torch.log_softmax(logits / temperature, dim=1)
            probabilities = log_probs.exp()
            choices = torch.tensor([selected[index] for index in indices],
                                   dtype=torch.long, device=device)
            chosen_log_probs = log_probs.gather(1, choices[:, None]).squeeze(1)
            previous = torch.tensor([old_log_probs[index] for index in indices],
                                    dtype=chosen_log_probs.dtype, device=device)
            advantage = torch.tensor([
                advantages[index] if advantages is not None else reward - (
                    state_baselines[index] if state_baselines is not None else baseline)
                for index in indices],
                dtype=chosen_log_probs.dtype, device=device)
            weights = (torch.tensor([sample_weights[index] for index in indices],
                                    dtype=chosen_log_probs.dtype, device=device)
                       if sample_weights is not None else torch.ones_like(advantage))
            ratio = (chosen_log_probs - previous).exp()
            entropy = -(probabilities * log_probs).sum(1)
            loss = (-(weights * clipped_surrogate(
                ratio, advantage, clip_epsilon)).mean()
                    - entropy_coefficient * (weights * entropy).mean())
            if parent_kl_weight:
                parent_log_probs = torch.nn.utils.rnn.pad_sequence(
                    [parent_log_prob_rows[index] for index in indices],
                    batch_first=True, padding_value=0.0)
                parent_probs = torch.nn.utils.rnn.pad_sequence(
                    [parent_prob_rows[index] for index in indices],
                    batch_first=True, padding_value=0.0)
                loss = loss + parent_kl_weight * (
                    weights * (parent_probs * (
                        parent_log_probs - log_probs)).sum(1)).mean()
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_gradient_norm)
            optimizer.step()
            total_loss += float(loss.detach())
            updates += 1
    return total_loss / updates


def predict_state_values(value_model: VisibleStateValue,
                         vocabulary: CardVocabulary,
                         records: Sequence[DecisionRecord],
                         feature_version: int,
                         batch_size: int = 32) -> tuple[float, ...]:
    """Freeze critic predictions before updating either model on an episode."""
    if batch_size < 1:
        raise ValueError("critic batch size must be positive")
    device = next(value_model.parameters()).device
    value_model.eval()
    with torch.no_grad():
        values = []
        for start in range(0, len(records), batch_size):
            features = [encode_decision(record.observation, record.legal_actions,
                                        vocabulary, feature_version).to(device)
                        for record in records[start:start + batch_size]]
            values.extend(value_model.forward_batch(features).tolist())
        return tuple(values)


def state_value_update(value_model: VisibleStateValue,
                       vocabulary: CardVocabulary,
                       records: Sequence[DecisionRecord], reward: float,
                       feature_version: int,
                       optimizer: torch.optim.Optimizer,
                       max_gradient_norm: float = 1.0,
                       batch_size: int = 32) -> float:
    """Fit visible-state outcome estimates to the completed duel's return."""
    if not records or max_gradient_norm <= 0 or not isfinite(reward) or batch_size < 1:
        raise ValueError("value update needs decisions and finite terminal reward")
    device = next(value_model.parameters()).device
    value_model.train()
    optimizer.zero_grad()
    total = 0.0
    for start in range(0, len(records), batch_size):
        features = [encode_decision(record.observation, record.legal_actions,
                                    vocabulary, feature_version).to(device)
                    for record in records[start:start + batch_size]]
        losses = (value_model.forward_batch(features) - reward).square()
        (losses.sum() / len(records)).backward()
        total += float(losses.detach().sum())
    torch.nn.utils.clip_grad_norm_(value_model.parameters(), max_gradient_norm)
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
    baseline_scope: str = "global",
    schedule_mode: str = "paired_seats",
    value_model: VisibleStateValue | None = None,
    resource_value_model: FrozenResourceRidge | None = None,
    value_learning_rate: float = 1e-3,
    policy_gradient_reduction: str = "sum",
    parent_kl_weight: float = 0.0,
    policy_update: str = "reinforce",
    reinforce_batch_size: int = 1,
    ppo_epochs: int = 2,
    ppo_batch_size: int = 16,
    ppo_clip_epsilon: float = 0.2,
    ppo_rollout_games: int = 1,
    ppo_rollout_weighting: str = "per_decision",
    ppo_baseline_timing: str = "online",
    ppo_gae_lambda: float | None = None,
    rollout_workers: int = 0,
    rollout_batch_inference: bool = False,
    trace_rollout_inference: bool = False,
    reuse_rollout_features: bool = False,
    skip_capped_games: bool = False,
    skip_unsupported_games: bool = False,
    baseline_opponent_factory: Callable[[int], Agent] = RandomAgent,
    baseline_opponent_name: str = "random",
    independent_opponent_rng: bool = False,
    record_episode: Callable[[int, EpisodeResult], None] | None = None,
) -> tuple[dict, ...]:
    """Train one learner seat per duel against a baseline or frozen past policies.

    Frozen snapshots prevent the opponent from changing within an episode.
    PPO can update from one or several duels sampled under the same policy.
    Neither branch is league training or an established competitive policy.
    """
    if (not matchups or not seeds or learning_rate <= 0 or snapshot_every < 1
            or max_snapshots < 1 or learner_temperature <= 0
            or not 0 <= historical_probability <= 1
            or baseline_scope not in ("global", "learner_deck", "state_value",
                                      "resource_ridge")
            or policy_gradient_reduction not in ("sum", "mean")
            or value_learning_rate <= 0
            or not isfinite(parent_kl_weight) or parent_kl_weight < 0
            or (baseline_scope == "state_value") != (value_model is not None)
            or (baseline_scope == "resource_ridge") != (resource_value_model is not None)
            or not callable(baseline_opponent_factory)
            or not baseline_opponent_name
            or (ppo_gae_lambda is not None and
                (not isfinite(ppo_gae_lambda) or not 0 <= ppo_gae_lambda <= 1
                 or policy_update != "clipped_ppo" or resource_value_model is None
                 or ppo_baseline_timing == "leave_one_out"))
            or schedule_mode not in ("paired_seats", "four_roles")):
        raise ValueError("invalid self-play schedule or hyperparameters")
    if (policy_update not in ("reinforce", "clipped_ppo")
            or reinforce_batch_size < 1 or ppo_epochs < 1
            or ppo_batch_size < 1 or ppo_rollout_games < 1
            or rollout_workers < 0
            or ppo_rollout_weighting not in ("per_decision", "per_episode")
            or ppo_baseline_timing not in ("online", "frozen_rollout", "leave_one_out")
            or not 0 < ppo_clip_epsilon < 1):
        raise ValueError("invalid self-play policy update")
    if ppo_baseline_timing in ("frozen_rollout", "leave_one_out") and (
            policy_update != "clipped_ppo" or ppo_rollout_games < 2):
        raise ValueError("rollout baseline requires multi-duel PPO")
    if resource_value_model is not None and (
            policy_update != "clipped_ppo" or ppo_baseline_timing != "online"):
        raise ValueError("frozen resource ridge requires PPO and online baseline timing")
    if ppo_rollout_games > 1 and (policy_update != "clipped_ppo"
                                  or baseline_scope == "state_value"
                                  or skip_capped_games or skip_unsupported_games
                                  or snapshot_every % ppo_rollout_games):
        raise ValueError("multi-duel PPO requires terminal duels, a moving baseline, "
                         "and snapshot intervals divisible by rollout size")
    if rollout_workers and (policy_update != "clipped_ppo"
                            or ppo_rollout_games < 2
                            or skip_capped_games or skip_unsupported_games
                            or baseline_scope == "state_value"):
        raise ValueError("parallel rollout needs multi-duel PPO and terminal games")
    if rollout_batch_inference and (
            rollout_workers or policy_update != "clipped_ppo"
            or ppo_rollout_games < 2 or skip_capped_games
            or skip_unsupported_games or baseline_scope == "state_value"):
        raise ValueError("batched inference needs multi-duel PPO without workers or skips")
    if trace_rollout_inference and (model.feature_version != 23
                                    or policy_update != "clipped_ppo"
                                    or ppo_rollout_games < 2
                                    or rollout_workers or rollout_batch_inference):
        raise ValueError("traced rollout inference needs single-process v23 "
                         "multi-duel PPO")
    if reuse_rollout_features and (policy_update != "clipped_ppo" or rollout_workers):
        raise ValueError("rollout feature reuse needs single-process PPO")
    if (policy_update == "clipped_ppo" and
            (model.feature_version < 10 or model.feature_version in (14, 15))):
        raise ValueError("clipped PPO requires a supported batched policy version")
    if reinforce_batch_size > 1 and (policy_update != "reinforce"
                                     or model.feature_version < 10
                                     or model.feature_version in (14, 15)):
        raise ValueError("batched REINFORCE requires REINFORCE and a supported v10+ policy")
    rng = random.Random(random_seed)
    generator = torch.Generator(device="cpu").manual_seed(random_seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    parent_model = (copy.deepcopy(model).eval().requires_grad_(False)
                    if parent_kl_weight else None)
    value_optimizer = (torch.optim.Adam(value_model.parameters(),
                                        lr=value_learning_rate)
                       if value_model is not None else None)
    snapshots = [copy.deepcopy(model.state_dict())]
    baselines: dict[str, float] = {}
    rollout_baselines: dict[str, float] = {}
    reports = []
    rollout_records: list[DecisionRecord] = []
    rollout_features: list[DecisionFeatures] = []
    rollout_advantages: list[float] = []
    rollout_record_counts: list[int] = []
    rollout_report_indices: list[int] = []
    rollout_rewards: list[float] = []
    rollout_keys: list[str] = []
    rollout_all_report_indices: list[int] = []
    rollout_record_episode_indices: list[int] = []
    schedule = episode_schedule(matchups, seeds, mode=schedule_mode)
    pool = (ProcessPoolExecutor(max_workers=min(rollout_workers, ppo_rollout_games),
                                mp_context=get_context("spawn"))
            if rollout_workers > 1 else None)
    rollout_scorer = None
    try:
        parallel_batch: dict[int, tuple[EpisodeResult, str]] = {}
        for index, (seed, decks, learner_seat) in enumerate(schedule):
            if (trace_rollout_inference and not rollout_workers
                    and index % ppo_rollout_games == 0):
                model.eval()
                rollout_scorer = TracedRolloutScorer(model)
            if (ppo_baseline_timing in ("frozen_rollout", "leave_one_out")
                    and index % ppo_rollout_games == 0):
                rollout_baselines = baselines.copy()
            if (rollout_workers or rollout_batch_inference) and index % ppo_rollout_games == 0:
                model_state = (None if rollout_batch_inference
                               else copy.deepcopy(model.state_dict()))
                tasks = []
                names = []
                for batch_index in range(index, min(index + ppo_rollout_games, len(schedule))):
                    batch_seed, batch_decks, batch_seat = schedule[batch_index]
                    snapshot_index = (rng.randrange(len(snapshots))
                                      if rng.random() < historical_probability else None)
                    names.append(f"snapshot_{snapshot_index}" if snapshot_index is not None
                                 else baseline_opponent_name)
                    tasks.append((model_state, vocabulary, model.card.embedding_dim,
                                  model.feature_version,
                                  snapshots[snapshot_index] if snapshot_index is not None else None,
                                  batch_decks, batch_seed, batch_seat, engine_factory,
                                  max_decisions, learner_temperature,
                                  random_seed + batch_seed, baseline_opponent_factory,
                                  independent_opponent_rng))
                if rollout_batch_inference:
                    batch_games = []
                    for task in tasks:
                        (_, _, _, _, opponent_state, batch_decks, batch_seed,
                         batch_seat, _, _, _, generator_seed, _, _) = task
                        batch_generator = torch.Generator(device="cpu").manual_seed(
                            generator_seed)
                        if opponent_state is None:
                            batch_opponent: Agent = baseline_opponent_factory(batch_seed)
                        else:
                            frozen = LegalActionPolicy(
                                vocabulary.size, width=model.card.embedding_dim,
                                feature_version=model.feature_version)
                            frozen.load_state_dict(opponent_state)
                            frozen.eval()
                            batch_opponent = SamplingPolicyAgent(
                                frozen, vocabulary,
                                (independent_opponent_generator(generator_seed)
                                 if independent_opponent_rng else batch_generator))
                        batch_games.append((batch_opponent, batch_decks,
                                            batch_seed, batch_seat, batch_generator))
                    episodes = run_batched_learning_episodes(
                        model, vocabulary, batch_games, engine_factory,
                        max_decisions=max_decisions,
                        learner_temperature=learner_temperature,
                        collect_features=reuse_rollout_features)
                elif rollout_workers == 1:
                    previous_threads = torch.get_num_threads()
                    try:
                        episodes = list(map(_parallel_rollout_worker, tasks))
                    finally:
                        torch.set_num_threads(previous_threads)
                else:
                    episodes = list(pool.map(_parallel_rollout_worker, tasks))
                parallel_batch = {batch_index: (episode, name)
                                  for batch_index, (episode, name) in enumerate(
                                      zip(episodes, names, strict=True), start=index)}
            if rollout_workers or rollout_batch_inference:
                episode, opponent_name = parallel_batch.pop(index)
            else:
                if rng.random() < historical_probability:
                    snapshot_index = rng.randrange(len(snapshots))
                    frozen = LegalActionPolicy(vocabulary.size, width=model.card.embedding_dim,
                                               feature_version=model.feature_version)
                    frozen.load_state_dict(snapshots[snapshot_index])
                    frozen.eval()

                    opponent: Agent = SamplingPolicyAgent(
                        frozen, vocabulary,
                        (independent_opponent_generator(random_seed + seed)
                         if independent_opponent_rng else generator))
                    opponent_name = f"snapshot_{snapshot_index}"
                else:
                    opponent = baseline_opponent_factory(seed)
                    opponent_name = baseline_opponent_name
                try:
                    episode = run_learning_episode(model, vocabulary, opponent, decks, seed,
                                                   learner_seat, engine_factory, generator,
                                                   max_decisions, learner_temperature,
                                                   **({"rollout_scorer": rollout_scorer}
                                                      if trace_rollout_inference else {}),
                                                   **({"collect_features": True}
                                                      if reuse_rollout_features else {}))
                except EpisodeDecisionLimit:
                    if not skip_capped_games:
                        raise
                    reports.append({"seed": seed, "learner_seat": learner_seat,
                                    "decks": decks, "opponent": opponent_name,
                                    "status": "decision_limit", "decisions": max_decisions,
                                    "learner_decisions": 0, "policy_loss": None,
                                    "value_loss": None})
                    continue
                except SimulatorUnavailable as exc:
                    if not skip_unsupported_games:
                        raise
                    reports.append({"seed": seed, "learner_seat": learner_seat,
                                    "decks": decks, "opponent": opponent_name,
                                    "status": "simulator_unavailable", "error": str(exc),
                                    "learner_decisions": 0, "policy_loss": None,
                                    "value_loss": None})
                    continue
            if record_episode is not None:
                record_episode(index, episode)
            baseline_key = decks[learner_seat] if baseline_scope == "learner_deck" else "global"
            state_baselines = (
                predict_state_values(value_model, vocabulary, episode.learner_records,
                                     model.feature_version)
                if value_model is not None and episode.learner_records else
                resource_value_model.predict_records(
                    episode.learner_records, vocabulary, model.feature_version)
                if resource_value_model is not None and episode.learner_records
                else None)
            baseline = (sum(state_baselines) / len(state_baselines)
                        if state_baselines else
                        (rollout_baselines if ppo_baseline_timing in
                         ("frozen_rollout", "leave_one_out")
                         else baselines).get(baseline_key, 0.0))
            loss = None
            if episode.learner_records:
                if policy_update == "clipped_ppo":
                    if ppo_rollout_games == 1:
                        loss = ppo_clipped_update(
                            model, vocabulary, episode.learner_records,
                            episode.reward, baseline, optimizer,
                            epochs=ppo_epochs, batch_size=ppo_batch_size,
                            clip_epsilon=ppo_clip_epsilon,
                            entropy_coefficient=entropy_coefficient,
                            temperature=learner_temperature,
                            state_baselines=state_baselines,
                            advantages=(terminal_gae_advantages(
                                state_baselines, episode.reward, ppo_gae_lambda)
                                if ppo_gae_lambda is not None else None),
                            parent_model=parent_model,
                            parent_kl_weight=parent_kl_weight,
                            random_seed=random_seed + seed,
                            encoded_features=(episode.learner_features
                                              if reuse_rollout_features else None))
                    else:
                        rollout_records.extend(episode.learner_records)
                        if reuse_rollout_features:
                            rollout_features.extend(episode.learner_features)
                        rollout_advantages.extend(
                            terminal_gae_advantages(state_baselines, episode.reward,
                                                    ppo_gae_lambda)
                            if ppo_gae_lambda is not None else
                            (episode.reward - value for value in state_baselines)
                            if state_baselines is not None else
                            [episode.reward - baseline] * len(episode.learner_records))
                        if ppo_baseline_timing == "leave_one_out":
                            rollout_record_episode_indices.extend(
                                [len(rollout_rewards)] * len(episode.learner_records))
                        rollout_record_counts.append(len(episode.learner_records))
                        rollout_report_indices.append(len(reports))
                else:
                    loss = policy_gradient_update(
                        model, vocabulary, episode.learner_records,
                        episode.reward, baseline, optimizer,
                        entropy_coefficient,
                        temperature=learner_temperature,
                        state_baselines=state_baselines,
                        reduction=policy_gradient_reduction,
                        parent_model=parent_model,
                        parent_kl_weight=parent_kl_weight,
                        batch_size=reinforce_batch_size)
            value_loss = (state_value_update(
                value_model, vocabulary, episode.learner_records, episode.reward,
                model.feature_version, value_optimizer)
                if value_model is not None and episode.learner_records else None)
            if value_model is None and resource_value_model is None:
                baselines[baseline_key] = (
                    0.95 * baselines.get(baseline_key, 0.0)
                    + 0.05 * episode.reward)
            reports.append({"seed": seed, "learner_seat": learner_seat,
                            "decks": decks, "opponent": opponent_name,
                            "status": "terminal",
                            "deck_sha256": episode.trajectory.deck_sha256,
                            "asset_sha256": episode.trajectory.asset_sha256,
                            "rules_profile": episode.trajectory.rules_profile,
                            "winner": episode.winner, "reward": episode.reward,
                            "baseline": baseline,
                            "decisions": episode.decisions,
                            "learner_decisions": len(episode.learner_records),
                            "policy_loss": loss, "value_loss": value_loss})
            if ppo_baseline_timing == "leave_one_out":
                rollout_rewards.append(episode.reward)
                rollout_keys.append(baseline_key)
                rollout_all_report_indices.append(len(reports) - 1)
            if (ppo_rollout_games > 1
                    and ((index + 1) % ppo_rollout_games == 0 or index + 1 == len(seeds))):
                if ppo_baseline_timing == "leave_one_out":
                    totals: dict[str, tuple[float, int]] = {}
                    for key, reward in zip(rollout_keys, rollout_rewards, strict=True):
                        total, count = totals.get(key, (0.0, 0))
                        totals[key] = (total + reward, count + 1)
                    episode_baselines = []
                    for key, reward, report_index in zip(
                            rollout_keys, rollout_rewards,
                            rollout_all_report_indices, strict=True):
                        total, count = totals[key]
                        estimate = ((total - reward) / (count - 1) if count > 1
                                    else rollout_baselines.get(key, 0.0))
                        episode_baselines.append(estimate)
                        reports[report_index]["baseline"] = estimate
                    rollout_advantages = [
                        rollout_rewards[episode_index] - episode_baselines[episode_index]
                        for episode_index in rollout_record_episode_indices]
                if rollout_records:
                    weights = None
                    if ppo_rollout_weighting == "per_episode":
                        weights = [len(rollout_records) / (len(rollout_record_counts) * count)
                                   for count in rollout_record_counts for _ in range(count)]
                    rollout_loss = ppo_clipped_update(
                        model, vocabulary, rollout_records, 0.0, 0.0, optimizer,
                        epochs=ppo_epochs, batch_size=ppo_batch_size,
                        clip_epsilon=ppo_clip_epsilon,
                        entropy_coefficient=entropy_coefficient,
                        temperature=learner_temperature,
                        parent_model=parent_model,
                        parent_kl_weight=parent_kl_weight,
                        random_seed=random_seed + seed,
                        advantages=rollout_advantages, sample_weights=weights,
                        encoded_features=(rollout_features if reuse_rollout_features else None))
                    for report_index in rollout_report_indices:
                        reports[report_index]["policy_loss"] = rollout_loss
                rollout_records.clear()
                rollout_features.clear()
                rollout_advantages.clear()
                rollout_record_counts.clear()
                rollout_report_indices.clear()
                rollout_rewards.clear()
                rollout_keys.clear()
                rollout_all_report_indices.clear()
                rollout_record_episode_indices.clear()
            if (index + 1) % snapshot_every == 0:
                snapshots.append(copy.deepcopy(model.state_dict()))
                if len(snapshots) > max_snapshots:
                    snapshots.pop(1)  # keep the initial teacher in the pool
    finally:
        if pool is not None:
            pool.shutdown()
    return tuple(reports)
