"""Supervised fitting on previously verified visible decision records."""

import random
from collections.abc import Sequence

import torch
from torch import nn

from goat_ai.replay import DecisionRecord
from goat_ai.training.policy import CardVocabulary, LegalActionPolicy, encode_decision


def fit_behavioral_clone(model: LegalActionPolicy, vocabulary: CardVocabulary,
                         records: Sequence[DecisionRecord], *, epochs: int = 1,
                         learning_rate: float = 1e-3, seed: int = 0) -> tuple[float, ...]:
    """Return mean per-decision cross-entropy for each epoch.

    This function trains on its input as supplied. Callers must verify source,
    permission, and replay fidelity before fitting; see the CLI for native
    replay verification. Loss alone is not a playing-strength measurement.
    """
    if not records or epochs < 1 or learning_rate <= 0:
        raise ValueError("training needs records, positive epochs, and positive learning rate")
    device = next(model.parameters()).device
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    losses = []
    examples = [(encode_decision(record.observation, record.legal_actions, vocabulary,
                                 model.feature_version),
                 record.legal_actions.index(record.selected_action)) for record in records]
    for epoch in range(epochs):
        order = list(range(len(examples)))
        random.Random(seed + epoch).shuffle(order)
        model.train()
        total = 0.0
        for index in order:
            features, target = examples[index]
            logits = model(features.to(device)).unsqueeze(0)
            loss = nn.functional.cross_entropy(
                logits, torch.tensor([target], dtype=torch.long, device=device))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += float(loss.detach())
        losses.append(total / len(examples))
    return tuple(losses)
