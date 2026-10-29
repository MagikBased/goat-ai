"""Offline paired duel continuations from one verified player-visible decision.

This is a diagnostic, not an online search agent. The native engine reconstructs
the source position from its seed and exact action prefix. Continuation agents
receive only their own observations and legal actions. An optional different
checkpoint evaluates a changed policy without claiming to reproduce the
recorded suffix.
"""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from goat_ai.agents import (
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION


def recorded_policy_options(inference: str, native_root: Path) -> dict:
    """Continue with the same visible policy mode that produced the replay."""
    if inference == "greedy":
        return {}
    versions = {"greedy_own_loss_guard_v1": 1,
                "greedy_own_loss_guard_v2": 2,
                "greedy_own_loss_guard_v3": 3,
                "greedy_own_loss_guard_v4": 4,
                "greedy_own_loss_guard_v5": 5,
                "greedy_own_loss_guard_v6": 6}
    if inference not in versions:
        raise ValueError(f"unsupported source policy inference {inference!r}")
    version = versions[inference]
    return {"own_loss_guard": True, "own_loss_guard_version": version,
            "card_facts": load_card_facts(native_root) if version in (2, 5, 6) else None}


def evaluate_branches(source_path: Path, checkpoint: Path, native_root: Path,
                      decision_index: int, action_indices: tuple[int, ...],
                      output_dir: Path, max_decisions: int = 3000,
                      continuation_checkpoint: Path | None = None,
                      continuation_use_source_inference: bool = False) -> dict:
    """Replay a common prefix, then continue each offered action to terminal."""
    source = read_trajectory(source_path)
    metadata = source.skill_metadata or {}
    seat = metadata.get("demonstrator_seat")
    if (source.source != "policy_evaluation" or seat not in (0, 1)
            or metadata.get("policy_checkpoint_sha256") != sha256_file(checkpoint)
            or metadata.get("policy_inference_version") != POLICY_INFERENCE_VERSION
            or metadata.get("opponent") != "TacticalHeuristicAgent"
            or metadata.get("opponent_version") != 14):
        raise ValueError("source must be a matching policy-versus-Tactical replay")
    inference = metadata.get("policy_inference")
    policy_options = recorded_policy_options(inference, native_root)
    if (not 0 <= decision_index < len(source.decisions)
            or source.decisions[decision_index].observation.acting_player != seat):
        raise ValueError("decision must belong to the recorded policy")
    offered = source.decisions[decision_index].legal_actions
    if (not action_indices or len(set(action_indices)) != len(action_indices)
            or any(type(index) is not int or not 0 <= index < len(offered)
                   for index in action_indices)
            or offered.index(source.decisions[decision_index].selected_action)
            not in action_indices):
        raise ValueError("include the recorded action and distinct offered alternatives")
    if max_decisions < 1:
        raise ValueError("max_decisions must be positive")
    if continuation_use_source_inference and continuation_checkpoint is None:
        raise ValueError("source inference option requires a continuation checkpoint")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    verified_source = verify_trajectory(source, ExperimentalOcgcoreEngine(native_root))
    audit_trajectory_visibility(source)
    continuation_path = continuation_checkpoint or checkpoint
    continuation_options = (policy_options if continuation_checkpoint is None
                            or continuation_use_source_inference else {})
    policy = load_policy_agent(continuation_path, **continuation_options)
    if policy.model.feature_version != metadata.get("policy_feature_version"):
        raise ValueError("source and checkpoint policy feature versions differ")
    tactical = TacticalHeuristicAgent(
        load_flip_monster_codes(native_root), load_card_races(native_root),
        card_facts=load_card_facts(native_root))
    agents = (policy, tactical) if seat == 0 else (tactical, policy)
    output_dir.mkdir(parents=True, exist_ok=True)
    branches = []
    for action_index in action_indices:
        with GoatEnvironment(*source.decks, source.seed,
                             ExperimentalOcgcoreEngine(native_root)) as env:
            observation = env.reset()
            for prefix_index in range(decision_index):
                record = source.decisions[prefix_index]
                if observation != record.observation or env.legal_actions() != record.legal_actions:
                    raise ValueError(f"source prefix differs at decision {prefix_index}")
                observation = env.step(record.selected_action)
            record = source.decisions[decision_index]
            if observation != record.observation or env.legal_actions() != offered:
                raise ValueError("branch decision differs from source")
            observation = env.step(offered[action_index])
            for _ in range(max_decisions):
                if env.is_terminal():
                    break
                action = agents[observation.acting_player].select_action(
                    observation, env.legal_actions())
                observation = env.step(action)
            if not env.is_terminal():
                raise RuntimeError(f"branch {action_index} exceeded decision cap")
            trajectory = replace(
                env.trajectory(), source="offline_branch_evaluation",
                skill_metadata={
                    "source_trajectory_sha256": sha256_file(source_path),
                    "source_decision_index": decision_index,
                    "branch_action_index": action_index,
                    "policy_seat": seat,
                    "source_policy_checkpoint_sha256": sha256_file(checkpoint),
                    "policy_checkpoint_sha256": sha256_file(continuation_path),
                    "continuation": (inference if continuation_options else "greedy")
                    + "_policy_vs_tactical_v14",
                    "offline_diagnostic_only": True,
                })
            if (continuation_checkpoint is None
                    and offered[action_index] == record.selected_action
                    and (trajectory.decisions != source.decisions
                         or trajectory.winner != source.winner)):
                raise ValueError("recorded-action continuation does not reproduce source")
            path = output_dir / f"action_{action_index}.json"
            write_trajectory(path, trajectory)
            saved = read_trajectory(path)
            verified = verify_trajectory(saved, ExperimentalOcgcoreEngine(native_root))
            audit_trajectory_visibility(saved)
            branches.append({"action_index": action_index,
                             "recorded_action": offered[action_index] == record.selected_action,
                             "action_kind": offered[action_index].kind,
                             "action_code": offered[action_index].parameters.get("code"),
                             "winner": saved.winner,
                             "decisions": verified,
                             "trajectory": str(path),
                             "trajectory_sha256": sha256_file(path)})
    report = {"source": str(source_path), "source_sha256": sha256_file(source_path),
              "verified_source_decisions": verified_source,
              "checkpoint_sha256": sha256_file(checkpoint),
              "source_checkpoint_sha256": sha256_file(checkpoint),
              "continuation_checkpoint_sha256": sha256_file(continuation_path),
              "decision_index": decision_index, "policy_seat": seat,
              "policy_inference": inference,
              "continuation_inference": (inference if continuation_options else "greedy"),
              "scope": "offline_single_seed_full_state_branch_not_online_search",
              "branches": branches}
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--decision-index", type=int, required=True)
    parser.add_argument("--action-index", type=int, action="append", required=True)
    parser.add_argument("--max-decisions", type=int, default=3000)
    parser.add_argument("--continuation-checkpoint", type=Path,
                        help="use a different greedy policy after the verified branch point")
    parser.add_argument("--continuation-use-source-inference", action="store_true",
                        help="apply the recorded policy's inference guard to the new checkpoint")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate_branches(args.source, args.checkpoint, args.native_root,
                               args.decision_index, tuple(args.action_index),
                               args.output_dir, args.max_decisions,
                               args.continuation_checkpoint,
                               args.continuation_use_source_inference)
    print(json.dumps({"decision_index": report["decision_index"],
                      "policy_seat": report["policy_seat"],
                      "branches": report["branches"]}, indent=2))


if __name__ == "__main__":
    main()
