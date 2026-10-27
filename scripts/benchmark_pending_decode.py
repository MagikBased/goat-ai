"""Compare native pending-prompt reuse with forced redecoding in full duels."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import OcgcoreProbe
from goat_ai.environments import GoatEnvironment
from goat_ai.replay.fingerprint import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--deck-a", type=Path,
                        default=Path("examples/decks/control_probe.ydk"))
    parser.add_argument("--deck-b", type=Path,
                        default=Path("examples/decks/chaos_probe.ydk"))
    parser.add_argument("--seed", type=int, default=15000)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--max-decisions", type=int, default=5000)
    args = parser.parse_args()
    if args.games < 1 or args.max_decisions < 1:
        parser.error("games and max-decisions must be positive")

    cached_decode = OcgcoreProbe.decode_pending

    def fresh_decode(probe):
        probe._decoded_pending = None
        return cached_decode(probe)

    def run(use_cache):
        OcgcoreProbe.decode_pending = cached_decode if use_cache else fresh_decode
        started = perf_counter()
        trajectories = []
        try:
            for seed in range(args.seed, args.seed + args.games):
                agents = (RandomAgent(seed), RandomAgent(seed + 1))
                with GoatEnvironment(str(args.deck_a), str(args.deck_b), seed,
                                     engine=ExperimentalOcgcoreEngine(args.native_root)) as env:
                    observation = env.reset()
                    for _ in range(args.max_decisions):
                        action = agents[observation.acting_player].select_action(
                            observation, env.legal_actions())
                        observation = env.step(action)
                        if env.is_terminal():
                            trajectories.append(env.trajectory())
                            break
                    else:
                        raise RuntimeError(f"duel exceeded decision cap: seed={seed}")
            return perf_counter() - started, trajectories
        finally:
            OcgcoreProbe.decode_pending = cached_decode

    measurements = []
    for order in ((False, True), (True, False)):
        runs = {mode: run(mode) for mode in order}
        fresh, cached = runs[False], runs[True]
        if fresh[1] != cached[1]:
            raise AssertionError("prompt cache changed native trajectories")
        measurements.append({
            "order": ["cached" if mode else "fresh" for mode in order],
            "fresh_seconds": fresh[0],
            "cached_seconds": cached[0],
            "speedup": fresh[0] / cached[0],
            "decisions": [len(game.decisions) for game in cached[1]],
            "winners": [game.winner for game in cached[1]],
            "matched_trajectories": True,
        })
    print(json.dumps({
        "seed": args.seed,
        "games": args.games,
        "deck_sha256": [sha256_file(args.deck_a), sha256_file(args.deck_b)],
        "measurements": measurements,
    }, indent=2))


if __name__ == "__main__":
    main()
