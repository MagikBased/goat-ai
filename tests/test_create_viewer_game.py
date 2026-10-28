"""Local game creation uses real native duels and verified replay artifacts."""

import json
import os
import shutil
from pathlib import Path

import pytest

from goat_ai.replay import read_trajectory
from scripts.create_viewer_game import ROOT, GameCreator

DECK1 = "goat_control_rhymus_lizo_new_jersey_2005.ydk"
DECK2 = "chaos_bryan_coronel_new_jersey_2005.ydk"


def _creator(tmp_path, native_root=None):
    folder = tmp_path / "examples/decks"
    folder.mkdir(parents=True)
    for name in (DECK1, DECK2):
        shutil.copyfile(ROOT / "examples/decks" / name, folder / name)
    return GameCreator(root=tmp_path, native_root=native_root or tmp_path)


def test_game_creator_rejects_unlisted_paths_and_invalid_agents(tmp_path):
    creator = _creator(tmp_path)
    spec = {"deck1": DECK1, "deck2": DECK2,
            "agent1": "tactical", "agent2": "random", "seed": 42}
    assert creator.options()["decks"] == [DECK2, DECK1]
    assert not creator.options()["native_ready"]
    with pytest.raises(ValueError, match="published deck list"):
        creator.create({**spec, "deck1": "../../secret.ydk"})
    with pytest.raises(ValueError, match="available AI"):
        creator.create({**spec, "agent2": "shell"})
    with pytest.raises(ValueError, match="unsigned 32-bit"):
        creator.create({**spec, "seed": True})
    with pytest.raises(FileNotFoundError, match="native GOAT assets"):
        creator.create(spec)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_game_creator_generates_verified_reviewer_replay(tmp_path):
    creator = _creator(tmp_path, Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve())
    spec = {"deck1": DECK1, "deck2": DECK2,
            "agent1": "tactical", "agent2": "random", "seed": 4321}
    result = creator.create(spec)
    assert result["winner"] in (0, 1, None)
    assert result["decisions"] > 0
    assert result["viewer"].endswith(".html")
    replay = creator.output_dir / f"{result['id']}.json"
    viewer = creator.output_dir / f"{result['id']}.html"
    reviewer = creator.output_dir / f"{result['id']}.review.json"
    assert replay.is_file() and viewer.is_file() and reviewer.is_file()
    trajectory = read_trajectory(replay)
    assert len(trajectory.decisions) == result["decisions"]
    assert trajectory.source == "local_ai_match"
    assert trajectory.skill_metadata["agents"] == ["Tactical heuristic", "Random"]
    assert "__EMBEDDED_REPLAY__" not in viewer.read_text(encoding="utf-8")
    reveals = json.loads(reviewer.read_text(encoding="utf-8"))
    assert len(reveals["frames"]) == result["decisions"] + 1
    assert creator.recent()[0] == result
