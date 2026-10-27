"""Compare scalar and batched REINFORCE updates on recorded visible choices."""

import argparse
import copy
import json
import platform
import subprocess
from pathlib import Path
from time import process_time

import torch

from goat_ai.replay import read_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training.checkpoint import load_policy_agent
from goat_ai.training.self_play import policy_gradient_update


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--seat", type=int, choices=(0, 1), default=0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    if args.batch_size < 2 or args.rounds < 1:
        parser.error("batch-size must exceed one and rounds must be positive")

    agent = load_policy_agent(args.checkpoint)
    trajectory = read_trajectory(args.trajectory)
    records = tuple(record for record in trajectory.decisions
                    if record.observation.acting_player == args.seat
                    and len(record.legal_actions) > 1)
    if not records:
        parser.error("trajectory has no multi-option decisions for this seat")

    rounds = []
    for index in range(args.rounds):
        modes = ("scalar", "batched") if index % 2 == 0 else (
            "batched", "scalar")
        results = {}
        for mode in modes:
            model = copy.deepcopy(agent.model)
            optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
            started = process_time()
            loss = policy_gradient_update(
                model, agent.vocabulary, records, 1.0, 0.0, optimizer,
                entropy_coefficient=0.001, reduction="mean",
                batch_size=1 if mode == "scalar" else args.batch_size)
            results[mode] = (process_time() - started, loss,
                             tuple(parameter.detach().clone()
                                   for parameter in model.parameters()))
        scalar, batched = results["scalar"], results["batched"]
        rounds.append({
            "order": modes,
            "scalar_cpu_seconds": scalar[0],
            "batched_cpu_seconds": batched[0],
            "speedup": scalar[0] / batched[0],
            "loss_absolute_difference": abs(scalar[1] - batched[1]),
            "max_parameter_absolute_difference": max(
                (left - right).abs().max().item()
                for left, right in zip(scalar[2], batched[2])),
        })
    print(json.dumps({
        "project_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip(),
        "platform": platform.platform(),
        "torch_version": str(torch.__version__),
        "torch_threads": torch.get_num_threads(),
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "trajectory_sha256": sha256_file(args.trajectory),
        "feature_version": agent.model.feature_version,
        "seat": args.seat,
        "decisions": len(records),
        "batch_size": args.batch_size,
        "rounds": rounds,
    }, indent=2))


if __name__ == "__main__":
    main()
