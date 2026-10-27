"""Frozen, player-visible resource baseline for policy-gradient experiments."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import torch

from goat_ai.replay.fingerprint import sha256_file
from goat_ai.replay.trajectory import DecisionRecord
from goat_ai.training.policy import CardVocabulary, DecisionFeatures, encode_decision


def visible_resource_features(features: DecisionFeatures) -> torch.Tensor:
    """Six public/acting-player-visible differences, independent of card IDs."""
    numbers = features.state_numbers
    cards = features.state_cards
    own_monsters = ((cards[:, 1] == 2) & (cards[:, 2] == 1)).sum() / 5
    other_monsters = ((cards[:, 1] == 2) & (cards[:, 2] == 2)).sum() / 5
    own_backrow = ((cards[:, 1] == 3) & (cards[:, 2] == 1)).sum() / 5
    other_backrow = ((cards[:, 1] == 3) & (cards[:, 2] == 2)).sum() / 5
    return torch.stack((numbers[0] - numbers[1],
                        numbers[6] - numbers[7],
                        own_monsters - other_monsters,
                        own_backrow - other_backrow,
                        numbers[2] - numbers[3],
                        numbers[8])).double()


@dataclass(frozen=True)
class FrozenResourceRidge:
    """Fixed six-feature regression; no gradient or private engine state."""

    mean: tuple[float, ...]
    scale: tuple[float, ...]
    coefficients: tuple[float, ...]

    def __post_init__(self) -> None:
        if (len(self.mean) != 6 or len(self.scale) != 6
                or len(self.coefficients) != 7
                or any(not isfinite(value) for value in
                       (*self.mean, *self.scale, *self.coefficients))
                or any(value <= 0 for value in self.scale)):
            raise ValueError("resource ridge needs six finite features and positive scales")

    def predict_features(self, features: DecisionFeatures) -> float:
        resources = visible_resource_features(features)
        score = sum((float(value) - mean) / scale * coefficient
                    for value, mean, scale, coefficient in zip(
                        resources, self.mean, self.scale,
                        self.coefficients[:-1], strict=True))
        return max(-1.0, min(1.0, score + self.coefficients[-1]))

    def predict_records(self, records: Sequence[DecisionRecord],
                        vocabulary: CardVocabulary,
                        feature_version: int) -> tuple[float, ...]:
        return tuple(self.predict_features(encode_decision(
            record.observation, record.legal_actions, vocabulary,
            feature_version)) for record in records)


def load_frozen_resource_ridge(path: Path, parent_sha256: str,
                               feature_version: int) -> tuple[FrozenResourceRidge, dict]:
    """Check the fitted artifact and its exact source bytes before PPO use."""
    artifact = json.loads(path.read_text(encoding="utf-8"))
    if (artifact.get("schema_version") != 1
            or artifact.get("model_type") != "frozen_visible_resource_ridge_v1"
            or artifact.get("policy_checkpoint_sha256") != parent_sha256
            or artifact.get("feature_version") != feature_version
            or artifact.get("training_games") != len(
                artifact.get("training_replay_sha256", {}))):
        raise ValueError("resource ridge artifact does not match parent policy")
    report_path = Path(artifact["comparison_report_path"])
    if sha256_file(report_path) != artifact["comparison_report_sha256"]:
        raise ValueError("resource ridge comparison report changed")
    for replay, digest in artifact["training_replay_sha256"].items():
        if sha256_file(Path(replay)) != digest:
            raise ValueError(f"resource ridge source replay changed: {replay}")
    model = FrozenResourceRidge(tuple(artifact["mean"]), tuple(artifact["scale"]),
                                tuple(artifact["coefficients"]))
    return model, artifact
