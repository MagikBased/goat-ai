"""Optional real TCP room regression against an installed external EDOPro host."""

import asyncio
import hashlib
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
import torch

from goat_ai.agents import RandomAgent
from goat_ai.engine.historical_host_scripts import validate_pinned_host_assets
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory
from goat_ai.replay.edopro_live_verify import (
    verify_edopro_human_annotations,
    verify_edopro_live_recording,
)
from goat_ai.replay.fingerprint import sha256_file
from scripts.confirm_edopro_human_actions import confirm_frames
from scripts.create_viewer_game import GameCreator
from scripts.edopro_local_room import EdoRoomManager
from scripts.serve_edopro_policy import Bridge
from scripts.train_behavioral_clone import load_experimental_edopro_confirmations


def test_room_download_uses_only_known_saved_session(tmp_path):
    manager = EdoRoomManager(GameCreator(root=tmp_path, native_root=tmp_path))
    session = manager.folder / ("a" * 16)
    session.mkdir(parents=True)
    (session / "session.json").write_text('{"ai_deck":"fixture.ydk"}')
    replay = session / "game-001-seed-1.yrpX"
    with pytest.raises(ValueError, match="no saved native replay"):
        manager.native_replay("a" * 16)
    replay.write_bytes(b"yrpX-test")
    assert manager.native_replay("a" * 16) == replay
    with pytest.raises(ValueError, match="invalid EDOPro session ID"):
        manager.native_replay("../other")
    with pytest.raises(ValueError, match="session is unavailable"):
        manager.native_replay("b" * 16)


def test_stopped_room_keeps_launch_error_after_server_restart(tmp_path):
    session = tmp_path / "edopro_games" / ("a" * 16)
    session.mkdir(parents=True)
    (session / "session.json").write_text(json.dumps({
        "ai_deck": "fixture.ydk", "pid": 999_999_999}))
    (session / "room.log").write_text("EDOPro host failed to load card script\n")
    manager = EdoRoomManager(GameCreator(root=tmp_path, native_root=tmp_path))
    assert manager.process is None
    status = manager.status()
    assert status["sessions"][0]["running"] is False
    assert status["sessions"][0]["error"] == "EDOPro host failed to load card script"
    (session / "room.log").write_text("")
    assert manager.status()["sessions"][0]["error"] == (
        "The room exited before saving a duel")


