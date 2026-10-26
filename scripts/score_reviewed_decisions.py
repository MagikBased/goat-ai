"""Score replay-verified review labels without claiming competitive strength."""

import argparse
import json
from pathlib import Path

import torch

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_decision_annotations, read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import encode_decision


def score_decision(model, vocabulary, record, label_index: int) -> dict:
    """Compare an annotated legal choice with the recorded choice on one view."""
    legal = record.legal_actions
    if not 0 <= label_index < len(legal):
        raise ValueError("annotation action index is not legal")
    features = encode_decision(record.observation, legal, vocabulary,
                               model.feature_version)
    model.eval()
    with torch.no_grad():
        logits = model(features).cpu()
        if logits.ndim != 1 or len(logits) != len(legal) or not torch.isfinite(logits).all():
            raise ValueError("policy returned invalid legal-action scores")
        probabilities = torch.softmax(logits, dim=0)
    recorded_index = legal.index(record.selected_action)
    best_index = int(torch.argmax(logits).item())
    label_score = float(logits[label_index])
    other_score = max((float(score) for index, score in enumerate(logits)
                       if index != label_index), default=label_score)
    return {
        "legal_actions": len(legal),
        "recorded_index": recorded_index,
        "annotated_index": label_index,
        "model_best_index": best_index,
        "annotated_rank": 1 + sum(float(score) > label_score for score in logits),
        "annotated_probability": float(probabilities[label_index]),
        "annotated_minus_recorded_logit": label_score - float(logits[recorded_index]),
        "annotated_minus_best_other_logit": label_score - other_score,
        "model_matches_annotation": best_index == label_index,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--case", nargs=2, action="append", metavar=("REPLAY", "LABELS"),
                        required=True, help="repeat for each trajectory and annotation file")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    metadata = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
        raise ValueError("unsupported policy checkpoint schema")
    agent = load_policy_agent(args.checkpoint)
    training_hashes = set(metadata.get("trajectory_sha256", {}).values())
    training_seeds = {game["seed"] for game in metadata.get("training_games", ())}
    cases = []
    for replay_path, labels_path in args.case:
        replay_path = Path(replay_path)
        labels_path = Path(labels_path)
        trajectory = read_trajectory(replay_path)
        verified = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        replay_hash = sha256_file(replay_path)
        labels, _ = read_decision_annotations(labels_path, replay_hash, trajectory)
        decisions = []
        for index, action_index in labels.choices:
            record = trajectory.decisions[index]
            decisions.append({
                "decision_index": index,
                "viewer_frame": index + 1,
                "acting_player": record.observation.acting_player,
                "turn": record.observation.turn,
                "phase": record.observation.phase,
                **score_decision(agent.model, agent.vocabulary, record, action_index),
            })
        cases.append({
            "trajectory": str(replay_path),
            "trajectory_sha256": replay_hash,
            "annotation": str(labels_path),
            "annotation_sha256": sha256_file(labels_path),
            "authorization": labels.authorization,
            "reviewer": labels.reviewer,
            "verified_decisions": verified,
            "exact_replay_in_training": replay_hash in training_hashes,
            "seed_in_training": trajectory.seed in training_seeds,
            "decisions": decisions,
        })
    report = {
        "schema_version": 1,
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "cases": cases,
    }
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(json.dumps({"output": str(args.output),
                          "cases": len(cases),
                          "labels": sum(len(case["decisions"]) for case in cases)}))
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
