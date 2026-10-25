"""Fit a first policy on replay-verified decision trajectories."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import torch

from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.replay import demonstrator_records, read_trajectory, verify_trajectory
from goat_ai.training import (
    CardVocabulary,
    LegalActionPolicy,
    fit_behavioral_clone,
)
from goat_ai.training.policy import POLICY_FEATURE_VERSION


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectories", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"), default="restricted")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--feature-version", type=int, choices=(1, 2, 3, 4, 5, 6, 7, 8, 9),
                        default=POLICY_FEATURE_VERSION)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.epochs < 1 or args.width < 1 or args.learning_rate <= 0:
        parser.error("epochs, width, and learning rate must be positive")
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    records = []
    sources: Counter[str] = Counter()
    trajectory_hashes = {}
    training_games = []
    for path in args.trajectories:
        raw = path.read_bytes()
        trajectory = read_trajectory(path)
        if trajectory.schema_version not in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17) or not trajectory.deck_sha256 or not (
            trajectory.asset_sha256
        ):
            raise ValueError(f"{path}: training requires replay-fingerprinted schema v3–v17")
        count = verify_trajectory(trajectory, engine_type(args.native_root))
        selected = demonstrator_records(trajectory)
        records.extend(selected)
        sources[trajectory.source] += len(selected)
        trajectory_hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        training_games.append({"seed": trajectory.seed,
                               "deck_sha256": trajectory.deck_sha256,
                               "main_deck_composition_sha256": tuple(
                                   main_deck_composition_sha256(read_ydk(deck))
                                   for deck in trajectory.decks),
                               "source": trajectory.source,
                               "demonstrator_seat": (trajectory.skill_metadata or {}).get(
                                   "demonstrator_seat"),
                               "verified_decisions": count,
                               "selected_decisions": len(selected)})
    vocabulary = CardVocabulary.from_goat_whitelist(
        args.native_root / "banlist/GOAT.lflist.conf")
    torch.manual_seed(args.seed)
    model = LegalActionPolicy(vocabulary.size, width=args.width,
                              feature_version=args.feature_version)
    losses = fit_behavioral_clone(model, vocabulary, records, epochs=args.epochs,
                                  learning_rate=args.learning_rate, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "schema_version": 1, "model_state": model.state_dict(),
        "vocabulary_codes": vocabulary.codes, "width": args.width,
        "feature_version": model.feature_version,
        "trajectory_sha256": trajectory_hashes, "source_decisions": dict(sources),
        "training_games": training_games,
        "seed": args.seed, "torch_version": str(torch.__version__),
        "losses": losses,
    }
    torch.save(checkpoint, args.output)
    print(json.dumps({"output": str(args.output), "decisions": len(records),
                      "sources": sources, "epoch_loss": losses}, indent=2))


if __name__ == "__main__":
    main()
