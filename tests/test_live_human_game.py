"""Browser human games keep the native engine private and save verified demos."""

import json
import os
import random
import shutil
from dataclasses import replace
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
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
    folder.mkdir(parents=True, exist_ok=True)
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
def test_live_game_auto_passes_only_forced_human_windows(tmp_path):
    manager = _manager(tmp_path, Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve())
    base = {"deck1": DECK1, "deck2": DECK2, "human_seat": 0,
            "opponent": "random"}
    try:
        forced = manager.start({**base, "seed": 4322})
        assert forced["decisions"] == 2
        assert forced["observation"]["phase"] == "main1"
        assert len(forced["legal_actions"]) > 1
        journal = manager.creator.output_dir / "_in_progress" / f"{forced['id']}.json"
        assert len(json.loads(journal.read_text())["entries"]) == forced["decisions"]

        optional = manager.start({**base, "seed": 5})
        assert optional["decisions"] == 0
        assert optional["observation"]["phase"] == "draw"
        assert {action["kind"] for action in optional["legal_actions"]} == {"chain", "pass"}
    finally:
        manager.close_all()


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_unfinished_duel_recovers_from_verified_actions_after_server_restart(tmp_path):
    native = Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve()
    spec = {"deck1": DECK1, "deck2": DECK2, "human_seat": 1,
            "opponent": "random", "seed": 4322}
    manager = _manager(tmp_path, native)
    state = manager.start(spec)
    assert state["observation"]["acting_player"] == 1
    state = manager.choose(state["id"], 0, state["decisions"])
    journal = manager.creator.output_dir / "_in_progress" / f"{state['id']}.json"
    saved = json.loads(journal.read_text())
    assert saved["entries"] and all(set(entry) == {
        "index", "observation_sha256", "legal_sha256", "origin"}
        for entry in saved["entries"])
    assert "observation" not in journal.read_text().replace("observation_sha256", "")
    manager.close_all()

    resumed = _manager(tmp_path, native)
    try:
        assert resumed.get(state["id"]) == state
        next_state = resumed.choose(state["id"], 0, state["decisions"])
        assert next_state["decisions"] > state["decisions"]
        assert resumed.close(state["id"]) == {"closed": True}
        assert not journal.exists()
    finally:
        resumed.close_all()

    corrupt = manager.creator.output_dir / "_in_progress" / f"{state['id']}.json"
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    saved["entries"][0]["legal_sha256"] = "0" * 64
    corrupt.write_text(json.dumps(saved), encoding="utf-8")
    rejected = _manager(tmp_path, native)
    try:
        with pytest.raises(ValueError, match="differs at decision"):
            rejected.get(state["id"])
    finally:
        rejected.close_all()


def test_local_card_art_is_cached_on_demand(tmp_path, monkeypatch):
    creator = GameCreator(root=tmp_path, native_root=tmp_path)
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    monkeypatch.setattr(serve_review_queue, "GameCreator", lambda root: creator)
    database = tmp_path / "database/cards.cdb"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"test")
    monkeypatch.setattr(serve_review_queue, "load_card_names", lambda root: {123: "Test"})
    calls = []

    def cache(code, output_dir, native_root):
        calls.append(code)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{code}.jpg").write_bytes(b"\xff\xd8\xfftest")
        return True

    monkeypatch.setattr(serve_review_queue, "cache_card_image", cache)
    backs = []

    def cache_backs(output_dir):
        backs.append(True)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "cover.png").write_bytes(b"\x89PNG\r\n\x1a\nback")
        return 1, 0

    monkeypatch.setattr(serve_review_queue, "setup_card_backs", cache_backs)
    server = serve_review_queue.make_server(None, None, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(f"{base}/replays/card_images/123.jpg", timeout=5) as response:
            assert response.read() == b"\xff\xd8\xfftest"
        with urlopen(f"{base}/replays/card_images/123.jpg", timeout=5) as response:
            assert response.status == 200
        assert calls == [123]
        with urlopen(f"{base}/replays/card_images/cover.png", timeout=5) as response:
            assert response.read().endswith(b"back")
        assert backs == [True]
        with pytest.raises(HTTPError) as missing:
            urlopen(f"{base}/replays/card_images/999.jpg", timeout=5)
        assert missing.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


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
        manager.choose(state["id"], len(state["legal_actions"]), state["decisions"])
    human = random.Random(100)
    previous = state
    auto_index = state["decisions"]
    state = manager.choose(state["id"], human.randrange(len(state["legal_actions"])),
                           state["decisions"], manual=False)
    with pytest.raises(ValueError, match="stale live decision"):
        manager.choose(state["id"], 0, previous["decisions"])
    assert manager.get(state["id"])["decisions"] == state["decisions"]
    for _ in range(3000):
        if state["terminal"]:
            break
        state = manager.choose(state["id"], human.randrange(len(state["legal_actions"])),
                               state["decisions"])
    assert state["terminal"]
    assert state["viewer"].endswith(".html")
    replay = manager.creator.output_dir / f"{state['id']}.json"
    assert replay.with_suffix(".html").is_file()
    assert not (manager.creator.output_dir / "_in_progress" / f"{state['id']}.json").exists()
    trajectory = read_trajectory(replay)
    assert trajectory.source == "human_web"
    assert trajectory.skill_metadata["authorization"] == "self_recorded"
    assert len(trajectory.decisions) == state["decisions"]
    records = training_demonstrator_records(trajectory)
    assert records and all(record.observation.acting_player == 0 for record in records)
    explicit = trajectory.skill_metadata["explicit_human_decision_indices"]
    assert auto_index not in explicit
    assert len(records) == len(explicit)
    assert all(records[position] is trajectory.decisions[index]
               for position, index in enumerate(explicit))
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
        state = post("/api/live/choice", {"id": state["id"], "action_index": 0,
                                           "expected_decisions": state["decisions"],
                                           "manual": True})
        assert state["decisions"] >= 2
        with pytest.raises(HTTPError) as invalid_origin:
            post("/api/live/choice", {"id": state["id"], "action_index": 0,
                                      "expected_decisions": state["decisions"],
                                      "manual": "yes"})
        assert invalid_origin.value.code == 400
        with pytest.raises(HTTPError) as stale:
            post("/api/live/choice", {"id": state["id"], "action_index": 0,
                                      "expected_decisions": 0})
        assert stale.value.code == 400
        with urlopen(f"{base}/api/live/state?id={state['id']}", timeout=5) as response:
            assert json.load(response)["decisions"] == state["decisions"]
        assert post("/api/live/close", {"id": state["id"]}) == {"closed": True}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_live_game_neural_opponent_reaches_human_decision_without_hidden_cards(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve()
    checkpoint = native_root / "fv23_current_tactical_broader_33000_33031.pt"
    if not checkpoint.is_file():
        pytest.skip("selected neural checkpoint not installed")
    manager = _manager(tmp_path, native_root)
    manager.creator.checkpoint = checkpoint
    state = manager.start({"deck1": DECK1, "deck2": DECK2, "human_seat": 1,
                           "opponent": "policy", "seed": 4327})
    try:
        assert state["terminal"] is False
        assert state["observation"]["viewer"] == 1
        assert state["observation"]["acting_player"] == 1
        assert state["legal_actions"]
        assert all(card["code"] is None for card in state["observation"]["field"]
                   if card["controller"] == 0 and card["position"] == "facedown")
        assert "opponent_hand" not in state["observation"]
    finally:
        manager.close(state["id"])
