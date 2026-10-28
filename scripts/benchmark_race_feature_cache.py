"""AB/BA complete sampled duels with and without cached race-mask features."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import torch

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent, policy
from goat_ai.training.self_play import run_learning_episode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--deck-a", type=Path,
                        default=Path("examples/decks/control_probe.ydk"))
    parser.add_argument("--deck-b", type=Path,
                        default=Path("examples/decks/chaos_probe.ydk"))
    parser.add_argument("--seed", type=int, default=17100)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.games < 1 or args.max_decisions < 1:
        parser.error("games and max-decisions must be positive")

    agent = load_policy_agent(args.checkpoint)
    cached = policy._race_mask_bits

    def uncached(race: int) -> tuple[float, ...]:
        return tuple(float(bool(race & (1 << bit))) for bit in range(64))

    def run(use_cache: bool):
        policy._race_mask_bits = cached if use_cache else uncached
        started = perf_counter()
        episodes = [run_learning_episode(
            agent.model, agent.vocabulary, RandomAgent(seed + 1),
            (str(args.deck_a), str(args.deck_b)), seed, seed % 2,
            lambda: ExperimentalOcgcoreEngine(args.native_root),
            torch.Generator().manual_seed(seed), args.max_decisions)
            for seed in range(args.seed, args.seed + args.games)]
        return perf_counter() - started, episodes

    try:
        rounds = []
        for order in ((False, True), (True, False)):
            results = {mode: run(mode) for mode in order}
            reference, candidate = results[False][1], results[True][1]
            matched = all(left.trajectory == right.trajectory
                          and left.learner_records == right.learner_records
                          for left, right in zip(reference, candidate, strict=True))
            if not matched:
                raise AssertionError("race cache changed a sampled duel")
            rounds.append({
                "order": ["cached" if mode else "uncached" for mode in order],
                "uncached_seconds": results[False][0],
                "cached_seconds": results[True][0],
                "decisions": [episode.decisions for episode in reference],
                "matched_trajectories": matched,
            })
    finally:
        policy._race_mask_bits = cached

    report = {
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "deck_sha256": {str(deck): sha256_file(deck)
                        for deck in (args.deck_a, args.deck_b)},
        "seeds": list(range(args.seed, args.seed + args.games)),
        "rounds": rounds,
    }
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
