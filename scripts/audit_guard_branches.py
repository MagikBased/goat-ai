"""Compare guard-changed decisions with paired offline native continuations.

Each pair shares one recorded hidden state and one deterministic continuation.
Its terminal result is diagnostic, not an expected action value or training label.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from goat_ai.agents.tactical_guard import (
    safe_optional_own_loss_indices,
    safe_target_indices,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION
from scripts.evaluate_decision_branches import evaluate_branches


def _policy_score(winner: int | None, seat: int) -> float:
    return 0.5 if winner is None else float(winner == seat)


def audit_guard_branches(replays: list[Path], checkpoint: Path, native_root: Path,
                         output_dir: Path, *, max_cases: int = 100,
                         max_decisions: int = 3000) -> dict:
    if not replays or max_cases < 1 or max_decisions < 1:
        raise ValueError("provide replays and positive case and decision bounds")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    checkpoint_hash = sha256_file(checkpoint)
    parent = load_policy_agent(checkpoint)
    guard = load_policy_agent(checkpoint, own_loss_guard=True)
    candidates = []
    paths = set()
    for path in replays:
        path = path.resolve()
        if path in paths:
            raise ValueError("duplicate source replay")
        paths.add(path)
        trajectory = read_trajectory(path)
        metadata = trajectory.skill_metadata or {}
        seat = metadata.get("demonstrator_seat")
        if (trajectory.source != "policy_evaluation" or type(seat) is not int
                or seat not in (0, 1)
                or metadata.get("policy_checkpoint_sha256") != checkpoint_hash
                or metadata.get("policy_feature_version") != parent.model.feature_version
                or metadata.get("policy_inference") != "greedy"
                or metadata.get("policy_inference_version") != POLICY_INFERENCE_VERSION
                or metadata.get("opponent") != "TacticalHeuristicAgent"
                or metadata.get("opponent_version") != 14):
            raise ValueError(f"{path}: expected matching greedy policy versus Tactical-v14")
        verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
        audit_trajectory_visibility(trajectory)
        for index, record in enumerate(trajectory.decisions):
            if record.observation.acting_player != seat:
                continue
            if parent.select_action(record.observation,
                                    record.legal_actions) != record.selected_action:
                raise ValueError(f"{path}: policy choice differs at decision {index}")
            if len(record.legal_actions) < 2:
                continue
            kept = safe_optional_own_loss_indices(
                record.observation, record.legal_actions,
                range(len(record.legal_actions)))
            kept = safe_target_indices(record.observation, record.legal_actions,
                                       kept, protect_removal_targets=True)
            if record.selected_action in [record.legal_actions[choice]
                                          for choice in kept]:
                continue
            alternate = guard.select_action(record.observation, record.legal_actions)
            if alternate != record.selected_action:
                candidates.append((path, index,
                                   record.legal_actions.index(record.selected_action),
                                   record.legal_actions.index(alternate)))
    if len(candidates) > max_cases:
        raise ValueError(f"guard changes {len(candidates)} choices, above case bound")
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    counts = Counter()
    for path, index, recorded_index, alternate_index in candidates:
        folder = output_dir / f"{path.stem}_{sha256_file(path)[:12]}_{index}"
        report = evaluate_branches(path, checkpoint, native_root, index,
                                   (recorded_index, alternate_index), folder,
                                   max_decisions=max_decisions)
        recorded, alternate = report["branches"]
        difference = (_policy_score(alternate["winner"], report["policy_seat"])
                      - _policy_score(recorded["winner"], report["policy_seat"]))
        outcome = ("alternative_better" if difference > 0 else
                   "alternative_worse" if difference < 0 else "same_score")
        counts[outcome] += 1
        cases.append({"source": str(path), "source_sha256": report["source_sha256"],
                      "decision_index": index, "policy_seat": report["policy_seat"],
                      "recorded_action_index": recorded_index,
                      "alternate_action_index": alternate_index,
                      "recorded_winner": recorded["winner"],
                      "alternate_winner": alternate["winner"],
                      "outcome": outcome,
                      "report": str(folder / "report.json"),
                      "report_sha256": sha256_file(folder / "report.json")})
    result = {"schema_version": 1, "checkpoint_sha256": checkpoint_hash,
              "scope": "offline_single_hidden_state_one_continuation_per_action",
              "training_labels": False, "cases": cases,
              "outcomes": dict(sorted(counts.items()))}
    (output_dir / "manifest.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--max-cases", type=int, default=100)
    parser.add_argument("--max-decisions", type=int, default=3000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = audit_guard_branches(args.replays, args.checkpoint, args.native_root,
                                  args.output_dir, max_cases=args.max_cases,
                                  max_decisions=args.max_decisions)
    print(json.dumps({"cases": len(result["cases"]),
                      "outcomes": result["outcomes"],
                      "manifest": str(args.output_dir / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