@pytest.mark.skipif(
    not (os.getenv("GOAT_AI_EDOPRO_HOST_ROOT") and os.getenv("GOAT_AI_EDOPRO_MIRROR_ROOT")
         and os.getenv("GOAT_AI_EDOPRO_HISTORICAL") == "1"),
    reason="pinned EDOPro host and exact matching native root not supplied",
)
def test_page_room_launcher_completes_and_lists_verified_game():
    """Exercise the real child process and the room manager used by the page."""
    pytest.importorskip("ygo_agent")
    from ygo_agent.arena.client import ArenaClient
    from ygo_agent.arena.deck import load_ydk
    from ygo_agent.arena.policies import RandomPolicy
    from ygo_agent.core import Engine

    project = Path(__file__).resolve().parents[1]
    native = Path(os.environ["GOAT_AI_EDOPRO_MIRROR_ROOT"]).resolve()
    host = Path(os.environ["GOAT_AI_EDOPRO_HOST_ROOT"]).resolve()
    engine = Engine.load(str(host))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory(dir=native, prefix="edopro-launcher-test-") as scratch:
        creator = GameCreator(root=project, native_root=native)
        manager = EdoRoomManager(creator, port=port)
        manager.folder = Path(scratch) / "sessions"
        manager.session = None
        manager.process = None
        try:
            launched = manager.start("warrior_montague_clash.ydk")
            assert launched["room_running"]
            identifier = launched["sessions"][0]["id"]
            for _ in range(150):
                if manager.status()["listening"]:
                    break
                if manager.process.poll() is not None:
                    pytest.fail((manager.folder / identifier / "room.log").read_text())
                time.sleep(0.1)
            else:
                pytest.fail("launched EDOPro room did not start listening")

            deck = load_ydk(str(project / "examples/decks/"
                                "gravekeeper_daryl_gessler_indianapolis_2005.ydk"),
                            engine.cards).deck
            random = RandomPolicy(9303)
            client = ArenaClient("Protocol human", deck=deck,
                                 policy=lambda prompt: random(prompt, None))

            async def play() -> None:
                try:
                    await client.connect("127.0.0.1", port)
                    await client.wait(60)
                finally:
                    await client.close()

            asyncio.run(play())
            assert client.log.errors == []
            for _ in range(100):
                recording = manager.status()["sessions"][0]["recording"]
                if recording and recording.get("verified"):
                    break
                time.sleep(0.1)
            else:
                pytest.fail(f"launched room did not save a verified game: {recording}")
            assert recording["complete"] is True
            assert recording["goat_decks_legal"] is True
            assert recording["experimental_confirmed_eligible"] is True
            assert recording["viewer"].endswith(".html")
            choices = manager.choices(identifier)
            assert choices["candidates"]
            assert choices["training_admitted"] is False
            assert choices["continues_recorded_policy"] is True
            assert "--init-checkpoint" in choices["training_command"]
            assert "--feature-version 23 --width 32" in choices["training_command"]
            assert "confirmed_child.pt" in choices["training_command"]
            confirmed = manager.save_choices(
                identifier, [choices["candidates"][0]["frame"]])
            assert confirmed["confirmed"] == 1
            with ZipFile(BytesIO(manager.confirmed_bundle(identifier))) as bundle:
                manifest = json.loads(bundle.read("bundle_manifest.json"))
                assert manifest["confirmed_human_choices"] == 1
                assert manifest["historical_goat_certified"] is False
            child_run = subprocess.run(
                shlex.split(choices["training_command"])[1:],
                cwd=project, env=os.environ, check=True,
                capture_output=True, text=True)
            assert json.loads(child_run.stdout)["decisions"] == 1
            child = torch.load(manager.folder / identifier / "confirmed_child.pt",
                               map_location="cpu", weights_only=True)
            assert child["parent_checkpoint_sha256"] == hashlib.sha256(
                creator.checkpoint.read_bytes()).hexdigest()
            assert child["new_source_decisions"] == {
                "edopro_human_confirmed_experimental": 1}
            creator.checkpoint = Path(scratch) / "missing-parent.pt"
            fallback = manager.choices(identifier)
            assert fallback["continues_recorded_policy"] is False
            assert "--init-checkpoint" not in fallback["training_command"]
            assert "confirmed_pilot.pt" in fallback["training_command"]
        finally:
            if manager.process is not None and manager.process.poll() is None:
                manager.process.terminate()
                manager.process.wait(timeout=10)


