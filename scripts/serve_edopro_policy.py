"""Host a private EDOPro room with GOAT AI as one duelist.

Requires the optional external ygo-agent host on PYTHONPATH. The host is AGPL;
this project does not vendor or relicense it. Saved games are experimental
records, not automatically admitted as training examples.
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from goat_ai.engine.decks import Decklist
from goat_ai.replay.live_mirror import LiveDuelMirror
from goat_ai.replay.trajectory import Trajectory, write_trajectory
from goat_ai.training import load_policy_agent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-root", type=Path, required=True,
                        help="unpacked EDOPro installation used by the external host")
    parser.add_argument("--mirror-root", type=Path, required=True,
                        help="native root matching the host core and scripts exactly")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--ai-deck", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path(".cache/goat-ai/edopro_games"))
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7911)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()
    try:
        from ygo_agent.arena.deck import DeckSizes, find_banlist, load_banlists, load_ydk
        from ygo_agent.arena.duel import DuelConfig, DuelObserver
        from ygo_agent.arena.seats import Seat
        from ygo_agent.arena.server import ArenaServer, Room, RoomConfig, RoomObserver
        from ygo_agent.core import Engine
    except ImportError as exc:
        parser.error("install the optional external ygo-agent host and put it on PYTHONPATH: " + str(exc))

    if not args.mirror_root.is_dir():
        parser.error("mirror root is missing")
    engine = Engine.load(str(args.host_root))
    banlist = find_banlist(load_banlists(engine.install.lflist_paths), "2005.4 GOAT")
    policy = load_policy_agent(args.checkpoint, own_loss_guard=True)
    config = RoomConfig(name="GOAT AI experimental", duel=DuelConfig(rules="goat"),
                        banlist=banlist, seed=args.seed, max_matches=1, rematch=False,
                        deck_sizes=DeckSizes(extra=(0, 999)),
                        lan_discovery=False, host_client=False)
    room = Room(engine, config)
    deck = load_ydk(str(args.ai_deck), engine.cards).deck
    bridge = Bridge(args.mirror_root, args.out, policy,
                    hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                    DuelObserver, RoomObserver)
    room.add_local(1, bridge.seat(Seat), deck)
    room.duel_observers.append(bridge.duel_observer())
    room.room_observers.append(bridge.room_observer())
    server = ArenaServer(room, args.bind, args.port)

    async def run() -> None:
        await server.start()
        print(f"EDOPro: LAN -> Host address {args.bind}, port {server.port}; "
              f"AI occupies seat 2. Games save to {args.out}", flush=True)
        await server.serve(timeout=args.timeout)

    try:
        asyncio.run(run())
    finally:
        bridge.close()


class Bridge:
    """Per-room mirror and recorder; host owns all unrestricted duel state."""

    def __init__(self, native_root, out, policy, checkpoint_sha256,
                 duel_observer_type, room_observer_type):
        self.native_root = native_root
        self.out = out
        self.policy = policy
        self.checkpoint_sha256 = checkpoint_sha256
        self.duel_observer_type = duel_observer_type
        self.room_observer_type = room_observer_type
        self.mirror = None

    def seat(self, base):
        bridge = self

        class GoatSeat(base):
            name = "GOAT AI"

            def choose(self, prompt, retry):
                if retry:
                    raise RuntimeError("host rejected GOAT AI's response")
                return bridge.mirror.choose(self.view.team, bridge.policy)

        return GoatSeat()

    def duel_observer(self):
        bridge = self

        class Audit(self.duel_observer_type):
            def on_start(self, duel):
                if bridge.mirror is not None:
                    bridge.mirror.close()
                bridge.mirror = LiveDuelMirror(bridge.native_root, historical_patches=False)
                decks = tuple(Decklist(tuple(main), tuple(extra))
                              for main, extra in duel._insertion)
                bridge.mirror.start(duel.core_seed, decks)

            def on_prompt(self, team, prompt, retry):
                if retry:
                    raise RuntimeError("host rejected a duel response")
                bridge.mirror.verify_prompt(team, prompt.type)

            def on_response(self, team, prompt, data):
                bridge.mirror.confirm_response(team, data)

        return Audit()

    def room_observer(self):
        bridge = self

        class Save(self.room_observer_type):
            def on_deck_rejected(self, player, error):
                print(f"Deck rejected for {player.name}: {error}", flush=True)

            def on_game_end(self, room, duel, result):
                bridge.out.mkdir(parents=True, exist_ok=True)
                stem = bridge.out / f"game-{len(room.games):03d}-seed-{duel.seed}"
                if duel.replay is not None:
                    stem.with_suffix(".yrpX").write_bytes(duel.replay.yrpx())
                mirror = bridge.mirror
                complete = (mirror is not None and mirror.decision is not None
                            and mirror.decision.terminal and result.retries == 0
                            and not result.lua_errors and mirror.response_count == result.responses)
                metadata = {
                    "source": "edopro_external_unpatched",
                    "training_admitted": False,
                    "checkpoint_sha256": bridge.checkpoint_sha256,
                    "mirror_complete": complete,
                    "core_seed": list(duel.core_seed),
                    "seed": duel.seed,
                    "winner_team": None if result.is_draw else result.winner,
                    "turns": result.turns,
                    "host_responses": result.responses,
                    "mirror_responses": mirror.response_count if mirror else None,
                    "retries": result.retries,
                    "lua_errors": result.lua_errors,
                    "names": list(duel.names),
                }
                stem.with_suffix(".meta.json").write_text(
                    json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
                if complete:
                    trajectory = Trajectory(
                        ruleset="goat_external_unverified", decks=tuple(duel.names),
                        seed=duel.seed, decisions=tuple(mirror.records),
                        winner=metadata["winner_team"], source="edopro_external_unpatched",
                        schema_version=28,
                        terminal_observation=mirror.decision.observation,
                    )
                    write_trajectory(stem.with_suffix(".review.json"), trajectory)
                print(f"Saved {stem} (mirror complete: {complete}; training admitted: no)", flush=True)

        return Save()

    def close(self):
        if self.mirror is not None:
            self.mirror.close()


if __name__ == "__main__":
    main()
