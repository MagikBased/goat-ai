"""Selective replay learning with a frozen parent policy as a stability target."""

import random
from collections.abc import Sequence
from math import isfinite

import torch
from torch import nn

from goat_ai.replay import DecisionRecord

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
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Fit selected labels while matching the parent on separate visible states.

    The caller must replay-verify and visibility-audit both record sets.
    Returns per-step labeled cross-entropy and parent KL diagnostics.
    """
    if (not labeled or not preservation or steps < 1 or preservation_batch < 1
            or preservation_batch > len(preservation) or learning_rate <= 0
            or not isfinite(preservation_weight) or preservation_weight <= 0):
        raise ValueError("parent KL needs records and positive finite settings")
    if parent is model or parent.feature_version != model.feature_version:
        raise ValueError("parent KL needs a separate compatible reference policy")
    device = next(model.parameters()).device
    if next(parent.parameters()).device != device:
        raise ValueError("parent and student must use the same device")
    target_examples = [(encode_decision(record.observation, record.legal_actions,
                                        vocabulary, model.feature_version),
                        record.legal_actions.index(record.selected_action))
                       for record in labeled]
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
        labeled_loss = sum(
            nn.functional.cross_entropy(
                model(features.to(device)).unsqueeze(0),
                torch.tensor([target], dtype=torch.long, device=device))
            for features, target in target_examples) / len(target_examples)
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