@pytest.mark.skipif(
    not (os.getenv("GOAT_AI_EDOPRO_HOST_ROOT") and os.getenv("GOAT_AI_EDOPRO_MIRROR_ROOT")),
    reason="external EDOPro host and exact matching native root not supplied",
)
@pytest.mark.parametrize("surrender", [False, True])
@pytest.mark.parametrize("authorized", [False, True])
def test_network_room_saves_audited_game_or_prefix(tmp_path, surrender, authorized):
    pytest.importorskip("ygo_agent")
    from ygo_agent.arena.client import ArenaClient
    from ygo_agent.arena.deck import DeckSizes, find_banlist, load_banlists, load_ydk
    from ygo_agent.arena.duel import DuelConfig, DuelObserver
    from ygo_agent.arena.policies import RandomPolicy
    from ygo_agent.arena.seats import Seat
    from ygo_agent.arena.server import ArenaServer, Room, RoomConfig, RoomObserver
    from ygo_agent.core import Engine

    root = Path(os.environ["GOAT_AI_EDOPRO_HOST_ROOT"])
    mirror_root = Path(os.environ["GOAT_AI_EDOPRO_MIRROR_ROOT"])
    historical = os.getenv("GOAT_AI_EDOPRO_HISTORICAL") == "1"
    engine = Engine.load(str(root))
    if historical:
        validate_pinned_host_assets(engine, mirror_root)
    banlist = find_banlist(load_banlists(engine.install.lflist_paths), "2005.4 GOAT")
    room = Room(engine, RoomConfig(
        name="GOAT AI test", duel=DuelConfig(rules="goat"), banlist=banlist,
        deck_sizes=DeckSizes(main=(40, 999), extra=(0, 999)),
        seed=9301, max_matches=1,
        rematch=False, lan_discovery=False, host_client=False,
    ))
    decks = Path(__file__).parents[1] / "examples/decks"
    bridge = Bridge(mirror_root, tmp_path, RandomAgent(9302),
                    "0" * 64, DuelObserver, RoomObserver,
                    historical_patches=historical,
                    human_authorization="self_recorded" if authorized else None)
    room.add_local(1, bridge.seat(Seat), load_ydk(
        str(decks / "warrior_montague_clash.ydk"), engine.cards).deck)
    room.duel_observers.append(bridge.duel_observer())
    room.room_observers.append(bridge.room_observer())
    client_policy = RandomPolicy(9303)
    client = ArenaClient(
        "Protocol human", deck=load_ydk(
            str(decks / "gravekeeper_daryl_gessler_indianapolis_2005.ydk"),
            engine.cards).deck,
        policy=lambda prompt: client_policy(prompt, None),
        respond_delay=0.005 if surrender else 0.0,
    )
    server = ArenaServer(room, "127.0.0.1", 0)

    async def play() -> None:
        await server.start()
        try:
            await client.connect("127.0.0.1", server.port)
            if surrender:
                for _ in range(500):
                    if room.duel is not None and room.duel.responses >= 8:
                        client.surrender()
                        break
                    await asyncio.sleep(0.01)
                else:
                    raise AssertionError("room did not reach a reviewable prefix")
            await client.wait(30)
            await server.serve(timeout=5)
        finally:
            await client.close()
            await server.close()
            bridge.close()

    asyncio.run(play())
    assert client.log.errors == []
    assert client.log.replay is not None
    assert len(room.games) == 1
    result = room.games[0][1]
    assert result.retries == 0 and not result.lua_errors
    metadata = json.loads(next(tmp_path.glob("*.meta.json")).read_text())
    assert metadata["mirror_complete"] is not surrender
    assert metadata["mirror_prefix_valid"] is surrender
    assert metadata["training_admitted"] is False
    assert metadata["human_client_seat"] == 1
    assert metadata["human_authorization"] == (
        "self_recorded" if authorized else None)
    trajectory_deck_hashes = list(metadata["deck_sha256"])
    assert len(trajectory_deck_hashes) == 2
    assert metadata["host_responses"] == result.responses
    trajectory = read_trajectory(next(tmp_path.glob("*.review.json")))
    assert trajectory.skill_metadata["human_client_seat"] == 1
    assert trajectory.skill_metadata["authorization"] == (
        "self_recorded" if authorized else None)
    assert list(trajectory.deck_sha256) == trajectory_deck_hashes
    assert audit_trajectory_visibility(trajectory)["decisions"] == len(trajectory.decisions)
    expected_source = ("edopro_pinned_historical" if historical
                       else "edopro_external_unpatched")
    assert trajectory.source == expected_source + ("_partial" if surrender else "")
    assert trajectory.skill_metadata["recording_status"] == (
        "interrupted" if surrender else "complete")
    assert trajectory.terminal_observation is not None
    assert len(trajectory.decisions) >= result.responses
    replay_path = next(tmp_path.glob("*.yrpX"))
    assert replay_path.stat().st_size > 0
    review_path = next(tmp_path.glob("*.review.json"))
    metadata_path = next(tmp_path.glob("*.meta.json"))
    verified = verify_edopro_live_recording(
        replay_path, review_path, metadata_path, mirror_root)
    assert verified["visible_decisions"] == len(trajectory.decisions)
    assert verified["visibility_audited_decisions"] == len(trajectory.decisions)
    assert verified["reviewable_prefix"] is surrender
    assert verified["deck_identity_verified"] is True
    assert verified["goat_decks_legal"] is True
    assert verified["goat_deck_error"] is None
    assert verified["asset_identity_verified"] is True
    assert verified["training_admitted"] is False
    assert metadata["asset_sha256"] == trajectory.asset_sha256
    assert "build/libocgcore.so" in trajectory.asset_sha256
    if historical and authorized and not surrender:
        legacy = json.loads(review_path.read_text())
        legacy["schema_version"] = 30
        for view in [*(row["observation"] for row in legacy["decisions"]),
                     legacy["terminal_observation"]]:
            for card in view["hand"]:
                card.pop("level", None)
        old_review = tmp_path / "legacy_v30.review.json"
        old_review.write_text(json.dumps(legacy))
        assert verify_edopro_live_recording(
            replay_path, old_review, metadata_path, mirror_root)[
                "visible_decisions"] == len(trajectory.decisions)
        legacy["schema_version"] = 29
        for view in [*(row["observation"] for row in legacy["decisions"]),
                     legacy["terminal_observation"]]:
            for cards in (view["hand"], view["field"], *view["graveyards"],
                          *view["banished"], view["own_extra_deck"]):
                for card in cards:
                    card.pop("level", None)
        old_review = tmp_path / "legacy_v29.review.json"
        old_review.write_text(json.dumps(legacy))
        assert verify_edopro_live_recording(
            replay_path, old_review, metadata_path, mirror_root)[
                "visible_decisions"] == len(trajectory.decisions)
        legacy["schema_version"] = 28
        for view in [*(row["observation"] for row in legacy["decisions"]),
                     legacy["terminal_observation"]]:
            for cards in (view["hand"], view["field"], *view["graveyards"],
                          *view["banished"], view["own_extra_deck"]):
                for card in cards:
                    card.pop("attribute", None)
        old_review = tmp_path / "legacy_v28.review.json"
        old_review.write_text(json.dumps(legacy))
        assert verify_edopro_live_recording(
            replay_path, old_review, metadata_path, mirror_root)[
                "visible_decisions"] == len(trajectory.decisions)
    if authorized and not surrender:
        human_index = next(index for index, record in enumerate(trajectory.decisions)
                           if record.observation.acting_player == 1
                           and len(record.legal_actions) > 1)
        record = trajectory.decisions[human_index]
        played = record.legal_actions.index(record.selected_action)
        label_path = tmp_path / "confirmed_human.json"
        label_path.write_text(json.dumps({
            "schema_version": 1,
            "source_trajectory_sha256": sha256_file(review_path),
            "authorization": "self_recorded", "reviewer": "self",
            "choices": [{"decision_index": human_index, "action_index": played}],
        }))
        confirmed = verify_edopro_human_annotations(
            replay_path, review_path, metadata_path, label_path, mirror_root)
        assert confirmed["confirmed_human_choices"] == 1
        assert confirmed["training_admitted"] is False
        forced_index = next(index for index, candidate in
                            enumerate(trajectory.decisions)
                            if candidate.observation.acting_player == 1
                            and len(candidate.legal_actions) == 1)
        label_path.write_text(json.dumps({
            "schema_version": 1,
            "source_trajectory_sha256": sha256_file(review_path),
            "authorization": "self_recorded", "reviewer": "self",
            "choices": [{"decision_index": forced_index, "action_index": 0}],
        }))
        with pytest.raises(ValueError, match="optional human choice"):
            verify_edopro_human_annotations(
                replay_path, review_path, metadata_path, label_path, mirror_root)
        label_path.unlink()
        reviewed_index = next(index for index, candidate in
                              enumerate(trajectory.decisions)
                              if candidate.observation.acting_player == 1
                              and len(candidate.legal_actions) > 1)
        generated_path = tmp_path / "human_confirmed.json"
        generated = confirm_frames(replay_path, [reviewed_index + 1],
                                   mirror_root, generated_path)
        assert generated["confirmed_human_choices"] == 1
        assert confirm_frames(replay_path, [reviewed_index + 1],
                              mirror_root, generated_path) == generated
        ai_index = next(index for index, candidate in
                        enumerate(trajectory.decisions)
                        if candidate.observation.acting_player == 0)
        with pytest.raises(ValueError, match="AI seat"):
            confirm_frames(replay_path, [ai_index + 1], mirror_root,
                           tmp_path / "invalid_ai.json")
        session_id = "a" * 16
        session_dir = tmp_path / "sessions" / session_id
        session_dir.mkdir(parents=True)
        (session_dir / "session.json").write_text('{"ai_deck":"fixture.ydk"}')
        for source in (replay_path, review_path, metadata_path):
            shutil.copy2(source, session_dir / source.name)
        manager = EdoRoomManager(GameCreator(root=tmp_path, native_root=mirror_root))
        manager.folder = session_dir.parent
        choices = manager.choices(session_id)
        assert reviewed_index + 1 in {item["frame"] for item in choices["candidates"]}
        assert choices["training_admitted"] is False
        saved = manager.save_choices(session_id, [reviewed_index + 1])
        assert saved["confirmed"] == 1
        assert manager.choices(session_id)["confirmed"] == 1
        copied_replay = session_dir / replay_path.name
        assert manager.native_replay(session_id) == copied_replay
        with pytest.raises(ValueError, match="invalid EDOPro session ID"):
            manager.native_replay("../other")
        assert copied_replay.with_suffix(".human_labels.json").is_file()
        if historical:
            with ZipFile(BytesIO(manager.confirmed_bundle(session_id))) as bundle:
                assert set(bundle.namelist()) == {
                    copied_replay.name,
                    copied_replay.with_suffix(".review.json").name,
                    copied_replay.with_suffix(".meta.json").name,
                    copied_replay.with_suffix(".human_labels.json").name,
                    "bundle_manifest.json"}
                manifest = json.loads(bundle.read("bundle_manifest.json"))
                assert manifest["confirmed_human_choices"] == 1
                for name, digest in manifest["sha256"].items():
                    assert digest == hashlib.sha256(bundle.read(name)).hexdigest()
            _, training_records, main_hashes, training_report, hashes = (
                load_experimental_edopro_confirmations(copied_replay, mirror_root))
            assert len(training_records) == 1
            assert training_records[0].observation.acting_player == 1
            assert len(main_hashes) == 2
            assert len(hashes) == 4
            assert training_report["training_admitted"] is False
            output = tmp_path / "experimental_edopro_clone.pt"
            trained = subprocess.run([
                sys.executable, str(Path(__file__).parents[1] /
                                    "scripts/train_behavioral_clone.py"),
                "--experimental-edopro-confirmed", str(copied_replay),
                "--native-root", str(mirror_root), "--output", str(output),
                "--feature-version", "23", "--width", "16", "--epochs", "1",
            ], check=True, capture_output=True, text=True)
            assert json.loads(trained.stdout)["decisions"] == 1
            checkpoint = torch.load(output, map_location="cpu", weights_only=True)
            assert checkpoint["source_decisions"] == {
                "edopro_human_confirmed_experimental": 1}
            assert checkpoint["training_games"][0]["historical_goat_certified"] is False
        else:
            with pytest.raises(ValueError, match="fingerprinted pinned room"):
                load_experimental_edopro_confirmations(copied_replay, mirror_root)
    elif not authorized and not surrender:
        with pytest.raises(ValueError, match="authorized self-recording"):
            confirm_frames(replay_path, [1], mirror_root,
                           tmp_path / "unauthorized.json")
    metadata["human_authorization"] = "unauthorized"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported human recording authorization"):
        verify_edopro_live_recording(replay_path, review_path,
                                     metadata_path, mirror_root)
    metadata["human_authorization"] = "self_recorded" if authorized else None
    original_assets = metadata["asset_sha256"]
    metadata["asset_sha256"] = {**original_assets, "build/libocgcore.so": "0" * 64}
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from replay"):
        verify_edopro_live_recording(replay_path, review_path,
                                     metadata_path, mirror_root)
    metadata["asset_sha256"] = original_assets
    metadata["deck_sha256"][0] = "0" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from replay"):
        verify_edopro_live_recording(replay_path, review_path,
                                     metadata_path, mirror_root)
    metadata["deck_sha256"] = trajectory_deck_hashes
    if surrender:
        metadata["core_seed"][0] ^= 1
    else:
        metadata["winner_team"] = 1 - metadata["winner_team"]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from replay"):
        verify_edopro_live_recording(replay_path, review_path,
                                     metadata_path, mirror_root)


def test_experimental_edopro_loader_rejects_incomplete_or_unpatched(tmp_path, monkeypatch):
    replay = tmp_path / "game.yrpX"
    for path in (replay, replay.with_suffix(".review.json"),
                 replay.with_suffix(".meta.json"),
                 replay.with_suffix(".human_labels.json")):
        path.write_bytes(b"fixture")
    for complete, historical, assets, decks, legal in (
            (False, True, True, True, True),
            (True, False, True, True, True),
            (True, True, False, True, True),
            (True, True, True, False, True),
            (True, True, True, True, False)):
        monkeypatch.setattr(
            "scripts.train_behavioral_clone.verify_edopro_human_annotations",
            lambda *args, complete=complete, historical=historical,
            assets=assets, decks=decks, legal=legal: {
                "complete": complete, "historical_patches": historical,
                "asset_identity_verified": assets,
                "deck_identity_verified": decks,
                "goat_decks_legal": legal})
        with pytest.raises(ValueError, match="fingerprinted pinned room"):
            load_experimental_edopro_confirmations(replay, tmp_path)
