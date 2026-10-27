"""Self-play checkpoints retain exact terminal-game replay provenance."""

import pytest

from goat_ai.replay.fingerprint import sha256_file
from scripts.train_self_play import checked_replay_hashes, replay_directory


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
