"""Host a private EDOPro room with GOAT AI as one duelist.

Requires the optional external ygo-agent host on PYTHONPATH. The host is AGPL;
this project does not vendor or relicense it. Saved games are experimental
records, not automatically admitted as training examples.
"""

import argparse
import asyncio
import hashlib
import json
from math import isfinite
from pathlib import Path

from goat_ai.agents import (TacticalHeuristicAgent, load_card_facts,
                            load_card_races, load_flip_monster_codes)
from goat_ai.engine.decks import Decklist
from goat_ai.engine.historical_host_scripts import validate_pinned_host_assets
from goat_ai.replay.edopro_live_verify import deck_composition_sha256
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
    parser.add_argument("--historical-pinned", action="store_true",
                        help="require the pinned core, DBs, list and checksum-guarded GOAT scripts")
    parser.add_argument("--human-authorization", choices=("self_recorded",),
                        help="mark the human client's decisions as your authorized self-recording")
    parser.add_argument("--tactical-fallback-margin", type=float, choices=(1.0,),
                        help="experimental: use Tactical when the policy's top-two logits "
                             "differ by less than this value")
    args = parser.parse_args()
    if args.tactical_fallback_margin is not None and (
            not isfinite(args.tactical_fallback_margin)
            or args.tactical_fallback_margin < 0):
        parser.error("--tactical-fallback-margin must be finite and nonnegative")
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
    if args.historical_pinned:
        validate_pinned_host_assets(engine, args.mirror_root)
    banlist = find_banlist(load_banlists(engine.install.lflist_paths), "2005.4 GOAT")
    fallback = (TacticalHeuristicAgent(
        load_flip_monster_codes(args.mirror_root),
        load_card_races(args.mirror_root),
        card_facts=load_card_facts(args.mirror_root))
        if args.tactical_fallback_margin is not None else None)
    policy = load_policy_agent(
        args.checkpoint,
        own_loss_guard=args.tactical_fallback_margin is None,
        tactical_fallback_agent=fallback,
        tactical_fallback_margin=args.tactical_fallback_margin)
    ai_inference = ("policy_own_loss_guard_v1" if fallback is None else
                    f"policy_tactical_fallback_margin_{args.tactical_fallback_margin:g}")
    config = RoomConfig(name="GOAT AI experimental", duel=DuelConfig(rules="goat"),
                        banlist=banlist, seed=args.seed, max_matches=1, rematch=False,
                        deck_sizes=DeckSizes(main=(40, 999), extra=(0, 999)),
                        lan_discovery=False, host_client=False)
    room = Room(engine, config)
    deck = load_ydk(str(args.ai_deck), engine.cards).deck
    bridge = Bridge(args.mirror_root, args.out, policy,
                    hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                    DuelObserver, RoomObserver,
                    historical_patches=args.historical_pinned,
                    human_authorization=args.human_authorization,
                    ai_inference=ai_inference)
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
                 duel_observer_type, room_observer_type, *, historical_patches=False,
                 human_authorization=None,
                 ai_inference="policy_own_loss_guard_v1"):
        if human_authorization not in (None, "self_recorded"):
            raise ValueError("unsupported human recording authorization")
        self.native_root = native_root
        self.out = out
        self.policy = policy
        self.checkpoint_sha256 = checkpoint_sha256
        self.historical_patches = historical_patches
        self.human_authorization = human_authorization
        self.ai_inference = ai_inference
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
                bridge.mirror = LiveDuelMirror(
                    bridge.native_root, historical_patches=bridge.historical_patches)
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
                synchronized = (mirror is not None and mirror.decision is not None
                                and mirror.records and result.retries == 0
                                and not result.lua_errors
                                and mirror.response_count == result.responses)
                complete = bool(synchronized and mirror.decision.terminal)
                prefix = bool(synchronized and not complete)
                source = ("edopro_pinned_historical" if bridge.historical_patches
                          else "edopro_external_unpatched")
                deck_hashes = tuple(deck_composition_sha256(main, extra)
                                    for main, extra in duel._insertion)
                asset_sha256 = mirror.asset_manifest() if complete or prefix else None
                metadata = {
                    "source": source,
                    "training_admitted": False,
                    "historical_patches": bridge.historical_patches,
                    "checkpoint_sha256": bridge.checkpoint_sha256,
                    "ai_inference": bridge.ai_inference,
                    "mirror_complete": complete,
                    "mirror_prefix_valid": prefix,
                    "core_seed": list(duel.core_seed),
                    "seed": duel.seed,
                    "winner_team": None if result.is_draw else result.winner,
                    "turns": result.turns,
                    "host_responses": result.responses,
                    "mirror_responses": mirror.response_count if mirror else None,
                    "retries": result.retries,
                    "lua_errors": result.lua_errors,
                    "names": list(duel.names),
                    "deck_sha256": list(deck_hashes),
                    "asset_sha256": asset_sha256,
                    "human_client_seat": 1,
                    "human_authorization": bridge.human_authorization,
                }
                stem.with_suffix(".meta.json").write_text(
                    json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
                if complete or prefix:
                    trajectory = Trajectory(
                        ruleset=("goat_pinned_historical" if bridge.historical_patches
                                 else "goat_external_unverified"),
                        decks=tuple(duel.names),
                        seed=duel.seed, decisions=tuple(mirror.records),
                        winner=metadata["winner_team"] if complete else None,
                        source=source if complete else source + "_partial",
                        skill_metadata={
                            "recording_status": "complete" if complete else "interrupted",
                            "human_client_seat": 1,
                            "authorization": bridge.human_authorization,
                            "ai_inference": bridge.ai_inference,
                        },
                        schema_version=31,
                        deck_sha256=deck_hashes,
                        asset_sha256=asset_sha256,
                        terminal_observation=mirror.decision.observation,
                    )
                    write_trajectory(stem.with_suffix(".review.json"), trajectory)
                print(f"Saved {stem} (complete: {complete}; "
                      f"reviewable prefix: {prefix}; training admitted: no)", flush=True)

        return Save()

    def close(self):
        if self.mirror is not None:
            self.mirror.close()


if __name__ == "__main__":
    main()
