"""Outcome filtering must follow the learner seat, never the winner alone."""

from types import SimpleNamespace

import pytest

from scripts import select_selfplay_replays as selector


def test_selects_only_learner_wins_across_both_seats(monkeypatch, tmp_path):
    paths = [tmp_path / f"episode_{index:05}.json" for index in range(4)]
    replays = {
        paths[0]: SimpleNamespace(source="self_play_rl", seed=10, winner=0,
                                  skill_metadata={"learner_seat": 0, "demonstrator_seat": 0,
                                                  "self_play_episode_index": 0}),
        paths[1]: SimpleNamespace(source="self_play_rl", seed=11, winner=0,
                                  skill_metadata={"learner_seat": 1, "demonstrator_seat": 1,
                                                  "self_play_episode_index": 1}),
        paths[2]: SimpleNamespace(source="self_play_rl", seed=12, winner=1,
                                  skill_metadata={"learner_seat": 1, "demonstrator_seat": 1,
                                                  "self_play_episode_index": 2}),
        paths[3]: SimpleNamespace(source="self_play_rl", seed=13, winner=None,
                                  skill_metadata={"learner_seat": 0, "demonstrator_seat": 0,
                                                  "self_play_episode_index": 3}),
    }
    monkeypatch.setattr(selector, "read_trajectory", lambda path, **kwargs: replays[path])
    assert selector.select(paths, "win", expected_games=4) == [paths[0], paths[2]]
    assert selector.select(paths, "loss", expected_games=4) == [paths[1]]
    assert selector.select(paths, "draw", expected_games=4) == [paths[3]]


def test_rejects_missing_episode_and_ambiguous_seat(monkeypatch, tmp_path):
    path = tmp_path / "episode_00001.json"
    replay = SimpleNamespace(source="self_play_rl", seed=11, winner=0,
                             skill_metadata={"learner_seat": 0, "demonstrator_seat": 0,
                                             "self_play_episode_index": 1})
    monkeypatch.setattr(selector, "read_trajectory", lambda path, **kwargs: replay)
    with pytest.raises(ValueError, match="complete contiguous"):
        selector.select([path], "win", expected_games=1)
    replay.skill_metadata["self_play_episode_index"] = 0
    replay.skill_metadata["learner_seat"] = True
    with pytest.raises(ValueError, match="provenance"):
        selector.select([path], "win", expected_games=1)
