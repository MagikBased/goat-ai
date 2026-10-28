"""Browser human games keep the native engine private and save verified demos."""

import json
import os
import random
import shutil
from dataclasses import replace
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

import pytest

from goat_ai.replay import read_trajectory, training_demonstrator_records
from scripts import serve_review_queue
from scripts.create_viewer_game import ROOT, GameCreator
from scripts.live_human_game import LiveGameManager

DECK1 = "goat_control_rhymus_lizo_new_jersey_2005.ydk"
DECK2 = "chaos_bryan_coronel_new_jersey_2005.ydk"


def _manager(tmp_path, native_root=None):
    folder = tmp_path / "examples/decks"
    folder.mkdir(parents=True)
    for name in (DECK1, DECK2):
        shutil.copyfile(ROOT / "examples/decks" / name, folder / name)
    return LiveGameManager(GameCreator(root=tmp_path, native_root=native_root or tmp_path))


def test_live_game_rejects_invalid_requests(tmp_path):
    manager = _manager(tmp_path)
    spec = {"deck1": DECK1, "deck2": DECK2, "human_seat": 0,
            "opponent": "random", "seed": 42}
    with pytest.raises(ValueError, match="published deck list"):
        manager.start({**spec, "deck2": "../../private.ydk"})
    with pytest.raises(ValueError, match="human seat"):
        manager.start({**spec, "human_seat": True})
    with pytest.raises(ValueError, match="AI opponent"):
        manager.start({**spec, "opponent": "shell"})
    with pytest.raises(FileNotFoundError, match="native GOAT assets"):
        manager.start(spec)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_live_game_completes_and_saves_human_only_demonstration(tmp_path):
    manager = _manager(tmp_path, Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve())
    state = manager.start({"deck1": DECK1, "deck2": DECK2, "human_seat": 0,
                           "opponent": "random", "seed": 4322})
    repeated = manager.start({"deck1": DECK1, "deck2": DECK2, "human_seat": 0,
                              "opponent": "random", "seed": 4322})
    assert repeated["observation"] == state["observation"]
    assert repeated["legal_actions"] == state["legal_actions"]
    assert manager.close(repeated["id"]) == {"closed": True}
    assert not state["terminal"]
    assert state["observation"]["viewer"] == 0
    assert state["observation"]["acting_player"] == 0
    assert all(str(card["code"]) in state["card_names"]
               for card in state["observation"]["own_extra_deck"])
    assert all(card["code"] is None for card in state["observation"]["field"]
               if card["controller"] == 1 and card["position"] == "facedown")
    with pytest.raises(ValueError, match="not legal"):
        manager.choose(state["id"], len(state["legal_actions"]))
    human = random.Random(100)
    for _ in range(3000):
        if state["terminal"]:
            break
        state = manager.choose(state["id"], human.randrange(len(state["legal_actions"])))
    assert state["terminal"]
    assert state["viewer"].endswith(".html")
    replay = manager.creator.output_dir / f"{state['id']}.json"
    assert replay.with_suffix(".html").is_file()
    trajectory = read_trajectory(replay)
    assert trajectory.source == "human_web"
    assert trajectory.skill_metadata["authorization"] == "self_recorded"
    assert len(trajectory.decisions) == state["decisions"]
    records = training_demonstrator_records(trajectory)
    assert records and all(record.observation.acting_player == 0 for record in records)
    with pytest.raises(ValueError, match="self_recorded"):
        training_demonstrator_records(replace(
            trajectory, skill_metadata={"demonstrator_seat": 0}))
    assert manager.get(state["id"])["viewer"] == state["viewer"]
    assert manager.close(state["id"]) == {"closed": True}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_live_http_requests_keep_native_engine_on_its_worker_thread(tmp_path, monkeypatch):
    manager = _manager(tmp_path, Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve())
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    monkeypatch.setattr(serve_review_queue, "GameCreator", lambda root: manager.creator)
    server = serve_review_queue.make_server(None, None, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def post(path, payload):
        request = Request(base + path, data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    try:
        state = post("/api/live/start", {"deck1": DECK1, "deck2": DECK2,
                                         "human_seat": 1, "opponent": "random",
                                         "seed": 4326})
        assert state["observation"]["viewer"] == 1
        state = post("/api/live/choice", {"id": state["id"], "action_index": 0})
        assert state["decisions"] >= 2
        assert post("/api/live/close", {"id": state["id"]}) == {"closed": True}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
