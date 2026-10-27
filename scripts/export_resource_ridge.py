"""Export a verified frozen mirror value fit for an opt-in PPO ablation."""

import argparse
import json
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from scripts.compare_value_architectures import (
    fit_resource_ridge_model,
    selected_records,
)


def export_resource_ridge(report_path: Path, replay_dir: Path, checkpoint: Path,
                          native_root: Path, output: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    parent_hash = sha256_file(checkpoint)
    if (report.get("policy_checkpoint_sha256") != parent_hash
            or report.get("corpus_source") != "policy_evaluation"
            or report.get("primary_mirror_policy") is not True
            or report.get("train_games", 0) < 1
            or report.get("holdout_games", 0) < 1
            or report.get("independent_games", 0) < 1):
        raise ValueError("comparison report is not a held-out frozen mirror fit")
    agent = load_policy_agent(checkpoint)
    paths = sorted(replay_dir.glob("matchup_*.json"),
                   key=lambda path: (int(path.stem.split("_")[3]),
                                     int(path.stem.split("_")[1]),
                                     int(path.stem.split("_")[5])))
    if len(paths) != report["train_games"] + report["holdout_games"]:
        raise ValueError("replay directory differs from comparison corpus")
    games = []
    train_hashes = {}
    for path in paths[:report["train_games"]]:
        digest = sha256_file(path)
        if report["replay_sha256"].get(str(path)) != digest:
            raise ValueError(f"training replay differs from comparison: {path}")
        trajectory = read_trajectory(path)
        if ((trajectory.skill_metadata or {}).get("policy_checkpoint_sha256")
                != parent_hash or
                (trajectory.skill_metadata or {}).get("opponent_checkpoint_sha256")
                != parent_hash):
            raise ValueError(f"replay is not frozen mirror self-play: {path}")
        verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
        audit_trajectory_visibility(trajectory)
        if sha256_file(path) != digest:
            raise ValueError(f"training replay changed during verification: {path}")
        games.append(selected_records(trajectory,
                                      report["max_records_per_game"],
                                      "policy_evaluation"))
        train_hashes[str(path)] = digest
    model = fit_resource_ridge_model(games, agent.vocabulary,
                                     agent.model.feature_version)
    expected = report["scores"]["resource_ridge"]["standardized_coefficients_and_intercept"]
    if any(abs(a - b) > 1e-9 for a, b in zip(model.coefficients, expected,
                                              strict=True)):
        raise ValueError("refitted resource coefficients differ from comparison")
    artifact = {
        "schema_version": 1,
        "model_type": "frozen_visible_resource_ridge_v1",
        "policy_checkpoint_sha256": parent_hash,
        "comparison_report_path": str(report_path),
        "comparison_report_sha256": sha256_file(report_path),
        "feature_version": agent.model.feature_version,
        "mean": model.mean,
        "scale": model.scale,
        "coefficients": model.coefficients,
        "training_replay_sha256": train_hashes,
        "training_games": len(games),
        "max_records_per_game": report["max_records_per_game"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison_report", type=Path)
    parser.add_argument("replay_dir", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    artifact = export_resource_ridge(
        args.comparison_report, args.replay_dir, args.checkpoint,
        args.native_root, args.output)
    print(json.dumps({"output": str(args.output),
                      "training_games": artifact["training_games"],
                      "parent_sha256": artifact["policy_checkpoint_sha256"]}))


if __name__ == "__main__":
    main()
