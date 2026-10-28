"""Compare scalar and batched visible-state critic fitting on a saved duel."""

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
from goat_ai.training import encode_decision, load_policy_agent
from goat_ai.training.self_play import VisibleStateValue, state_value_update


def scalar_update(model, vocabulary, records, reward, feature_version, optimizer):
    """Previous one-forward-per-decision update, retained for this ablation."""
    optimizer.zero_grad()
    loss_total = 0.0
    for record in records:
        features = encode_decision(record.observation, record.legal_actions,
                                   vocabulary, feature_version)
        loss = (model(features) - reward).square()
        (loss / len(records)).backward()
        loss_total += float(loss.detach())
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    return loss_total / len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--architecture", choices=("v1", "v2"), default="v2")
    args = parser.parse_args()
    if args.limit < 1 or args.batch_size < 1 or args.rounds < 1:
        parser.error("limit, batch size, and rounds must be positive")
    torch.set_num_threads(1)
    agent = load_policy_agent(args.checkpoint)
    trajectory = read_trajectory(args.trajectory)
    seat = (trajectory.skill_metadata or {}).get("learner_seat")
    if trajectory.source != "self_play_rl" or type(seat) is not int or seat not in (0, 1):
        parser.error("expected a self-play trajectory with a learner seat")
    records = tuple(record for record in trajectory.decisions
                    if record.observation.acting_player == seat
                    and len(record.legal_actions) > 1)[:args.limit]
    if not records:
        parser.error("trajectory has no learner decisions with alternatives")
    reward = (0.0 if trajectory.winner is None else
              1.0 if trajectory.winner == seat else -1.0)
    torch.manual_seed(27)
    width = agent.model.state_numbers[0].in_features
    reference = VisibleStateValue(agent.vocabulary.size, width,
                                  architecture=args.architecture,
                                  card_number_width=(6 if agent.model.feature_version >= 29
                                                     else 5))
    results = []
    for index in range(args.rounds):
        modes = ("scalar", "batched") if index % 2 == 0 else ("batched", "scalar")
        outcomes = {}
        for mode in modes:
            model = copy.deepcopy(reference)
            optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
            started = process_time()
            if mode == "scalar":
                loss = scalar_update(model, agent.vocabulary, records, reward,
                                     agent.model.feature_version, optimizer)
            else:
                loss = state_value_update(model, agent.vocabulary, records, reward,
                                          agent.model.feature_version, optimizer,
                                          batch_size=args.batch_size)
            outcomes[mode] = (process_time() - started, loss,
                              tuple(parameter.detach().clone()
                                    for parameter in model.parameters()))
        scalar, batched = outcomes["scalar"], outcomes["batched"]
        results.append({
            "order": modes,
            "scalar_cpu_seconds": scalar[0],
            "batched_cpu_seconds": batched[0],
            "speedup": scalar[0] / batched[0],
            "loss_absolute_difference": abs(scalar[1] - batched[1]),
            "max_parameter_absolute_difference": max(
                (left - right).abs().max().item()
                for left, right in zip(scalar[2], batched[2], strict=True)),
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
        "critic_architecture": args.architecture,
        "decisions": len(records),
        "batch_size": args.batch_size,
        "rounds": results,
    }, indent=2))


if __name__ == "__main__":
    main()
