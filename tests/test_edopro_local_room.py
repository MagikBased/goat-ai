"""The local EDOPro launcher accepts only published decks and keeps recordings review-only."""

from pathlib import Path

import pytest

from scripts.create_viewer_game import GameCreator
from scripts.edopro_local_room import EdoRoomManager


def test_edopro_room_launch_and_verified_viewer(tmp_path, monkeypatch):
    deck_folder = tmp_path / "examples/decks"
    deck_folder.mkdir(parents=True)
    (deck_folder / "ai.ydk").write_text("#main\n")
    native = tmp_path / ".cache/goat-ai"
    for relative in ("edopro_probe/ygo_agent_host/ygo_agent/arena/server.py",
                     "edopro_pinned_host/libocgcore.so",
                     "edopro_pinned_host/lflists/GOAT.lflist.conf",
                     "fv23_current_tactical_broader_33000_33031.pt"):
        path = native / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    (native / "edopro_pinned_host/script").mkdir()
    creator = GameCreator(root=tmp_path, native_root=native)
    room = EdoRoomManager(creator, port=0)

    class Child:
        def poll(self):
            return None

    calls = []

    def spawn(argv, **kwargs):
        calls.append((argv, kwargs))
        return Child()

    monkeypatch.setattr("scripts.edopro_local_room.subprocess.Popen", spawn)
    with pytest.raises(ValueError, match="published AI deck"):
        room.start("../../outside.ydk")
    started = room.start("ai.ydk")
    assert started["room_running"] is True
    assert started["training_admitted"] is False
    assert len(started["sessions"]) == 1
    assert started["sessions"][0]["ai_deck"] == "ai.ydk"
    argv, kwargs = calls[0]
    assert "--historical-pinned" in argv
    assert argv[argv.index("--human-authorization") + 1] == "self_recorded"
    assert argv[argv.index("--ai-deck") + 1] == str(deck_folder / "ai.ydk")
    assert str(native / "edopro_probe/ygo_agent_host") in kwargs["env"]["PYTHONPATH"]
    with pytest.raises(ValueError, match="already running"):
        room.start("ai.ydk")

    directory = native / "edopro_games" / started["sessions"][0]["id"]
    replay = directory / "game-001-seed-42.yrpX"
    replay.write_bytes(b"recorded")
    replay.with_suffix(".meta.json").write_text("{}")
    replay.with_suffix(".review.json").write_text("{}")
    monkeypatch.setattr("scripts.edopro_local_room.verify_edopro_live_recording",
                        lambda *args: {"complete": True})

    def render(_review: Path, viewer: Path, _native: Path):
        viewer.write_text("<html>Verified</html>")

    monkeypatch.setattr("scripts.edopro_local_room.render_replay", render)
    record = room.status()["sessions"][0]["recording"]
    assert record["verified"] is True
    assert record["complete"] is True
    assert record["training_admitted"] is False
    assert record["viewer"].endswith("/game-001-seed-42.html")
    assert (directory / "game-001-seed-42.html").is_file()


def test_edopro_room_reports_missing_optional_host(tmp_path):
    creator = GameCreator(root=tmp_path)
    room = EdoRoomManager(creator)
    assert room.status()["available"] is False
    with pytest.raises(ValueError, match="host package is missing"):
        room.start("ai.ydk")
