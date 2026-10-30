"""Optional real TCP room regression against an installed external EDOPro host."""

import asyncio
import json
import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.historical_host_scripts import validate_pinned_host_assets
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory
from goat_ai.replay.edopro_live_verify import verify_edopro_live_recording
from scripts.serve_edopro_policy import Bridge


@pytest.mark.skipif(
    not (os.getenv("GOAT_AI_EDOPRO_HOST_ROOT") and os.getenv("GOAT_AI_EDOPRO_MIRROR_ROOT")),
    reason="external EDOPro host and exact matching native root not supplied",
)
def test_network_room_saves_audited_complete_game(tmp_path):
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
                    historical_patches=historical)
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
    )
    server = ArenaServer(room, "127.0.0.1", 0)

    async def play() -> None:
        await server.start()
        try:
            await client.connect("127.0.0.1", server.port)
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
    assert metadata["mirror_complete"] is True
    assert metadata["training_admitted"] is False
    assert metadata["host_responses"] == result.responses
    trajectory = read_trajectory(next(tmp_path.glob("*.review.json")))
    assert audit_trajectory_visibility(trajectory)["decisions"] == len(trajectory.decisions)
    assert trajectory.source == ("edopro_pinned_historical" if historical
                                 else "edopro_external_unpatched")
    assert trajectory.terminal_observation is not None
    assert len(trajectory.decisions) >= result.responses
    replay_path = next(tmp_path.glob("*.yrpX"))
    assert replay_path.stat().st_size > 0
    review_path = next(tmp_path.glob("*.review.json"))
    metadata_path = next(tmp_path.glob("*.meta.json"))
    verified = verify_edopro_live_recording(
        replay_path, review_path, metadata_path, mirror_root)
    assert verified["visible_decisions"] == len(trajectory.decisions)
    assert verified["training_admitted"] is False
    metadata["winner_team"] = 1 - metadata["winner_team"]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from replay"):
        verify_edopro_live_recording(replay_path, review_path,
                                     metadata_path, mirror_root)
