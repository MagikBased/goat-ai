"""The PPO resource baseline uses only visible features and pinned sources."""

import json
from types import SimpleNamespace

import pytest
import torch

from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training.resource_value import (
    FrozenResourceRidge,
    load_frozen_resource_ridge,
)


def test_resource_prediction_ignores_hidden_identity() -> None:
    value = FrozenResourceRidge((0,) * 6, (1,) * 6,
                                (0, 0, 1, 0, 0, 0, 0))
    numbers = torch.zeros(10)
    cards = torch.tensor([[20, 2, 1, 1], [0, 2, 2, 2]])
    visible = SimpleNamespace(state_numbers=numbers, state_cards=cards)
    concealed = SimpleNamespace(state_numbers=numbers,
                                state_cards=cards.clone())
    concealed.state_cards[1, 0] = 99999
    assert value.predict_features(visible) == value.predict_features(concealed)
    assert value.predict_features(visible) == 0.0


def test_resource_artifact_checks_parent_report_and_replay_bytes(tmp_path) -> None:
    report = tmp_path / "comparison.json"
    replay = tmp_path / "training.json"
    report.write_text("report")
    replay.write_text("replay")
    artifact = {"schema_version": 1,
                "model_type": "frozen_visible_resource_ridge_v1",
                "policy_checkpoint_sha256": "a" * 64,
                "comparison_report_path": str(report),
                "comparison_report_sha256": sha256_file(report),
                "feature_version": 23, "training_games": 1,
                "training_replay_sha256": {str(replay): sha256_file(replay)},
                "mean": [0] * 6, "scale": [1] * 6,
                "coefficients": [0] * 7}
    path = tmp_path / "ridge.json"
    path.write_text(json.dumps(artifact))
    value, loaded = load_frozen_resource_ridge(path, "a" * 64, 23)
    assert loaded == artifact
    assert value.predict_features(SimpleNamespace(
        state_numbers=torch.zeros(10),
        state_cards=torch.tensor([[0, 0, 0, 0]]))) == 0.0
    with pytest.raises(ValueError, match="parent policy"):
        load_frozen_resource_ridge(path, "b" * 64, 23)
    replay.write_text("changed")
    with pytest.raises(ValueError, match="source replay changed"):
        load_frozen_resource_ridge(path, "a" * 64, 23)
    replay.write_text("replay")
    report.write_text("changed")
    with pytest.raises(ValueError, match="comparison report changed"):
        load_frozen_resource_ridge(path, "a" * 64, 23)
