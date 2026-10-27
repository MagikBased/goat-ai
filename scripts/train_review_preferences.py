"""Experimentally fit replay-reviewed action preferences with parent KL."""

import argparse
import copy
import json
import random
from math import isfinite
from pathlib import Path

import torch

from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import (
    demonstrator_records,
    read_decision_preferences,
    read_trajectory,
    verify_trajectory,
)
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import fit_preferences_with_parent_kl, load_policy_agent


def validate_preservation_reference(path: Path, digest: str, seed: int, *,
                                    parent_replay: bool, old_hashes: dict[str, str],
                                    new_hashes: dict[str, str], old_seeds: set[int],
                                    reviewed_seeds: set[int]) -> None:
    """Keep both preservation modes distinct in checkpoint provenance."""
    if parent_replay:
        if old_hashes.get(str(path)) != digest:
            raise ValueError(f"preservation replay is absent from parent provenance: {path}")
    elif (str(path) in old_hashes or digest in old_hashes.values()
          or digest in new_hashes.values()):
        raise ValueError(f"current preservation replay duplicates training data: {path}")
    if not parent_replay and seed in old_seeds | reviewed_seeds:
        raise ValueError(f"current preservation seed overlaps training: {seed}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--case", nargs=2, action="append", metavar=("REPLAY", "PREFERENCES"),
                        required=True)
    parser.add_argument("--preserve-trajectory", type=Path, action="append", default=[],
                        help="exact replay from parent training provenance")
    parser.add_argument("--preserve-current-trajectory", type=Path, action="append", default=[],
                        help="fresh replay under current native assets for parent-policy KL")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--preserve-per-trajectory", type=int, default=16)
    parser.add_argument("--preserve-batch", type=int, default=16)
    parser.add_argument("--parent-kl-weight", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.preserve_trajectory and not args.preserve_current_trajectory:
        parser.error("at least one preservation trajectory is required")
    if (args.steps < 1 or args.preserve_per_trajectory < 1
            or args.preserve_batch < 1 or not isfinite(args.parent_kl_weight)
            or args.parent_kl_weight <= 0 or not isfinite(args.learning_rate)
            or args.learning_rate <= 0 or args.output.resolve() == args.checkpoint.resolve()):
        parser.error("invalid optimization settings or output overlaps parent")
    metadata = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if (not isinstance(metadata, dict) or metadata.get("schema_version") != 1
            or not isinstance(metadata.get("training_games"), list)
            or not isinstance(metadata.get("trajectory_sha256"), dict)):
        parser.error("parent checkpoint lacks replay training provenance")
    agent = load_policy_agent(args.checkpoint)
    model = agent.model
    parent = copy.deepcopy(model).eval()
    rng = random.Random(args.seed)
    torch.manual_seed(args.seed)
    old_hashes = metadata["trajectory_sha256"]
    old_seeds = {game["seed"] for game in metadata["training_games"]}
    reviewed = []
    new_hashes = {}
    training_games = []
    preference_hashes = {}
    for replay_path, preferences_path in args.case:
        replay_path = Path(replay_path)
        preferences_path = Path(preferences_path)
        replay_hash = sha256_file(replay_path)
        if replay_path.as_posix() in old_hashes or replay_hash in old_hashes.values():
            raise ValueError(f"preference replay already used to train parent: {replay_path}")
        trajectory = read_trajectory(replay_path)
        if trajectory.seed in old_seeds:
            raise ValueError(f"preference seed already used to train parent: {trajectory.seed}")
        verify_trajectory(trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        preferences = read_decision_preferences(preferences_path, replay_hash, trajectory)
        reviewed.extend((trajectory.decisions[item.decision_index], item)
                        for item in preferences.preferences)
        new_hashes[str(replay_path)] = replay_hash
        preference_hashes[str(preferences_path)] = sha256_file(preferences_path)
        replay_metadata = trajectory.skill_metadata or {}
        reviewed_agent = (replay_metadata.get(
            "teacher" if preferences.reviewed_seat ==
            replay_metadata.get("demonstrator_seat") else "opponent")
            if preferences.authorization == "baseline_review" else "policy")
        training_games.append({
            "seed": trajectory.seed,
            "deck_sha256": trajectory.deck_sha256,
            "main_deck_composition_sha256": tuple(
                main_deck_composition_sha256(read_ydk(deck)) for deck in trajectory.decks),
            "source": {"self_play_review": "self_play_preference",
                       "policy_review": "policy_preference",
                       "baseline_review": "baseline_preference"}[preferences.authorization],
            "authorization": preferences.authorization,
            "reviewer": preferences.reviewer,
            "reviewed_seat": preferences.reviewed_seat,
            "reviewed_agent": reviewed_agent,
            "preference_sha256": preference_hashes[str(preferences_path)],
            "selected_decisions": len(preferences.preferences),
        })
    reviewed_seeds = {game["seed"] for game in training_games}
    all_preservation = [*args.preserve_trajectory, *args.preserve_current_trajectory]
    if len({path.resolve() for path in all_preservation}) != len(all_preservation):
        raise ValueError("duplicate preservation trajectory")
    if {Path(path).resolve() for path, _ in args.case} & {
            path.resolve() for path in all_preservation}:
        raise ValueError("reviewed replay cannot also be a preservation replay")
    preservation = []
    preservation_hashes = {}
    for path in all_preservation:
        digest = sha256_file(path)
        parent_replay = path in args.preserve_trajectory
        trajectory = read_trajectory(path)
        validate_preservation_reference(
            path, digest, trajectory.seed, parent_replay=parent_replay,
            old_hashes=old_hashes, new_hashes=new_hashes,
            old_seeds=old_seeds, reviewed_seeds=reviewed_seeds)
        verify_trajectory(trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        candidates = [record for record in demonstrator_records(trajectory)
                      if len(record.legal_actions) > 1]
        if not candidates:
            raise ValueError(f"no multi-option preservation decisions: {path}")
        preservation.extend(rng.sample(candidates, min(
            args.preserve_per_trajectory, len(candidates))))
        preservation_hashes[str(path)] = digest
        if not parent_replay:
            training_games.append({
                "seed": trajectory.seed,
                "deck_sha256": trajectory.deck_sha256,
                "main_deck_composition_sha256": tuple(
                    main_deck_composition_sha256(read_ydk(deck))
                    for deck in trajectory.decks),
                "source": "parent_kl_preservation",
                "selected_decisions": 0,
            })
            new_hashes[str(path)] = digest
    if args.preserve_batch > len(preservation):
        parser.error("preserve batch exceeds available preservation decisions")
    preference_losses, kl_losses = fit_preferences_with_parent_kl(
        model, parent, agent.vocabulary, reviewed, preservation,
        steps=args.steps, preservation_batch=args.preserve_batch,
        preservation_weight=args.parent_kl_weight,
        learning_rate=args.learning_rate, rng=rng)
    sources = dict(metadata.get("source_decisions", {}))
    for game in training_games:
        source = game["source"]
        if game["selected_decisions"]:
            sources[source] = sources.get(source, 0) + game["selected_decisions"]
    child = {
        "schema_version": 1, "model_state": model.state_dict(),
        "vocabulary_codes": agent.vocabulary.codes,
        "vocabulary_card_properties": agent.vocabulary.card_properties,
        "width": model.card.embedding_dim, "feature_version": model.feature_version,
        "parent_checkpoint_sha256": sha256_file(args.checkpoint),
        "training_games": [*metadata["training_games"], *training_games],
        "trajectory_sha256": old_hashes | new_hashes,
        "source_decisions": sources,
        "new_source_decisions": {
            source: sum(game["selected_decisions"] for game in training_games
                        if game["source"] == source)
            for source in {game["source"] for game in training_games
                           if game["selected_decisions"]}},
        "training_method": "review_preference_parent_kl",
        "preference_sha256": preference_hashes,
        "preservation_sha256": preservation_hashes,
        "preference_config": {
            "steps": args.steps, "preserve_per_trajectory": args.preserve_per_trajectory,
            "preserve_batch": args.preserve_batch,
            "parent_kl_weight": args.parent_kl_weight,
            "learning_rate": args.learning_rate, "seed": args.seed,
        },
        "preference_loss_first": preference_losses[0],
        "preference_loss_last": preference_losses[-1],
        "preservation_kl_last": kl_losses[-1],
        "torch_version": str(torch.__version__),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(child, args.output)
    print(json.dumps({"output": str(args.output), "preferences": len(reviewed),
                      "preservation_states": len(preservation),
                      "preference_loss_first": preference_losses[0],
                      "preference_loss_last": preference_losses[-1],
                      "preservation_kl_last": kl_losses[-1]}, indent=2))


if __name__ == "__main__":
    main()
