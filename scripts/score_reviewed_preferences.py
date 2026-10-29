"""Score replay-verified preferences without treating one action as uniquely best."""

import argparse
import json
from math import log
from pathlib import Path

import torch

from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_decision_preferences, read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import encode_decision


def validate_review_holdout(metadata: dict, replay_hash: str, seed: int,
                            main_deck_hashes: tuple[str, str] | None = None) -> None:
    """Reject review cases used by the scored checkpoint or its training decks."""
    sources = metadata.get("trajectory_sha256")
    games = metadata.get("training_games")
    if not isinstance(sources, dict) or not isinstance(games, list) or not games:
        raise ValueError("checkpoint lacks training provenance for held-out review")
    if replay_hash in sources.values():
        raise ValueError("review replay is in checkpoint training")
    if any(not isinstance(game, dict) or type(game.get("seed")) is not int
           for game in games):
        raise ValueError("checkpoint has invalid training seed provenance")
    if seed in {game["seed"] for game in games}:
        raise ValueError("review seed is in checkpoint training")
    if main_deck_hashes is not None:
        if any(not isinstance(game.get("main_deck_composition_sha256"), (list, tuple))
               or len(game["main_deck_composition_sha256"]) != 2
               or any(not isinstance(digest, str)
                      for digest in game["main_deck_composition_sha256"])
               for game in games):
            raise ValueError("checkpoint lacks Main Deck training provenance")
        used = {digest for game in games
                for digest in game["main_deck_composition_sha256"]}
        if used.intersection(main_deck_hashes):
            raise ValueError("review Main Deck is in checkpoint training")


def score_preference(model, vocabulary, record, preferred: tuple[int, ...],
                     disfavored: tuple[int, ...]) -> dict:
    """Use mean log-sum-exp so a larger acceptable set gets no size bonus."""
    legal = record.legal_actions
    if (not preferred or not disfavored
            or set(preferred) & set(disfavored)
            or any(type(index) is not int or not 0 <= index < len(legal)
                   for index in (*preferred, *disfavored))):
        raise ValueError("preference indices must be disjoint legal nonempty sets")
    features = encode_decision(record.observation, legal, vocabulary,
                               model.feature_version)
    model.eval()
    with torch.no_grad():
        logits = model(features)
        if (logits.ndim != 1 or len(logits) != len(legal)
                or not torch.isfinite(logits).all()):
            raise ValueError("policy returned invalid legal-action scores")
        good = torch.logsumexp(logits[list(preferred)], dim=0) - log(len(preferred))
        bad = torch.logsumexp(logits[list(disfavored)], dim=0) - log(len(disfavored))
    best = int(torch.argmax(logits).item())
    best_good = max(preferred, key=lambda index: float(logits[index]))
    good_score = float(logits[best_good])
    return {
        "legal_actions": len(legal),
        "recorded_index": legal.index(record.selected_action),
        "preferred_indices": list(preferred),
        "disfavored_indices": list(disfavored),
        "model_best_index": best,
        "model_best_is_preferred": best in preferred,
        "model_best_is_disfavored": best in disfavored,
        "best_preferred_index": best_good,
        "best_preferred_rank": 1 + sum(float(score) > good_score for score in logits),
        "preferred_minus_disfavored_log_mean_exp": float(good - bad),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--case", nargs=2, action="append", metavar=("REPLAY", "PREFERENCES"),
                        required=True)
    parser.add_argument("--require-heldout", action="store_true",
                        help="reject training replays and seeds from the scored checkpoint")
    parser.add_argument("--require-unseen-main-decks", action="store_true",
                        help="also reject Main Deck compositions used in checkpoint training")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    metadata = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
        raise ValueError("unsupported policy checkpoint schema")
    agent = load_policy_agent(args.checkpoint)
    training_hashes = set(metadata.get("trajectory_sha256", {}).values())
    training_seeds = {game["seed"] for game in metadata.get("training_games", ())}
    cases = []
    for replay_path, preferences_path in args.case:
        replay_path = Path(replay_path)
        preferences_path = Path(preferences_path)
        trajectory = read_trajectory(replay_path)
        verified = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        replay_hash = sha256_file(replay_path)
        reviewed = read_decision_preferences(preferences_path, replay_hash, trajectory)
        if args.require_heldout or args.require_unseen_main_decks:
            compositions = (tuple(main_deck_composition_sha256(read_ydk(deck))
                                  for deck in trajectory.decks)
                            if args.require_unseen_main_decks else None)
            validate_review_holdout(metadata, replay_hash, trajectory.seed,
                                    compositions)
        decisions = []
        for choice in reviewed.preferences:
            record = trajectory.decisions[choice.decision_index]
            decisions.append({
                "decision_index": choice.decision_index,
                "viewer_frame": choice.decision_index + 1,
                "acting_player": record.observation.acting_player,
                "turn": record.observation.turn,
                "phase": record.observation.phase,
                **score_preference(agent.model, agent.vocabulary, record,
                                   choice.preferred_action_indices,
                                   choice.disfavored_action_indices),
            })
        cases.append({
            "trajectory": str(replay_path),
            "trajectory_sha256": replay_hash,
            "preferences": str(preferences_path),
            "preferences_sha256": sha256_file(preferences_path),
            "authorization": reviewed.authorization,
            "reviewer": reviewed.reviewer,
            "reviewed_seat": reviewed.reviewed_seat,
            "verified_decisions": verified,
            "exact_replay_in_training": replay_hash in training_hashes,
            "seed_in_training": trajectory.seed in training_seeds,
            "decisions": decisions,
        })
    report = {"schema_version": 1, "checkpoint": str(args.checkpoint),
              "heldout_training_replay_and_seed_verified": bool(
                  args.require_heldout or args.require_unseen_main_decks),
              "unseen_main_decks_verified": args.require_unseen_main_decks,
              "checkpoint_sha256": sha256_file(args.checkpoint), "cases": cases}
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(json.dumps({"output": str(args.output), "cases": len(cases),
                          "preferences": sum(len(case["decisions"]) for case in cases)}))
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
