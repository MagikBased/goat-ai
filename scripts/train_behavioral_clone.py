"""Fit a first policy on replay-verified decision trajectories."""

import argparse
import copy
import hashlib
import json
import random
from collections import Counter
from math import isfinite
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
    fit_with_parent_kl,
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


def annotation_paths(trajectories: list[Path], ordered: list[Path],
                     assigned: list[str]) -> dict[Path, Path]:
    """Resolve optional labels by trajectory without relabeling unannotated games."""
    available = {path.resolve() for path in trajectories}
    if len(available) != len(trajectories):
        raise ValueError("duplicate trajectory path")
    if ordered and assigned:
        raise ValueError("use --annotation or --annotation-for, not both")
    if ordered:
        if len(ordered) != len(trajectories):
            raise ValueError("provide one annotation file for each trajectory")
        return {path.resolve(): label for path, label in zip(trajectories, ordered)}
    labels: dict[Path, Path] = {}
    for assignment in assigned:
        trajectory, separator, label = assignment.partition("=")
        if not separator or not trajectory or not label:
            raise ValueError("--annotation-for needs TRAJECTORY=LABELS")
        resolved = Path(trajectory).resolve()
        if resolved not in available:
            raise ValueError(f"annotation trajectory was not supplied: {trajectory}")
        if resolved in labels:
            raise ValueError(f"duplicate annotation for trajectory: {trajectory}")
        labels[resolved] = Path(label)
    return labels


def parse_source_weights(assignments: list[str], *, option: str = "source") -> dict[str, float]:
    weights = {}
    for assignment in assignments:
        source, separator, raw = assignment.partition("=")
        if not separator or not source:
            raise ValueError(f"--{option}-weight needs NAME=POSITIVE_WEIGHT")
        if source in weights:
            raise ValueError(f"duplicate {option} weight: {source}")
        try:
            weight = float(raw)
        except ValueError as exc:
            raise ValueError("source weight must be finite and positive") from exc
        if not isfinite(weight) or weight <= 0:
            raise ValueError("source weight must be finite and positive")
        weights[source] = weight
    return weights


