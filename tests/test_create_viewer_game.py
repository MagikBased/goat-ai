"""Local game creation uses real native duels and verified replay artifacts."""

import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from goat_ai.replay import read_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.create_viewer_game import ROOT, GameCreator
from scripts.validate_review_queue_labels import queue_sources, verify_queue_items

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
    with pytest.raises(ValueError, match="invalid local game ID"):
        creator.audit("../../secret")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("agent1,source", [
    ("tactical", "local_ai_match"), ("policy", "policy_evaluation"),
])
def test_game_creator_generates_verified_reviewer_replay(tmp_path, agent1, source):
    creator = _creator(tmp_path, Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve())
    spec = {"deck1": DECK1, "deck2": DECK2,
            "agent1": agent1, "agent2": "random", "seed": 4321}
    result = creator.create(spec)
    assert result["winner"] in (0, 1, None)
    assert result["decisions"] > 0
    assert result["review_flags"] >= 0
    assert result["viewer"].endswith(".html")
    replay = creator.output_dir / f"{result['id']}.json"
    viewer = creator.output_dir / f"{result['id']}.html"
    reviewer = creator.output_dir / f"{result['id']}.review.json"
    assert replay.is_file() and viewer.is_file() and reviewer.is_file()
    trajectory = read_trajectory(replay)
    assert len(trajectory.decisions) == result["decisions"]
    assert trajectory.source == source
    assert trajectory.skill_metadata["agents"] == [
        "Neural policy v23" if agent1 == "policy" else "Tactical heuristic", "Random"]
    if agent1 == "policy":
        assert trajectory.skill_metadata["demonstrator_seat"] == 0
        assert trajectory.skill_metadata["policy_inference"] == "greedy"
        assert trajectory.skill_metadata["policy_feature_version"] == 23
    assert "__EMBEDDED_REPLAY__" not in viewer.read_text(encoding="utf-8")
    reveals = json.loads(reviewer.read_text(encoding="utf-8"))
    assert len(reveals["frames"]) == result["decisions"] + 1
    audit = creator.audit(result["id"])
    assert audit["purpose"] == "heuristic_review_candidates_not_training_labels"
    assert len(audit["flags"]) == result["review_flags"]
    assert all(flag["viewer_frame"] == flag["decision_index"] + 1
               for flag in audit["flags"])
    assert creator.recent()[0] == result


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_policy_game_review_queue_separates_visible_labels_from_reveals(tmp_path, monkeypatch):
    creator = _creator(tmp_path, Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve())
    result = creator.create({"deck1": DECK1, "deck2": DECK2,
                             "agent1": "policy", "agent2": "tactical", "seed": 6804})
    assert result["policy_review_flags"] >= 1
    queue = creator.review_queue(result["id"])
    digest = sha256_file(queue)
    assert creator.review_queue(result["id"]) == queue
    assert sha256_file(queue) == digest
    report = json.loads(queue.read_text(encoding="utf-8"))
    assert len(report["selected"]) == result["policy_review_flags"]
    assert report["purpose"] == "human_review_candidates_not_training_labels"
    visible = queue.parent / "visible.html"
    reveal = queue.parent / "visible.review.html"
    assert visible.is_file() and reveal.is_file()
    assert queue.with_suffix(".html").is_file()
    source = creator.output_dir / f"{result['id']}.json"
    sources = queue_sources(report, queue)
    assert list(sources) == [sha256_file(source)]
    verify_queue_items(read_trajectory(source), sources[sha256_file(source)][1],
                       report["checkpoint_sha256"])
    with monkeypatch.context() as patch:
        patch.setattr("scripts.create_viewer_game.load_policy_agent", lambda _: SimpleNamespace(
            model=SimpleNamespace(feature_version=23),
            select_action=lambda _observation, _actions: object()))
        with pytest.raises(ValueError, match="recorded policy choice differs"):
            creator.review_queue(result["id"])
