"""Measure raw action-score margins on replay-verified policy decisions.

This is an off-policy diagnostic, not an estimate of playing strength.
"""

import argparse
import json
from pathlib import Path
from statistics import median

import torch

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import demonstrator_records, read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import encode_decision


def score_margin(agent, observation, actions) -> float:
    features = encode_decision(observation, actions, agent.vocabulary,
                               agent.model.feature_version)
    device = next(agent.model.parameters()).device
    with torch.inference_mode():
        scores = agent.model(features.to(device))
        largest = torch.topk(scores, 2).values
    return float(largest[0] - largest[1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--child", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("trajectories", nargs="+", type=Path)
    args = parser.parse_args()
    checkpoint_hashes = (sha256_file(args.parent), sha256_file(args.child))
    training_seeds = set()
    for checkpoint in (args.parent, args.child):
        metadata = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
            raise ValueError(f"{checkpoint}: unsupported checkpoint schema")
        training_seeds.update(game["seed"] for game in metadata.get("training_games", ()))
    parent = load_policy_agent(args.parent)
    child = load_policy_agent(args.child)
    parent.model.eval()
    child.model.eval()
    margins = {"parent": [], "child": [], "changed_parent": [],
               "unchanged_parent": []}
    replay_provenance = []
    for path in args.trajectories:
        replay = read_trajectory(path)
        if not replay.deck_sha256 or not replay.asset_sha256:
            raise ValueError(f"{path}: replay fingerprints required")
        if replay.seed in training_seeds:
            raise ValueError(f"{path}: seed overlaps a checkpoint's training games")
        count = verify_trajectory(replay, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(replay)
        replay_provenance.append({"path": str(path), "sha256": sha256_file(path),
                                  "seed": replay.seed, "verified_decisions": count,
                                  "recorded_policy_sha256": (
                                      (replay.skill_metadata or {}).get(
                                          "policy_checkpoint_sha256"))})
        for record in demonstrator_records(replay):
            actions = record.legal_actions
            if len(actions) < 2:
                continue
            parent_margin = score_margin(parent, record.observation, actions)
            child_margin = score_margin(child, record.observation, actions)
            changed = (parent.select_action(record.observation, actions)
                       != child.select_action(record.observation, actions))
            margins["parent"].append(parent_margin)
            margins["child"].append(child_margin)
            margins["changed_parent" if changed else "unchanged_parent"].append(
                parent_margin)
    if not margins["parent"]:
        raise ValueError("no multi-option demonstrator decisions")
    result = {
        "parent": {"path": str(args.parent), "sha256": checkpoint_hashes[0]},
        "child": {"path": str(args.child), "sha256": checkpoint_hashes[1]},
        "trajectories": replay_provenance,
        "multi_option_decisions": len(margins["parent"]),
        "changed_choices": len(margins["changed_parent"]),
        "raw_logit_margins": {
            name: {"count": len(values),
                   "median": median(values) if values else None,
                   "max": max(values) if values else None,
                   "at_least_two": sum(value >= 2.0 for value in values)}
            for name, values in margins.items()},
        "interpretation": "Off-policy raw model logit gaps between the two highest "
                          "legal actions. Policy guards can alter final choices. These "
                          "margins are not calibrated probabilities or playing strength.",
    }
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
