"""The local EDOPro launcher accepts only published decks and keeps recordings review-only."""

from pathlib import Path

import pytest

from goat_ai.actions import Action
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord, Trajectory, read_decision_annotations, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
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


def test_edopro_web_confirmations_only_label_optional_human_choices(tmp_path, monkeypatch):
    native = tmp_path / ".cache/goat-ai"
    directory = native / "edopro_games" / ("a" * 16)
    directory.mkdir(parents=True)
    (directory / "session.json").write_text('{"ai_deck":"ai.ydk"}')
    replay = directory / "game-001-seed-42.yrpX"
    replay.write_bytes(b"recorded")
    metadata = replay.with_suffix(".meta.json")
    metadata.write_text('{"human_authorization":"self_recorded",'
                        '"human_client_seat":1}')
    base = {"turn": 1, "phase": "main1", "life_points": (8000, 8000), "hand": (),
            "field": (), "graveyards": ((), ()), "banished": ((), ()),
            "opponent_hand_count": 5, "deck_counts": (35, 35),
            "extra_deck_counts": (0, 0)}
    ai = Observation(viewer=0, acting_player=0, **base)
    human = Observation(viewer=1, acting_player=1, **base)
    ai_actions = (Action("a", "pass", 0), Action("b", "end_phase", 0))
    human_actions = (Action("h", "normal_summon", 1, {"code": 87621407}),
                     Action("s", "set_monster", 1, {"code": 87621407}))
    forced = Action("f", "place", 1)
    trajectory = Trajectory(
        "goat_pinned_historical", ("AI", "Player"), 42,
        (DecisionRecord(ai, ai_actions, ai_actions[0]),
         DecisionRecord(human, human_actions, human_actions[0]),
         DecisionRecord(human, (forced,), forced)), None,
        source="edopro_pinned_historical",
        skill_metadata={"human_client_seat": 1, "authorization": "self_recorded"})
    review = replay.with_suffix(".review.json")
    write_trajectory(review, trajectory)
    monkeypatch.setattr("scripts.edopro_local_room.verify_edopro_live_recording",
                        lambda *args: {"complete": True})
    monkeypatch.setattr("scripts.confirm_edopro_human_actions.verify_edopro_live_recording",
                        lambda *args: {"complete": True})
    monkeypatch.setattr("scripts.edopro_local_room.verify_edopro_human_annotations",
                        lambda *args: {"confirmed_human_choices": 1})
    monkeypatch.setattr("scripts.confirm_edopro_human_actions.verify_edopro_human_annotations",
                        lambda *args: {"confirmed_human_choices": 1,
                                       "annotation_sha256": "0" * 64})
    monkeypatch.setattr("scripts.edopro_local_room.render_replay",
                        lambda _source, viewer, _root: viewer.write_text("<html></html>"))
    monkeypatch.setattr("scripts.edopro_local_room.load_card_names",
                        lambda _root: {87621407: "Dekoichi"})
    room = EdoRoomManager(GameCreator(root=tmp_path, native_root=native))
    choices = room.choices("a" * 16)
    assert [item["frame"] for item in choices["candidates"]] == [2]
    assert choices["candidates"][0]["card"] == "Dekoichi"
    assert choices["training_admitted"] is False
    with pytest.raises(ValueError, match="optional human-seat"):
        room.save_choices("a" * 16, [1])
    with pytest.raises(ValueError, match="optional human-seat"):
        room.save_choices("a" * 16, [3])
    assert room.save_choices("a" * 16, [2])["confirmed"] == 1
    labels = replay.with_suffix(".human_labels.json")
    annotations, records = read_decision_annotations(
        labels, sha256_file(review), trajectory)
    assert annotations.choices == ((1, 0),)
    assert records[0].selected_action == human_actions[0]
    assert room.choices("a" * 16)["candidates"][0]["confirmed"] is True
    assert room.save_choices("a" * 16, [])["confirmed"] == 0
    assert not labels.exists()