def restrict_trainable_modules(model: LegalActionPolicy, modules: list[str]) -> None:
    """Freeze other modules for a controlled, low-drift warm-start update."""
    if not modules:
        return
    available = dict(model.named_children())
    unknown = set(modules) - set(available)
    if unknown:
        raise ValueError(f"unknown trainable modules: {sorted(unknown)}")
    for name, parameter in model.named_parameters():
        parameter.requires_grad = any(name.startswith(f"{module}.") for module in modules)


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
                        help="authorized self-recorded or scripted-scenario labels, "
                             "one per trajectory in the same order; train only those decisions")
    parser.add_argument("--annotation-for", action="append", default=[],
                        metavar="TRAJECTORY=LABELS",
                        help="label selected trajectories; unlisted demonstrations use their "
                             "recorded demonstrator seat")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"), default="restricted")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--init-checkpoint", type=Path,
                        help="continue compatible weights and preserve parent training provenance")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1,
                        help="decisions per optimizer update; forward passes remain individual")
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--feature-version", type=int, choices=tuple(range(1, 20)),
                        default=POLICY_FEATURE_VERSION)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--focus-card", type=int, action="append", default=[],
                        help="increase exposure of decisions offering or responding to this card")
    parser.add_argument("--focus-weight", type=float, default=1.0,
                        help="relative sampling weight for focus-card opportunities")
    parser.add_argument("--source-weight", action="append", default=[],
                        metavar="SOURCE=WEIGHT",
                        help="relative sampling weight for a recorded decision source")
    parser.add_argument("--trainable-module", action="append", default=[],
                        metavar="MODULE",
                        help="train only these top-level policy modules; repeat to include more")
    parser.add_argument("--parent-kl-steps", type=int, default=0,
                        help="fit selected labels with parent-policy KL preservation")
    parser.add_argument("--preserve-trajectories", nargs="+", type=Path, default=[],
                        help="replay-verified parent training games for KL preservation")
    parser.add_argument("--preserve-per-trajectory", type=int, default=32,
                        help="multi-option parent states sampled from each preservation game")
    parser.add_argument("--preserve-batch", type=int, default=8,
                        help="parent states sampled at each KL optimization step")
    parser.add_argument("--parent-kl-weight", type=float, default=1.0)
    parser.add_argument("--label-kind-weight", action="append", default=[],
                        metavar="ACTION_KIND=WEIGHT",
                        help="relative weight for selected labels in parent-KL training")
    args = parser.parse_args()
    if (args.epochs < 1 or args.width < 1 or args.learning_rate <= 0
            or args.batch_size < 1 or not 1 <= args.focus_weight < float("inf")
            or any(code <= 0 for code in args.focus_card)
            or args.focus_weight > 1 and not args.focus_card):
        parser.error("training parameters must be positive; focus weight needs focus cards")
    try:
        labels_by_path = annotation_paths(args.trajectories, args.annotation,
                                          args.annotation_for)
        source_weights = parse_source_weights(args.source_weight)
        label_kind_weights = parse_source_weights(args.label_kind_weight,
                                                  option="label-kind")
    except ValueError as exc:
        parser.error(str(exc))
    if args.init_checkpoint and args.init_checkpoint.resolve() == args.output.resolve():
        parser.error("--output must differ from --init-checkpoint")
    if (args.parent_kl_steps < 0 or args.preserve_per_trajectory < 1
            or args.preserve_batch < 1 or not isfinite(args.parent_kl_weight)
            or args.parent_kl_weight <= 0):
        parser.error("parent KL settings must be finite and positive")
    if args.parent_kl_steps and (not args.init_checkpoint or not args.preserve_trajectories):
        parser.error("parent KL requires --init-checkpoint and --preserve-trajectories")
    if not args.parent_kl_steps and args.preserve_trajectories:
        parser.error("--preserve-trajectories requires --parent-kl-steps")
    if not args.parent_kl_steps and label_kind_weights:
        parser.error("--label-kind-weight requires --parent-kl-steps")
    if args.parent_kl_steps and (source_weights or args.focus_weight > 1):
        parser.error("parent KL uses labeled decisions directly; omit sampling weights")
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    records = []
    record_sources = []
    sources: Counter[str] = Counter()
    trajectory_hashes = {}
    training_games = []
    for path in args.trajectories:
        raw = path.read_bytes()
        trajectory = read_trajectory(path)
        if trajectory.schema_version not in range(3, 24) or not trajectory.deck_sha256 or not (
            trajectory.asset_sha256
        ):
            raise ValueError(f"{path}: training requires replay-fingerprinted schema v3–v23")
        if args.feature_version >= 17 and trajectory.schema_version < 22:
            raise ValueError(f"{path}: feature version {args.feature_version} requires "
                             "schema v22 attack context")
        if args.feature_version >= 19 and trajectory.schema_version < 23:
            raise ValueError(f"{path}: feature version 19 requires schema v23 turn owner")
        count = verify_trajectory(trajectory, engine_type(args.native_root))
        audit_trajectory_visibility(trajectory)
        annotation = None
        label_path = labels_by_path.get(path.resolve())
        if label_path is not None:
            annotation, selected = read_decision_annotations(
                label_path, hashlib.sha256(raw).hexdigest(), trajectory)
        else:
            if trajectory.source.startswith("scripted_"):
                raise ValueError(f"{path}: scripted replay requires explicit annotations")
            selected = demonstrator_records(trajectory)
        source = ({"self_recorded": "human_annotation",
                   "scripted_scenario": "synthetic_annotation"}[annotation.authorization]
                  if annotation is not None else trajectory.source)
        records.extend(selected)
        record_sources.extend([source] * len(selected))
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
                                   label_path.read_bytes()).hexdigest()
                                   if annotation is not None else None),
                               "authorization": (annotation.authorization if annotation is not None
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
    try:
        restrict_trainable_modules(model, args.trainable_module)
    except ValueError as exc:
        parser.error(str(exc))
    inherited_hashes = parent.get("trajectory_sha256", {}) if parent else {}
    collisions = {path for path, digest in trajectory_hashes.items()
                  if path in inherited_hashes and inherited_hashes[path] != digest}
    if collisions:
        raise ValueError(f"training trajectory path changed since parent checkpoint: "
                         f"{sorted(collisions)}")
    unknown_sources = set(source_weights) - set(sources)
    if unknown_sources:
        raise ValueError(f"source weights name absent decision sources: "
                         f"{sorted(unknown_sources)}")
    unknown_kinds = set(label_kind_weights) - {record.selected_action.kind
                                               for record in records}
    if unknown_kinds:
        raise ValueError(f"label kind weights name absent selected actions: "
                         f"{sorted(unknown_kinds)}")
    focus_codes = set(args.focus_card)
    focus_count = sum(focus_opportunity(record, focus_codes) for record in records)
    sampling_weights = ([source_weights.get(source, 1.0) * (
        args.focus_weight if focus_opportunity(record, focus_codes) else 1.0)
        for record, source in zip(records, record_sources)]
        if args.focus_weight > 1 or any(weight != 1 for weight in source_weights.values())
        else None)
    preservation_metadata = None
    if args.parent_kl_steps:
        if len({path.resolve() for path in args.preserve_trajectories}) != len(
                args.preserve_trajectories):
            raise ValueError("duplicate preservation trajectory path")
        reference = copy.deepcopy(model).eval()
        rng = random.Random(args.seed)
        preservation = []
        preservation_hashes = {}
        for path in args.preserve_trajectories:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if parent["trajectory_sha256"].get(str(path)) != digest:
                raise ValueError(f"{path}: preservation replay is absent from parent provenance")
            trajectory = read_trajectory(path)
            verify_trajectory(trajectory, engine_type(args.native_root))
            audit_trajectory_visibility(trajectory)
            candidates = [record for record in demonstrator_records(trajectory)
                          if len(record.legal_actions) > 1]
            if not candidates:
                raise ValueError(f"{path}: no multi-option preservation decisions")
            preservation.extend(rng.sample(candidates, min(
                args.preserve_per_trajectory, len(candidates))))
            preservation_hashes[str(path)] = digest
        losses, preservation_losses = fit_with_parent_kl(
            model, reference, vocabulary, records, preservation,
            steps=args.parent_kl_steps, preservation_batch=args.preserve_batch,
            preservation_weight=args.parent_kl_weight,
            learning_rate=args.learning_rate, rng=rng,
            labeled_weights=[label_kind_weights.get(record.selected_action.kind, 1.0)
                             for record in records])
        preservation_metadata = {
            "trajectory_sha256": preservation_hashes,
            "states": len(preservation),
            "per_trajectory": args.preserve_per_trajectory,
            "batch": args.preserve_batch,
            "weight": args.parent_kl_weight,
            "label_kind_weights": label_kind_weights,
            "steps": args.parent_kl_steps,
            "final_kl": preservation_losses[-1],
        }
    else:
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
        "source_weights": source_weights,
        "trainable_modules": tuple(args.trainable_module) or ("all",),
        "training_method": "parent_kl" if preservation_metadata else "behavioral_clone",
        "parent_kl": preservation_metadata,
        "focus_opportunity_decisions": focus_count,
        "sampling_mode": ("parent_kl" if preservation_metadata else
                          "weighted_with_replacement" if sampling_weights else "shuffle"),
        "losses": losses,
    }
    torch.save(checkpoint, args.output)
    summary = {"output": str(args.output), "decisions": len(records),
               "sources": sources, "focus_opportunity_decisions": focus_count}
    if preservation_metadata:
        summary.update({"training_method": "parent_kl",
                        "final_labeled_loss": losses[-1],
                        "final_preservation_kl": preservation_losses[-1],
                        "preservation_states": len(preservation)})
    else:
        summary["epoch_loss"] = losses
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
