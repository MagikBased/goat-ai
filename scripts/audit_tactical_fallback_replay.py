"""Verify a fallback-policy replay and list its choices that differ from the parent.

Parent choices are evaluated on the fallback's visited visible states. They
are diagnostics, not counterfactual game outcomes.
"""

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import torch

from goat_ai.agents import (TacticalHeuristicAgent, load_card_facts,
                            load_card_races, load_flip_monster_codes)
from goat_ai.agents.card_metadata import load_card_names
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import encode_decision


def _describe(action, names):
    detail = asdict(action)
    code = action.parameters.get("code")
    if type(code) is int:
        detail["card_name"] = names.get(code, f"Card #{code}")
    cards = action.parameters.get("cards")
    if isinstance(cards, list):
        detail["card_names"] = [names.get(card["code"], f"Card #{card['code']}")
                                for card in cards if type(card.get("code")) is int]
    return detail


def audit_replay(trajectory_path: Path, checkpoint: Path, native_root: Path,
                 margin: float) -> dict:
    if not 0 <= margin < float("inf"):
        raise ValueError("margin must be finite and nonnegative")
    trajectory = read_trajectory(trajectory_path)
    metadata = trajectory.skill_metadata or {}
    checkpoint_sha = sha256_file(checkpoint)
    expected_mode = f"greedy_tactical_fallback_margin_{margin:g}"
    if (trajectory.source != "policy_evaluation"
            or metadata.get("policy_checkpoint_sha256") != checkpoint_sha
            or metadata.get("policy_inference") != expected_mode
            or metadata.get("demonstrator_seat") not in (0, 1)):
        raise ValueError("replay is not bound to this fallback policy and margin")
    verified = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
    audit_trajectory_visibility(trajectory)
    parent = load_policy_agent(checkpoint)
    fallback = load_policy_agent(
        checkpoint,
        tactical_fallback_agent=TacticalHeuristicAgent(
            load_flip_monster_codes(native_root), load_card_races(native_root),
            card_facts=load_card_facts(native_root)),
        tactical_fallback_margin=margin)
    names = load_card_names(native_root)
    changed = []
    policy_decisions = 0
    seat = metadata["demonstrator_seat"]
    for index, record in enumerate(trajectory.decisions):
        if record.observation.acting_player != seat:
            continue
        policy_decisions += 1
        parent_action = parent.select_action(record.observation, record.legal_actions)
        fallback_action = fallback.select_action(record.observation, record.legal_actions)
        if fallback_action != record.selected_action:
            raise ValueError(f"fallback choice differs from replay at decision {index}")
        if parent_action == fallback_action:
            continue
        features = encode_decision(record.observation, record.legal_actions,
                                   parent.vocabulary, parent.model.feature_version)
        with torch.inference_mode():
            scores = parent.model(features)
            top = torch.topk(scores, 2).values
        changed.append({
            "decision_index": index,
            "turn": record.observation.turn,
            "phase": record.observation.phase,
            "raw_logit_margin": float(top[0] - top[1]),
            "parent_action": _describe(parent_action, names),
            "fallback_action": _describe(fallback_action, names),
        })
    return {
        "trajectory": str(trajectory_path),
        "trajectory_sha256": sha256_file(trajectory_path),
        "checkpoint_sha256": checkpoint_sha,
        "margin": margin,
        "verified_decisions": verified,
        "policy_decisions": policy_decisions,
        "changed_choices": len(changed),
        "changed_kinds": dict(Counter(item["fallback_action"]["kind"] for item in changed)),
        "decisions": changed,
        "interpretation": "Parent choices are on the fallback's visited visible states; "
                          "they are not alternate-game outcomes.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--margin", type=float, default=1.0)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_replay(args.trajectory, args.checkpoint, args.native_root,
                          args.margin)
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
