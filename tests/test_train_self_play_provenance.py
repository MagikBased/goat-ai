"""Self-play checkpoints retain exact terminal-game replay provenance."""

import pytest
import torch

from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import CardVocabulary, LegalActionPolicy
from scripts.train_self_play import checked_replay_hashes, load_training_agent, replay_directory


def test_replay_directory_defaults_beside_checkpoint_and_rejects_collisions(tmp_path):
    output = tmp_path / "child.pt"
    assert replay_directory(output, None) == tmp_path / "child_replays"
    with pytest.raises(ValueError, match="distinct"):
        replay_directory(output, output)
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "existing.json").write_text("existing")
    with pytest.raises(ValueError, match="empty"):
        replay_directory(output, occupied)


def test_checkpoint_replay_hashes_reject_missing_changed_and_overlapping_games(tmp_path):
    replay = tmp_path / "episode.json"
    replay.write_text("original")
    digest = sha256_file(replay)
    recorded = {11: (str(replay), digest)}
    reports = [{"seed": 11}]
    assert checked_replay_hashes(reports, recorded, {}) == {str(replay): digest}
    with pytest.raises(ValueError, match="differ"):
        checked_replay_hashes([{"seed": 12}], recorded, {})
    with pytest.raises(ValueError, match="overlaps"):
        checked_replay_hashes(reports, recorded, {str(replay): digest})
    with pytest.raises(ValueError, match="overlaps"):
        checked_replay_hashes([{"seed": 11}, {"seed": 12}],
                              {11: (str(replay), digest), 12: (str(replay), digest)}, {})
    replay.write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        checked_replay_hashes(reports, recorded, {})
    replay.unlink()
    with pytest.raises(FileNotFoundError):
        checked_replay_hashes(reports, recorded, {})


def test_self_play_feature_upgrade_preserves_parent_weights_and_provenance(tmp_path):
    vocabulary = CardVocabulary((10,), ((10, 1, 0),))
    parent = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    path = tmp_path / "parent.pt"
    torch.save({
        "schema_version": 1, "model_state": parent.state_dict(),
        "vocabulary_codes": vocabulary.codes,
        "vocabulary_card_properties": vocabulary.card_properties,
        "width": 8, "feature_version": 23,
        "training_games": [{"seed": 1, "deck_sha256": ("a", "b"),
                            "main_deck_composition_sha256": ("c", "d")}],
        "trajectory_sha256": {},
    }, path)
    ordinary = load_training_agent(path)
    upgraded = load_training_agent(path, upgrade_feature_23_to_32=True)
    assert ordinary.model.feature_version == 23
    assert upgraded.model.feature_version == 32
    assert torch.equal(ordinary.model.card.weight, upgraded.model.card.weight)
    original = ordinary.model.action_numbers[0].weight
    expanded = upgraded.model.action_numbers[0].weight
    assert torch.equal(original, expanded[:, :original.shape[1]])
    assert torch.count_nonzero(expanded[:, original.shape[1]:]) == 0
    v32_path = tmp_path / "v32.pt"
    torch.save({"schema_version": 1, "model_state": upgraded.model.state_dict(),
                "vocabulary_codes": vocabulary.codes,
                "vocabulary_card_properties": vocabulary.card_properties,
                "width": 8, "feature_version": 32}, v32_path)
    with pytest.raises(ValueError, match="requires a v23 checkpoint"):
        load_training_agent(v32_path, upgrade_feature_23_to_32=True)
