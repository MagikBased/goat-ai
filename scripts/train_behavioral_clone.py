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
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import (
    demonstrator_records,
    demonstrator_seat,
    read_decision_annotations,
    read_trajectory,
    verify_trajectory,
)
from goat_ai.training import (
    CardVocabulary,
    LegalActionPolicy,
    fit_behavioral_clone,
)
from goat_ai.training.policy import POLICY_FEATURE_VERSION

SOURCE_KINDS = frozenset((
    "activate", "attack", "chain", "change_position", "flip_summon",
    "normal_summon", "set_monster", "set_spell_trap", "special_summon",
))


def focus_opportunity(record, codes: set[int]) -> bool:
    """A visible option or public chain link involves a selected card ID."""
    return (len(record.legal_actions) > 1 and (
        any(action.kind in SOURCE_KINDS and action.parameters.get("code") in codes
            for action in record.legal_actions)
        or any(link.card_code in codes for link in record.observation.chain)))


def load_parent_checkpoint(path: Path, model: LegalActionPolicy,
                           vocabulary: CardVocabulary) -> dict:
    """Continue a clone only when weights and held-out provenance are compatible."""
    parent = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(parent, dict) or parent.get("schema_version") != 1:
        raise ValueError("unsupported parent policy checkpoint schema")
    if (parent.get("width") != model.card.embedding_dim
            or parent.get("feature_version", 1) != model.feature_version
            or tuple(parent.get("vocabulary_codes", ())) != vocabulary.codes):
        raise ValueError("parent policy architecture or vocabulary does not match")
    games = parent.get("training_games")
    if not isinstance(games, list) or not games or any(
            not isinstance(game, dict)
            or not isinstance(game.get("seed"), int)
            or not isinstance(game.get("deck_sha256"), (tuple, list))
            or len(game["deck_sha256"]) != 2
            or not isinstance(game.get("main_deck_composition_sha256"), (tuple, list))
            or len(game["main_deck_composition_sha256"]) != 2
            for game in games):
        raise ValueError("parent checkpoint lacks held-out training provenance")
    hashes = parent.get("trajectory_sha256")
    if not isinstance(hashes, dict):
        raise TypeError("parent checkpoint lacks trajectory hashes")
    model.load_state_dict(parent["model_state"], strict=True)
    return parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectories", nargs="+", type=Path)
    parser.add_argument("--annotation", type=Path, action="append", default=[],
                        help="self-recorded labels, one per trajectory in the same order; "
                             "train only annotated decisions")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"), default="restricted")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--init-checkpoint", type=Path,
                        help="continue compatible weights and preserve parent training provenance")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1,
                        help="decisions per optimizer update; forward passes remain individual")
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--feature-version", type=int, choices=tuple(range(1, 19)),
                        default=POLICY_FEATURE_VERSION)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--focus-card", type=int, action="append", default=[],
                        help="increase exposure of decisions offering or responding to this card")
    parser.add_argument("--focus-weight", type=float, default=1.0,
                        help="relative sampling weight for focus-card opportunities")
    args = parser.parse_args()
    if (args.epochs < 1 or args.width < 1 or args.learning_rate <= 0
            or args.batch_size < 1 or not 1 <= args.focus_weight < float("inf")
            or any(code <= 0 for code in args.focus_card)
            or args.focus_weight > 1 and not args.focus_card):
        parser.error("training parameters must be positive; focus weight needs focus cards")
    if args.annotation and len(args.annotation) != len(args.trajectories):
        parser.error("provide one annotation file for each trajectory")
    if args.init_checkpoint and args.init_checkpoint.resolve() == args.output.resolve():
        parser.error("--output must differ from --init-checkpoint")
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    records = []
    sources: Counter[str] = Counter()
    trajectory_hashes = {}
    training_games = []
    for index, path in enumerate(args.trajectories):
        raw = path.read_bytes()
        trajectory = read_trajectory(path)
        if trajectory.schema_version not in range(3, 23) or not trajectory.deck_sha256 or not (
            trajectory.asset_sha256
        ):
            raise ValueError(f"{path}: training requires replay-fingerprinted schema v3–v22")
        if args.feature_version >= 17 and trajectory.schema_version < 22:
            raise ValueError(f"{path}: feature version {args.feature_version} requires "
                             "schema v22 attack context")
        count = verify_trajectory(trajectory, engine_type(args.native_root))
        annotation = None
        if args.annotation:
            audit_trajectory_visibility(trajectory)
            annotation, selected = read_decision_annotations(
                args.annotation[index], hashlib.sha256(raw).hexdigest(), trajectory)
        else:
            selected = demonstrator_records(trajectory)
        records.extend(selected)
        source = "human_annotation" if annotation is not None else trajectory.source
        sources[source] += len(selected)
        trajectory_hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        training_games.append({"seed": trajectory.seed,
                               "deck_sha256": trajectory.deck_sha256,
                               "main_deck_composition_sha256": tuple(
                                   main_deck_composition_sha256(read_ydk(deck))
                                   for deck in trajectory.decks),
                               "source": source,
                               "demonstrator_seat": (None if annotation is not None
                                                     else demonstrator_seat(trajectory)),
                               "annotation_sha256": (hashlib.sha256(
                                   args.annotation[index].read_bytes()).hexdigest()
                                   if annotation is not None else None),
                               "authorization": ("self_recorded" if annotation is not None
                                                 else (trajectory.skill_metadata or {}).get(
                                                     "authorization")),
                               "reviewer": annotation.reviewer if annotation is not None else None,
                               "teacher": (trajectory.skill_metadata or {}).get("teacher"),
                               "teacher_version": (trajectory.skill_metadata or {}).get(
                                   "teacher_version"),
                               "opponent": (trajectory.skill_metadata or {}).get("opponent"),
                               "verified_decisions": count,
                               "selected_decisions": len(selected)})
    vocabulary = CardVocabulary.from_goat_whitelist(
        args.native_root / "banlist/GOAT.lflist.conf")
    torch.manual_seed(args.seed)
    model = LegalActionPolicy(vocabulary.size, width=args.width,
                              feature_version=args.feature_version)
    parent = (load_parent_checkpoint(args.init_checkpoint, model, vocabulary)
              if args.init_checkpoint else None)
    inherited_hashes = parent.get("trajectory_sha256", {}) if parent else {}
    collisions = {path for path, digest in trajectory_hashes.items()
                  if path in inherited_hashes and inherited_hashes[path] != digest}
    if collisions:
        raise ValueError(f"training trajectory path changed since parent checkpoint: "
                         f"{sorted(collisions)}")
    focus_codes = set(args.focus_card)
    focus_count = sum(focus_opportunity(record, focus_codes) for record in records)
    sampling_weights = ([args.focus_weight if focus_opportunity(record, focus_codes) else 1.0
                         for record in records]
                        if args.focus_weight > 1 else None)
    losses = fit_behavioral_clone(model, vocabulary, records, epochs=args.epochs,
                                  learning_rate=args.learning_rate, seed=args.seed,
                                  batch_size=args.batch_size,
                                  sampling_weights=sampling_weights)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    inherited_sources = Counter(parent.get("source_decisions", {})) if parent else Counter()
    checkpoint = {
        "schema_version": 1, "model_state": model.state_dict(),
        "vocabulary_codes": vocabulary.codes, "width": args.width,
        "feature_version": model.feature_version,
        "trajectory_sha256": inherited_hashes | trajectory_hashes,
        "source_decisions": dict(inherited_sources + sources),
        "new_source_decisions": dict(sources),
        "training_games": [*(parent["training_games"] if parent else ()),
                           *training_games],
        "new_training_games": len(training_games),
        "parent_checkpoint_sha256": (hashlib.sha256(
            args.init_checkpoint.read_bytes()).hexdigest()
            if args.init_checkpoint else None),
        "seed": args.seed, "torch_version": str(torch.__version__),
        "batch_size": args.batch_size,
        "focus_cards": tuple(sorted(focus_codes)),
        "focus_weight": args.focus_weight,
        "focus_opportunity_decisions": focus_count,
        "sampling_mode": "weighted_with_replacement" if sampling_weights else "shuffle",
        "losses": losses,
    }
    torch.save(checkpoint, args.output)
    print(json.dumps({"output": str(args.output), "decisions": len(records),
                      "sources": sources, "epoch_loss": losses,
                      "focus_opportunity_decisions": focus_count}, indent=2))


if __name__ == "__main__":
    main()
