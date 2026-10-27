"""Selective replay learning with a frozen parent policy as a stability target."""

import random
from collections.abc import Sequence
from math import isfinite, log

import torch
from torch import nn

from goat_ai.replay import DecisionRecord, ReviewedPreference

from .policy import CardVocabulary, LegalActionPolicy, encode_decision


def fit_with_parent_kl(
    model: LegalActionPolicy,
    parent: LegalActionPolicy,
    vocabulary: CardVocabulary,
    labeled: Sequence[DecisionRecord],
    preservation: Sequence[DecisionRecord],
    *,
    steps: int,
    preservation_batch: int,
    preservation_weight: float,
    learning_rate: float,
    rng: random.Random,
    labeled_weights: Sequence[float] | None = None,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Fit selected labels while matching the parent on separate visible states.

    The caller must replay-verify and visibility-audit both record sets.
    Returns per-step labeled cross-entropy and parent KL diagnostics.
    """
    if (not labeled or not preservation or steps < 1 or preservation_batch < 1
            or preservation_batch > len(preservation) or not isfinite(learning_rate)
            or learning_rate <= 0
            or not isfinite(preservation_weight) or preservation_weight <= 0):
        raise ValueError("parent KL needs records and positive finite settings")
    if parent is model or parent.feature_version != model.feature_version:
        raise ValueError("parent KL needs a separate compatible reference policy")
    if labeled_weights is not None and (len(labeled_weights) != len(labeled)
                                        or any(not isfinite(weight) or weight <= 0
                                               for weight in labeled_weights)):
        raise ValueError("labeled weights must be finite, positive, and match labels")
    device = next(model.parameters()).device
    if next(parent.parameters()).device != device:
        raise ValueError("parent and student must use the same device")
    target_examples = [(encode_decision(record.observation, record.legal_actions,
                                        vocabulary, model.feature_version),
                        record.legal_actions.index(record.selected_action))
                       for record in labeled]
    weights = tuple(labeled_weights) if labeled_weights is not None else (1.0,) * len(labeled)
    weight_total = sum(weights)
    preserve_features = [encode_decision(record.observation, record.legal_actions,
                                         vocabulary, model.feature_version)
                         for record in preservation]
    parent.eval()
    with torch.no_grad():
        parent_probabilities = [nn.functional.softmax(parent(features.to(device)), dim=0)
                                for features in preserve_features]
    optimizer = torch.optim.Adam((parameter for parameter in model.parameters()
                                  if parameter.requires_grad), lr=learning_rate)
    labeled_losses = []
    preservation_losses = []
    for _ in range(steps):
        model.train()
        optimizer.zero_grad()
        labeled_loss = sum(weight *
            nn.functional.cross_entropy(
                model(features.to(device)).unsqueeze(0),
                torch.tensor([target], dtype=torch.long, device=device))
            for (features, target), weight in zip(target_examples, weights)) / weight_total
        picks = rng.sample(range(len(preserve_features)), preservation_batch)
        preservation_loss = sum(
            nn.functional.kl_div(
                nn.functional.log_softmax(model(preserve_features[index].to(device)), dim=0),
                parent_probabilities[index], reduction="sum")
            for index in picks) / len(picks)
        (labeled_loss + preservation_weight * preservation_loss).backward()
        optimizer.step()
        labeled_losses.append(float(labeled_loss.detach()))
        preservation_losses.append(float(preservation_loss.detach()))
    return tuple(labeled_losses), tuple(preservation_losses)


def fit_preferences_with_parent_kl(
    model: LegalActionPolicy,
    parent: LegalActionPolicy,
    vocabulary: CardVocabulary,
    reviewed: Sequence[tuple[DecisionRecord, ReviewedPreference]],
    preservation: Sequence[DecisionRecord],
    *,
    steps: int,
    preservation_batch: int,
    preservation_weight: float,
    learning_rate: float,
    rng: random.Random,
    recorded_bad_weight: float = 1.0,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Raise preferred legal actions above disfavored ones with parent KL.

    The caller must replay-verify and visibility-audit every source trajectory.
    Each preference is a retrospective comparison, not a demonstrated action.
    """
    if (not reviewed or not preservation or steps < 1 or preservation_batch < 1
            or preservation_batch > len(preservation) or not isfinite(learning_rate)
            or learning_rate <= 0
            or not isfinite(preservation_weight) or preservation_weight <= 0):
        raise ValueError("preference KL needs records and positive finite settings")
    if not isfinite(recorded_bad_weight) or recorded_bad_weight <= 0:
        raise ValueError("recorded bad-choice weight must be finite and positive")
    if parent is model or parent.feature_version != model.feature_version:
        raise ValueError("preference KL needs a separate compatible reference policy")
    device = next(model.parameters()).device
    if next(parent.parameters()).device != device:
        raise ValueError("parent and student must use the same device")
    examples = []
    for record, preference in reviewed:
        legal = record.legal_actions
        good = preference.preferred_action_indices
        bad = preference.disfavored_action_indices
        if (not good or not bad or set(good) & set(bad)
                or any(type(index) is not int or not 0 <= index < len(legal)
                       for index in (*good, *bad))
                or legal.index(record.selected_action) not in (*good, *bad)):
            raise ValueError("preference must compare disjoint legal sets including recorded")
        weight = recorded_bad_weight if legal.index(record.selected_action) in bad else 1.0
        examples.append((encode_decision(record.observation, legal, vocabulary,
                                         model.feature_version), good, bad, weight))
    total_preference_weight = sum(item[3] for item in examples)
    preserve_features = [encode_decision(record.observation, record.legal_actions,
                                         vocabulary, model.feature_version)
                         for record in preservation]
    parent.eval()
    with torch.no_grad():
        parent_probabilities = [nn.functional.softmax(parent(features.to(device)), dim=0)
                                for features in preserve_features]
    optimizer = torch.optim.Adam((parameter for parameter in model.parameters()
                                  if parameter.requires_grad), lr=learning_rate)
    preference_losses = []
    preservation_losses = []

    def preference_term(features, good, bad):
        logits = model(features.to(device))
        good_score = torch.logsumexp(logits[list(good)], dim=0) - log(len(good))
        bad_score = torch.logsumexp(logits[list(bad)], dim=0) - log(len(bad))
        return nn.functional.softplus(bad_score - good_score)

    for _ in range(steps):
        model.train()
        optimizer.zero_grad()
        preference_loss = sum(weight * preference_term(features, good, bad)
                              for features, good, bad, weight in examples
                              ) / total_preference_weight
        picks = rng.sample(range(len(preserve_features)), preservation_batch)
        preservation_loss = sum(
            nn.functional.kl_div(
                nn.functional.log_softmax(model(preserve_features[index].to(device)), dim=0),
                parent_probabilities[index], reduction="sum")
            for index in picks) / len(picks)
        (preference_loss + preservation_weight * preservation_loss).backward()
        optimizer.step()
        preference_losses.append(float(preference_loss.detach()))
        preservation_losses.append(float(preservation_loss.detach()))
    return tuple(preference_losses), tuple(preservation_losses)
