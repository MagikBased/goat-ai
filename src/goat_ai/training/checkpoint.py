"""Load only the project's versioned policy weights and vocabulary."""

from pathlib import Path

import torch

from goat_ai.training.policy import CardVocabulary, LegalActionPolicy, PolicyAgent


def load_policy_agent(path: str | Path, *, device: str = "cpu") -> PolicyAgent:
    checkpoint = torch.load(path, map_location=device, weights_only=True)
    if not isinstance(checkpoint, dict) or checkpoint.get("schema_version") != 1:
        raise ValueError("unsupported policy checkpoint schema")
    vocabulary = CardVocabulary(tuple(checkpoint["vocabulary_codes"]))
    model = LegalActionPolicy(vocabulary.size, width=int(checkpoint["width"]))
    model.load_state_dict(checkpoint["model_state"])
    model.to(device).eval()
    return PolicyAgent(model, vocabulary)
