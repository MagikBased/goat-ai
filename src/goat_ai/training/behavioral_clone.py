"""Supervised fitting on previously verified visible decision records."""

import random
from collections.abc import Sequence
from math import isfinite

import torch
from torch import nn

from goat_ai.replay import DecisionRecord
from goat_ai.training.policy import CardVocabulary, LegalActionPolicy, encode_decision


def fit_behavioral_clone(model: LegalActionPolicy, vocabulary: CardVocabulary,
                         records: Sequence[DecisionRecord], *, epochs: int = 1,
                         learning_rate: float = 1e-3, seed: int = 0,
                         batch_size: int = 1,
                         batched_forward: bool = False,
                         sampling_weights: Sequence[float] | None = None) -> tuple[float, ...]:
    """Return mean per-decision cross-entropy for each epoch.

    This function trains on its input as supplied. Callers must verify source,
    permission, and replay fidelity before fitting; see the CLI for native
    replay verification. Loss alone is not a playing-strength measurement.
    """
    if not records or epochs < 1 or learning_rate <= 0 or batch_size < 1:
        raise ValueError("training needs records, positive epochs, learning rate, and batch size")
    if sampling_weights is not None and (len(sampling_weights) != len(records)
                                         or any(not isfinite(weight) or weight <= 0
                                                for weight in sampling_weights)):
        raise ValueError("sampling weights must be finite, positive, and match records")
    if batched_forward and (model.feature_version < 10
                            or model.feature_version in (14, 15)):
        raise ValueError("batched forward requires a supported v10+ feature version")
    device = next(model.parameters()).device
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    losses = []
    examples = [(encode_decision(record.observation, record.legal_actions, vocabulary,
                                 model.feature_version),
                 record.legal_actions.index(record.selected_action)) for record in records]
    for epoch in range(epochs):
        rng = random.Random(seed + epoch)
        if sampling_weights is None:
            order = list(range(len(examples)))
            rng.shuffle(order)
        else:
            # Keep the number of optimizer decisions fixed while exposing the
            # policy more often to the requested, rare decision contexts.
            order = rng.choices(range(len(examples)), weights=sampling_weights,
                                k=len(examples))
        model.train()
        total = 0.0
        for start in range(0, len(order), batch_size):
            batch = order[start:start + batch_size]
            optimizer.zero_grad()
            if batched_forward:
                logits, _ = model.forward_batch([examples[index][0].to(device)
                                                 for index in batch])
                targets = torch.tensor([examples[index][1] for index in batch],
                                       dtype=torch.long, device=device)
                batch_losses = nn.functional.cross_entropy(
                    logits, targets, reduction="none")
                total += float(batch_losses.detach().sum())
                batch_losses.mean().backward()
            else:
                batch_losses = []
                for index in batch:
                    features, target = examples[index]
                    logits = model(features.to(device)).unsqueeze(0)
                    loss = nn.functional.cross_entropy(
                        logits, torch.tensor([target], dtype=torch.long, device=device))
                    batch_losses.append(loss)
                    total += float(loss.detach())
                torch.stack(batch_losses).mean().backward()
            optimizer.step()
        losses.append(total / len(examples))
    return tuple(losses)
