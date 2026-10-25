"""Compare policies with teacher choices in replay-verified held-out duels.

This off-policy diagnostic measures action agreement, not competitive strength.
"""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import torch

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.replay import demonstrator_records, read_trajectory, verify_trajectory
from goat_ai.training import load_policy_agent

SCOPES = ("all", "multi_option", "multiple_kinds", "known_hand",
          "known_hand_multi_option")


def empty_counts() -> dict:
    return {scope: {"exact": 0, "kind": 0, "total": 0} for scope in SCOPES}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, action="append", required=True)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"),
                        default="restricted")
    parser.add_argument("--output", type=Path)
    parser.add_argument("trajectories", nargs="+", type=Path)
    args = parser.parse_args()
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    checkpoints = []
    for path in args.checkpoint:
        metadata = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
            raise ValueError(f"{path}: unsupported checkpoint schema")
        seeds = {game["seed"] for game in metadata.get("training_games", ())}
        checkpoints.append((path, seeds))

    counts = {str(path): defaultdict(empty_counts)
              for path, _ in checkpoints}
    verified = []
    for path in args.trajectories:
        trajectory = read_trajectory(path)
        if not trajectory.deck_sha256 or not trajectory.asset_sha256:
            raise ValueError(f"{path}: replay fingerprints required")
        for checkpoint, seeds in checkpoints:
            if trajectory.seed in seeds:
                raise ValueError(f"{path}: seed {trajectory.seed} overlaps {checkpoint}")
        count = verify_trajectory(trajectory, engine_type(args.native_root))
        records = demonstrator_records(trajectory)
        seat = (trajectory.skill_metadata or {}).get("demonstrator_seat")
        deck = trajectory.decks[seat] if seat is not None else "both seats"
        verified.append({"path": str(path), "sha256": sha256(path),
                         "seed": trajectory.seed, "deck": deck,
                         "verified_decisions": count,
                         "teacher_decisions": len(records)})
        for checkpoint, _ in checkpoints:
            agent = load_policy_agent(checkpoint)
            bucket = counts[str(checkpoint)][deck]
            for record in records:
                chosen = agent.select_action(record.observation, record.legal_actions)
                scopes = ["all"]
                if len(record.legal_actions) > 1:
                    scopes.append("multi_option")
                if len({action.kind for action in record.legal_actions}) > 1:
                    scopes.append("multiple_kinds")
                if record.observation.known_opponent_hand_cards:
                    scopes.append("known_hand")
                    if len(record.legal_actions) > 1:
                        scopes.append("known_hand_multi_option")
                for scope in scopes:
                    bucket[scope]["total"] += 1
                    bucket[scope]["exact"] += chosen == record.selected_action
                    bucket[scope]["kind"] += chosen.kind == record.selected_action.kind

    policies = []
    for path, _ in checkpoints:
        by_deck = dict(counts[str(path)])
        overall = {scope: {key: sum(bucket[scope][key] for bucket in by_deck.values())
                           for key in ("exact", "kind", "total")}
                   for scope in SCOPES}
        policies.append({"checkpoint": str(path), "sha256": sha256(path),
                         "overall": overall, "by_deck": by_deck})
    result = {"engine": args.engine, "trajectories": verified, "policies": policies,
              "interpretation": "off-policy agreement on verified visible decisions; "
              "not a playing-strength estimate"}
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
