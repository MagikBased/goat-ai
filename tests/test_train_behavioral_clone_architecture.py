"""Checkpoint continuation should inherit its model architecture by default."""

import pytest
import torch

from goat_ai.training.policy import POLICY_FEATURE_VERSION
from scripts.train_behavioral_clone import training_architecture


def test_new_clone_keeps_documented_architecture_defaults():
    assert training_architecture(None, None, None) == (64, POLICY_FEATURE_VERSION)


def test_continuation_inherits_parent_width_and_feature_version(tmp_path):
    path = tmp_path / "parent.pt"
    torch.save({"schema_version": 1, "width": 32, "feature_version": 23}, path)
    assert training_architecture(path, None, None) == (32, 23)
    assert training_architecture(path, 16, None) == (16, 23)
    assert training_architecture(path, None, 22) == (32, 22)
    assert training_architecture(path, None, None, upgrade_target=34) == (32, 34)


def test_invalid_parent_architecture_is_rejected_before_training(tmp_path):
    path = tmp_path / "parent.pt"
    torch.save({"schema_version": 1, "width": 0, "feature_version": 23}, path)
    with pytest.raises(ValueError, match="unsupported parent policy checkpoint architecture"):
        training_architecture(path, None, None)
