"""Load only the project's versioned policy weights and vocabulary."""

from collections.abc import Mapping
from pathlib import Path

import torch

from goat_ai.agents.baseline import Agent

from goat_ai.training.policy import CardVocabulary, LegalActionPolicy, PolicyAgent


def load_policy_agent(path: str | Path, *, device: str = "cpu",
                      tactical_guard: bool = False,
                      card_races: Mapping[int, int] | None = None,
                      weak_flip_attacks: Mapping[int, int] | None = None,
                      self_target_guard: bool = False,
                      own_loss_guard: bool = False,
                      own_loss_guard_version: int = 1,
                      card_facts: Mapping[int, tuple[int, int, int]] | None = None,
                      position_guard: bool = False,
                      position_guard_version: int = 2,
                      tactical_fallback_agent: Agent | None = None,
                      tactical_fallback_margin: float | None = None,
                      tactical_fallback_defer_card_choices: bool = False) -> PolicyAgent:
    checkpoint = torch.load(path, map_location=device, weights_only=True)
    if not isinstance(checkpoint, dict) or checkpoint.get("schema_version") != 1:
        raise ValueError("unsupported policy checkpoint schema")
    vocabulary = CardVocabulary(tuple(checkpoint["vocabulary_codes"]),
                                tuple(tuple(item) for item in
                                      checkpoint.get("vocabulary_card_properties", ())))
    if checkpoint.get("feature_version", 1) >= 22 and not vocabulary.card_properties:
        raise ValueError("feature version 22 checkpoint lacks printed card properties")
    model = LegalActionPolicy(vocabulary.size, width=int(checkpoint["width"]),
                              feature_version=int(checkpoint.get("feature_version", 1)))
    model.load_state_dict(checkpoint["model_state"])
    model.to(device).eval()
    return PolicyAgent(model, vocabulary, tactical_guard=tactical_guard,
                       card_races=card_races,
                       weak_flip_attacks=weak_flip_attacks,
                       self_target_guard=self_target_guard,
                       own_loss_guard=own_loss_guard,
                       own_loss_guard_version=own_loss_guard_version,
                       card_facts=card_facts,
                       position_guard=position_guard,
                       position_guard_version=position_guard_version,
                       tactical_fallback_agent=tactical_fallback_agent,
                       tactical_fallback_margin=tactical_fallback_margin,
                       tactical_fallback_defer_card_choices=(
                           tactical_fallback_defer_card_choices))
