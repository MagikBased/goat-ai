"""Compare matched native self-play with no-grad and inference-mode sampling."""

import argparse
import json
import platform
import subprocess
from pathlib import Path
from time import perf_counter

import torch

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import self_play
from goat_ai.training.checkpoint import load_policy_agent
from goat_ai.training.policy import encode_decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--deck-a", type=Path,
                        default=Path("examples/decks/control_probe.ydk"))
    parser.add_argument("--deck-b", type=Path,
                        default=Path("examples/decks/chaos_probe.ydk"))
    parser.add_argument("--seed", type=int, default=12000)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--max-decisions", type=int, default=5000)
    args = parser.parse_args()
    if min(args.games, args.rounds, args.max_decisions) < 1:
        parser.error("games, rounds, and max-decisions must be positive")

    agent = load_policy_agent(args.checkpoint)
    inference_sampler = self_play.sample_legal_action

    def no_grad_sampler(model, vocabulary, observation, legal_actions, generator,
                        temperature=1.0):
        if temperature <= 0:
            raise ValueError("temperature must be positive")
        if len(legal_actions) == 1:
            return legal_actions[0]
        features = encode_decision(observation, legal_actions, vocabulary,
                                   model.feature_version)
        device = next(model.parameters()).device
        with torch.no_grad():
            logits = model(features.to(device)) / temperature
            probabilities = torch.softmax(logits, dim=0).cpu()
            index = int(torch.multinomial(probabilities, 1,
                                          generator=generator).item())
        return legal_actions[index]

    def run_schedule(sampler):
        self_play.sample_legal_action = sampler
        started = perf_counter()
        episodes = []
        for seed in range(args.seed, args.seed + args.games):
            episodes.append(self_play.run_learning_episode(
                agent.model, agent.vocabulary, RandomAgent(seed + 1),
                (str(args.deck_a), str(args.deck_b)), seed, seed % 2,
                lambda: ExperimentalOcgcoreEngine(args.native_root),
                torch.Generator().manual_seed(seed), args.max_decisions))
        return perf_counter() - started, episodes

    rounds = []
    try:
        for index in range(args.rounds):
            modes = (("no_grad", "inference_mode") if index % 2 == 0
                     else ("inference_mode", "no_grad"))
            elapsed = {}
            episodes = {}
            for mode in modes:
                elapsed[mode], episodes[mode] = run_schedule(
                    no_grad_sampler if mode == "no_grad" else inference_sampler)
            if any(a.trajectory != b.trajectory for a, b in zip(
                    episodes["no_grad"], episodes["inference_mode"])):
                raise AssertionError("samplers produced different native trajectories")
            rounds.append({
                "order": modes,
                "no_grad_seconds": elapsed["no_grad"],
                "inference_mode_seconds": elapsed["inference_mode"],
                "speedup": elapsed["no_grad"] / elapsed["inference_mode"],
                "decisions": [item.decisions for item in episodes["inference_mode"]],
                "winners": [item.winner for item in episodes["inference_mode"]],
                "matched_trajectories": True,
            })
    finally:
        self_play.sample_legal_action = inference_sampler

    print(json.dumps({
        "project_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip(),
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "deck_sha256": [sha256_file(args.deck_a), sha256_file(args.deck_b)],
        "native_root": str(args.native_root),
        "platform": platform.platform(),
        "cpu": next((line.split(":", 1)[1].strip()
                     for line in Path("/proc/cpuinfo").read_text().splitlines()
                     if line.startswith("model name")), platform.processor()),
        "torch_version": str(torch.__version__),
        "torch_threads": torch.get_num_threads(),
        "seed": args.seed,
        "games": args.games,
        "rounds": rounds,
    }, indent=2))


if __name__ == "__main__":
    main()
