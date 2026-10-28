"""Fit a first policy on replay-verified decision trajectories."""

import argparse
import copy
import hashlib
import json
import multiprocessing
import random
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from math import isfinite
from pathlib import Path
from time import perf_counter

import torch

from goat_ai.agents import (
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.evaluation.thunder_search_audit import correct_staged_thunder_search
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import (
    demonstrator_records,
    demonstrator_seat,
    read_decision_annotations,
    read_trajectory,
    training_demonstrator_records,
    verify_trajectory,
)
from goat_ai.training import (
    CardVocabulary,
    LegalActionPolicy,
    fit_behavioral_clone,
    fit_with_parent_kl,
)
from goat_ai.training.on_policy_teacher import (
    filter_activation_opportunities,
    label_policy_trajectory,
    teacher_disagreement_flags,
)
from goat_ai.training.policy import POLICY_FEATURE_VERSION

SOURCE_KINDS = frozenset((
    "activate", "attack", "chain", "change_position", "flip_summon",
    "normal_summon", "set_monster", "set_spell_trap", "special_summon",
))


def verify_training_trajectory(task: tuple[Path, Path, str, bool]) -> tuple[int, str]:
    """Verify one recorded duel in an isolated native-engine process."""
    path, native_root, engine, fast_json = task
    engine_type = (RestrictedOcgcoreEngine if engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    trajectory = read_trajectory(path, fast_json=fast_json)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"{path}: trajectory changed during verification")
    count = verify_trajectory(trajectory, engine_type(native_root))
    audit_trajectory_visibility(trajectory)
    return count, digest


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


def decision_sampling_weights(records, sources, source_weights, focus_codes,
                              focus_weight, kind_weights,
                              disagreement_flags=None, disagreement_weight=1.0):
    """Compose opt-in BC sampling factors without changing unweighted runs."""
    if (len(records) != len(sources)
            or disagreement_flags is not None
            and len(disagreement_flags) != len(records)):
        raise ValueError("one source is required for each decision")
    if (not kind_weights and focus_weight == 1 and disagreement_weight == 1
            and all(weight == 1 for weight in source_weights.values())):
        return None
    return [source_weights.get(source, 1.0)
            * (focus_weight if focus_opportunity(record, focus_codes) else 1.0)
            * kind_weights.get(record.selected_action.kind, 1.0)
            * (disagreement_weight if disagreement_flags is not None
               and disagreement_flags[index] else 1.0)
            for index, (record, source) in enumerate(zip(records, sources))]


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
                           vocabulary: CardVocabulary, *,
                           allow_v23_to_v24: bool = False,
                           allow_v23_to_v25: bool = False,
                           allow_v23_to_v26: bool = False,
                           allow_v23_to_v27: bool = False,
                           allow_v23_to_v28: bool = False,
                           allow_v23_to_v29: bool = False,
                           allow_v23_to_v30: bool = False,
                           allow_v23_to_v31: bool = False) -> dict:
    """Continue a clone only when weights and held-out provenance are compatible."""
    parent = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(parent, dict) or parent.get("schema_version") != 1:
        raise ValueError("unsupported parent policy checkpoint schema")
    if (allow_v23_to_v24 or allow_v23_to_v25 or allow_v23_to_v26
            or allow_v23_to_v27 or allow_v23_to_v28 or allow_v23_to_v29
            or allow_v23_to_v30 or allow_v23_to_v31) and parent.get(
            "feature_version") != 23:
        raise ValueError("feature upgrade requires a feature-v23 parent")
    upgrade = (parent.get("feature_version") == 23
               and ((allow_v23_to_v24 and model.feature_version == 24)
                    or (allow_v23_to_v25 and model.feature_version == 25)
                    or (allow_v23_to_v26 and model.feature_version == 26)
                    or (allow_v23_to_v27 and model.feature_version == 27)
                    or (allow_v23_to_v28 and model.feature_version == 28)
                    or (allow_v23_to_v29 and model.feature_version == 29)
                    or (allow_v23_to_v30 and model.feature_version == 30)
                    or (allow_v23_to_v31 and model.feature_version == 31)))
    if (parent.get("width") != model.card.embedding_dim
            or (parent.get("feature_version", 1) != model.feature_version and not upgrade)
            or tuple(parent.get("vocabulary_codes", ())) != vocabulary.codes
            or tuple(tuple(item) for item in parent.get(
                "vocabulary_card_properties", ())) != vocabulary.card_properties):
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
    state = parent["model_state"]
    if upgrade:
        state = dict(state)
        if model.feature_version in (24, 25):
            key = "action_numbers.0.weight"
            original = state[key]
            expanded = torch.zeros_like(model.state_dict()[key])
            if (original.shape != (model.card.embedding_dim, 101)
                    or expanded.shape != (model.card.embedding_dim, 104)):
                raise ValueError("feature upgrade needs v23 action width 101 and resource width 104")
            expanded[:, :101] = original
            state[key] = expanded
        if model.feature_version == 25:
            state["trade_head.weight"] = model.state_dict()["trade_head.weight"].clone()
        if model.feature_version == 26:
            state["player_pool.weight"] = model.state_dict()["player_pool.weight"].clone()
        if model.feature_version == 27:
            for key in ("action_query.weight", "attended_card.weight"):
                state[key] = model.state_dict()[key].clone()
        if model.feature_version in (28, 29, 30, 31):
            for key, axis, growth in (("kind.weight", 0, 1),
                                      ("target_context.0.weight", 1, 1),
                                      ("action_numbers.0.weight", 1,
                                       36 if model.feature_version == 31 else
                                       3 if model.feature_version == 30 else 2)):
                original = state[key]
                expanded = torch.zeros_like(model.state_dict()[key])
                if (original.ndim != 2 or expanded.ndim != 2
                        or expanded.shape[axis] != original.shape[axis] + growth
                        or expanded.shape[1 - axis] != original.shape[1 - axis]):
                    raise ValueError("feature upgrade needs one new counter action input")
                if axis == 0:
                    expanded[:original.shape[0]] = original
                else:
                    expanded[:, :original.shape[1]] = original
                state[key] = expanded
        if model.feature_version in (29, 30, 31):
            key = "card_numbers.0.weight"
            original = state[key]
            expanded = torch.zeros_like(model.state_dict()[key])
            if expanded.shape != (original.shape[0], original.shape[1] + 1):
                raise ValueError("feature upgrade needs one new public age input")
            expanded[:, :original.shape[1]] = original
            state[key] = expanded
    model.load_state_dict(state, strict=True)
    return parent


def main() -> None:
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectories", nargs="+", type=Path)
    parser.add_argument("--annotation", type=Path, action="append", default=[],
                        help="self-recorded, scripted-scenario, policy-review, or "
                             "self-play-review labels, "
                             "one per trajectory in the same order; train only those decisions")
    parser.add_argument("--annotation-for", action="append", default=[],
                        metavar="TRAJECTORY=LABELS",
                        help="label selected trajectories; unlisted demonstrations use their "
                             "recorded demonstrator seat")
    parser.add_argument("--on-policy-teacher", choices=("tactical_v14", "tactical_card_advantage"),
                        help="label replay-verified policy-visited states with the "
                             "named synthetic teacher; requires --init-checkpoint")
    parser.add_argument("--on-policy-teacher-activation-focus-only", action="store_true",
                        help="train only decisions offering activation of a --focus-card")
    parser.add_argument("--on-policy-disagreement-weight", type=float, default=1.0,
                        help="relative sampling weight for policy/teacher disagreements")
    parser.add_argument("--synthetic-thunder-search-correction", action="store_true",
                        help="opt-in Tactical-v14 relabeling: take an offered Deck copy "
                             "instead of a zero-copy Thunder Dragon search")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"), default="restricted")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--init-checkpoint", type=Path,
                        help="continue compatible weights and preserve parent training provenance")
    parser.add_argument("--upgrade-feature-23-to-24", action="store_true",
                        help="zero-extend only the v23 action-number input when loading its parent")
    parser.add_argument("--upgrade-feature-23-to-25", action="store_true",
                        help="zero-extend v23 action numbers and initialize a zero trade head")
    parser.add_argument("--upgrade-feature-23-to-26", action="store_true",
                        help="load v23 weights and add a zero-initialized owner pool")
    parser.add_argument("--upgrade-feature-23-to-27", action="store_true",
                        help="load v23 weights and add zero-output action-to-card attention")
    parser.add_argument("--upgrade-feature-23-to-28", action="store_true",
                        help="load v23 weights and add counter-allocation action features")
    parser.add_argument("--upgrade-feature-23-to-29", action="store_true",
                        help="load v23 weights with counter choices and public face-up age")
    parser.add_argument("--upgrade-feature-23-to-30", action="store_true",
                        help="load v23 weights with distinct option choices, counters, and age")
    parser.add_argument("--upgrade-feature-23-to-31", action="store_true",
                        help="load v23 weights with distinct card announcements and v30 features")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1,
                        help="decisions per optimizer update; combine forward passes with --batched-forward")
    parser.add_argument("--batched-forward", action="store_true",
                        help="opt-in padded variable-action policy forward for supported v10+ models")
    parser.add_argument("--skip-forced-training", action="store_true",
                        help="exclude one-legal-action records from cloning updates; "
                             "they have zero choice loss but still remain in replay provenance")
    parser.add_argument("--omit-forced-forward", action="store_true",
                        help="keep original cloning batches and optimizer steps but omit "
                             "one-legal-action choices from mixed neural forwards; "
                             "requires --batched-forward")
    parser.add_argument("--verification-workers", type=int, default=1,
                        help="native replay verification processes (default: serial)")
    parser.add_argument("--fast-trajectory-json", action="store_true",
                        help="use optional orjson to decode input trajectories in the main "
                             "process and replay-verification workers")
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--feature-version", type=int, choices=tuple(range(1, 32)),
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
                        help="sample rare selected action kinds more often in cloning; "
                             "weight their loss in parent-KL training")
    args = parser.parse_args()
    if (args.epochs < 1 or args.width < 1 or args.learning_rate <= 0
            or args.batch_size < 1 or args.verification_workers < 1
            or not 1 <= args.focus_weight < float("inf")
            or not 1 <= args.on_policy_disagreement_weight < float("inf")
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
    if args.upgrade_feature_23_to_24 and (not args.init_checkpoint
                                         or args.feature_version != 24):
        parser.error("--upgrade-feature-23-to-24 requires a parent and feature v24")
    if args.upgrade_feature_23_to_25 and (not args.init_checkpoint
                                         or args.feature_version != 25):
        parser.error("--upgrade-feature-23-to-25 requires a parent and feature v25")
    if args.upgrade_feature_23_to_26 and (not args.init_checkpoint
                                         or args.feature_version != 26):
        parser.error("--upgrade-feature-23-to-26 requires a parent and feature v26")
    if args.upgrade_feature_23_to_27 and (not args.init_checkpoint
                                         or args.feature_version != 27):
        parser.error("--upgrade-feature-23-to-27 requires a parent and feature v27")
    if args.upgrade_feature_23_to_28 and (not args.init_checkpoint
                                         or args.feature_version != 28):
        parser.error("--upgrade-feature-23-to-28 requires a parent and feature v28")
    if args.upgrade_feature_23_to_29 and (not args.init_checkpoint
                                         or args.feature_version != 29):
        parser.error("--upgrade-feature-23-to-29 requires a parent and feature v29")
    if args.upgrade_feature_23_to_30 and (not args.init_checkpoint
                                         or args.feature_version != 30):
        parser.error("--upgrade-feature-23-to-30 requires a parent and feature v30")
    if args.upgrade_feature_23_to_31 and (not args.init_checkpoint
                                         or args.feature_version != 31):
        parser.error("--upgrade-feature-23-to-31 requires a parent and feature v31")
    if sum((args.upgrade_feature_23_to_24, args.upgrade_feature_23_to_25,
            args.upgrade_feature_23_to_26, args.upgrade_feature_23_to_27,
            args.upgrade_feature_23_to_28, args.upgrade_feature_23_to_29,
            args.upgrade_feature_23_to_30, args.upgrade_feature_23_to_31)) > 1:
        parser.error("select only one feature-upgrade path")
    if args.on_policy_teacher and (not args.init_checkpoint or args.annotation
                                   or args.annotation_for):
        parser.error("--on-policy-teacher requires --init-checkpoint and no annotations")
    if args.synthetic_thunder_search_correction and (
            args.on_policy_teacher or args.annotation or args.annotation_for):
        parser.error("synthetic Thunder correction requires raw Tactical trajectories")
    if args.on_policy_teacher_activation_focus_only and (
            not args.on_policy_teacher or not args.focus_card):
        parser.error("activation focus requires --on-policy-teacher and --focus-card")
    if args.on_policy_disagreement_weight > 1 and (
            not args.on_policy_teacher or args.on_policy_teacher_activation_focus_only):
        parser.error("disagreement weighting requires unfiltered on-policy teacher labels")
    if (args.parent_kl_steps < 0 or args.preserve_per_trajectory < 1
            or args.preserve_batch < 1 or not isfinite(args.parent_kl_weight)
            or args.parent_kl_weight <= 0):
        parser.error("parent KL settings must be finite and positive")
    if args.parent_kl_steps and (not args.init_checkpoint or not args.preserve_trajectories):
        parser.error("parent KL requires --init-checkpoint and --preserve-trajectories")
    if not args.parent_kl_steps and args.preserve_trajectories:
        parser.error("--preserve-trajectories requires --parent-kl-steps")
    if args.parent_kl_steps and (source_weights or args.focus_weight > 1):
        parser.error("parent KL uses labeled decisions directly; omit sampling weights")
    if args.parent_kl_steps and args.on_policy_disagreement_weight > 1:
        parser.error("disagreement weighting is supported only for behavioral cloning")
    if args.batched_forward and args.parent_kl_steps:
        parser.error("batched forward is currently supported only for behavioral cloning")
    if args.skip_forced_training and args.parent_kl_steps:
        parser.error("skipping forced choices is currently supported only for behavioral cloning")
    if args.omit_forced_forward and (not args.batched_forward
                                    or args.skip_forced_training
                                    or args.parent_kl_steps):
        parser.error("--omit-forced-forward requires behavioral cloning with "
                     "--batched-forward and without --skip-forced-training")
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    teacher = (TacticalHeuristicAgent(
        load_flip_monster_codes(args.native_root),
        load_card_races(args.native_root),
        card_facts=load_card_facts(args.native_root),
        card_advantage_guard=args.on_policy_teacher == "tactical_card_advantage")
        if args.on_policy_teacher else None)
    teacher_parent_hash = (hashlib.sha256(args.init_checkpoint.read_bytes()).hexdigest()
                           if teacher is not None else None)
    records = []
    record_sources = []
    record_disagreements = []
    sources: Counter[str] = Counter()
    trajectory_hashes = {}
    training_games = []
    thunder_corrections = 0
    verification_seconds = 0.0
    verified_results = None
    if args.verification_workers > 1:
        verification_started = perf_counter()
        tasks = [(path, args.native_root, args.engine, args.fast_trajectory_json)
                 for path in args.trajectories]
        with ProcessPoolExecutor(max_workers=args.verification_workers,
                                 mp_context=multiprocessing.get_context("spawn")) as pool:
            verified_results = list(pool.map(verify_training_trajectory, tasks))
        verification_seconds = perf_counter() - verification_started
    for trajectory_index, path in enumerate(args.trajectories):
        raw = path.read_bytes()
        trajectory = read_trajectory(path, fast_json=args.fast_trajectory_json)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(raw).digest():
            raise ValueError(f"{path}: trajectory changed while loading")
        if trajectory.schema_version not in range(3, 27) or not trajectory.deck_sha256 or not (
            trajectory.asset_sha256
        ):
            raise ValueError(f"{path}: training requires replay-fingerprinted schema v3–v26")
        if args.feature_version >= 17 and trajectory.schema_version < 22:
            raise ValueError(f"{path}: feature version {args.feature_version} requires "
                             "schema v22 attack context")
        if args.feature_version >= 19 and trajectory.schema_version < 23:
            raise ValueError(f"{path}: feature version {args.feature_version} requires "
                             "schema v23 turn owner")
        if args.feature_version >= 21 and trajectory.schema_version < 24:
            raise ValueError(f"{path}: feature version {args.feature_version} requires "
                             "schema v24 current monster Type")
        if args.feature_version >= 29 and trajectory.schema_version < 26:
            raise ValueError(f"{path}: feature version {args.feature_version} requires "
                             "schema v26 public face-up age")
        if verified_results is None:
            verification_started = perf_counter()
            count = verify_trajectory(trajectory, engine_type(args.native_root))
            audit_trajectory_visibility(trajectory)
            verification_seconds += perf_counter() - verification_started
        else:
            count, verified_digest = verified_results[trajectory_index]
            if hashlib.sha256(raw).hexdigest() != verified_digest:
                raise ValueError(f"{path}: trajectory changed after verification")
        annotation = None
        label_path = labels_by_path.get(path.resolve())
        disagreements = None
        if trajectory.source.startswith("edopro_"):
            raise ValueError(f"{path}: EDOPro reconstruction is not admitted for training")
        if teacher is not None:
            selected, disagreements = label_policy_trajectory(
                trajectory, teacher, teacher_parent_hash)
            disagreement_flags = teacher_disagreement_flags(trajectory, selected)
            if args.on_policy_teacher_activation_focus_only:
                selected, disagreements = filter_activation_opportunities(
                    trajectory, selected, args.focus_card)
                disagreement_flags = (False,) * len(selected)
        elif label_path is not None:
            annotation, selected = read_decision_annotations(
                label_path, hashlib.sha256(raw).hexdigest(), trajectory)
        else:
            selected = training_demonstrator_records(trajectory)
        corrections = 0
        if args.synthetic_thunder_search_correction:
            info = trajectory.skill_metadata or {}
            seat = info.get("demonstrator_seat")
            if (trajectory.source != "tactical"
                    or info.get("teacher") != "TacticalHeuristicAgent"
                    or type(info.get("teacher_version")) is not int
                    or info["teacher_version"] != 14
                    or type(seat) is not int or seat not in (0, 1)):
                raise ValueError(f"{path}: synthetic Thunder correction requires "
                                 "Tactical-v14 demonstrator provenance")
            selected, corrections = correct_staged_thunder_search(selected, seat)
            thunder_corrections += corrections
        if teacher is not None:
            source = f"automated_teacher_{args.on_policy_teacher}"
        elif annotation is not None:
            source = {"self_recorded": "human_annotation",
                      "scripted_scenario": "synthetic_annotation",
                      "policy_review": "policy_review_annotation",
                      "self_play_review": "self_play_review_annotation"}[annotation.authorization]
        else:
            source = ("synthetic_tactical_thunder_search"
                      if args.synthetic_thunder_search_correction else trajectory.source)
        records.extend(selected)
        record_sources.extend([source] * len(selected))
        record_disagreements.extend(
            disagreement_flags if teacher is not None else (False,) * len(selected))
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
                               "teacher_version": (TacticalHeuristicAgent.teacher_version
                                                   if teacher is not None else
                                                   (trajectory.skill_metadata or {}).get(
                                                       "teacher_version")),
                               "automated_teacher": args.on_policy_teacher,
                               "automated_teacher_disagreements": disagreements,
                               "opponent": (trajectory.skill_metadata or {}).get("opponent"),
                               "verified_decisions": count,
                               "selected_decisions": len(selected)})
        if args.synthetic_thunder_search_correction:
            training_games[-1]["synthetic_thunder_search_corrections"] = corrections
    vocabulary = CardVocabulary.from_goat_whitelist(
        args.native_root / "banlist/GOAT.lflist.conf",
        native_root=args.native_root if args.feature_version >= 22 else None)
    torch.manual_seed(args.seed)
    model = LegalActionPolicy(vocabulary.size, width=args.width,
                              feature_version=args.feature_version)
    parent = (load_parent_checkpoint(
        args.init_checkpoint, model, vocabulary,
        allow_v23_to_v24=args.upgrade_feature_23_to_24,
        allow_v23_to_v25=args.upgrade_feature_23_to_25,
        allow_v23_to_v26=args.upgrade_feature_23_to_26,
        allow_v23_to_v27=args.upgrade_feature_23_to_27,
        allow_v23_to_v28=args.upgrade_feature_23_to_28,
        allow_v23_to_v29=args.upgrade_feature_23_to_29,
        allow_v23_to_v30=args.upgrade_feature_23_to_30,
        allow_v23_to_v31=args.upgrade_feature_23_to_31)
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
    sampling_weights = decision_sampling_weights(
        records, record_sources, source_weights, focus_codes,
        args.focus_weight, label_kind_weights,
        record_disagreements, args.on_policy_disagreement_weight)
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
            trajectory = read_trajectory(path, fast_json=args.fast_trajectory_json)
            verify_trajectory(trajectory, engine_type(args.native_root))
            audit_trajectory_visibility(trajectory)
            candidates = [record for record in demonstrator_records(trajectory)
                          if len(record.legal_actions) > 1]
            if not candidates:
                raise ValueError(f"{path}: no multi-option preservation decisions")
            preservation.extend(rng.sample(candidates, min(
                args.preserve_per_trajectory, len(candidates))))
            preservation_hashes[str(path)] = digest
        fitting_started = perf_counter()
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
        fitting_started = perf_counter()
        losses = fit_behavioral_clone(model, vocabulary, records, epochs=args.epochs,
                                      learning_rate=args.learning_rate, seed=args.seed,
                                      batch_size=args.batch_size,
                                      batched_forward=args.batched_forward,
                                      sampling_weights=sampling_weights,
                                      skip_forced=args.skip_forced_training,
                                      omit_forced_forward=args.omit_forced_forward)
    fitting_seconds = perf_counter() - fitting_started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    inherited_sources = Counter(parent.get("source_decisions", {})) if parent else Counter()
    checkpoint = {
        "schema_version": 1, "model_state": model.state_dict(),
        "vocabulary_codes": vocabulary.codes,
        "vocabulary_card_properties": vocabulary.card_properties,
        "width": args.width,
        "feature_version": model.feature_version,
        "trajectory_sha256": inherited_hashes | trajectory_hashes,
        "source_decisions": dict(inherited_sources + sources),
        "new_source_decisions": dict(sources),
        "training_games": [*(parent["training_games"] if parent else ()),
                           *training_games],
        "new_training_games": len(training_games),
        **({"synthetic_thunder_search_corrections": thunder_corrections,
            "synthetic_thunder_search_rule": "take_offered_copy_v1"}
           if args.synthetic_thunder_search_correction else {}),
        "parent_checkpoint_sha256": (hashlib.sha256(
            args.init_checkpoint.read_bytes()).hexdigest()
            if args.init_checkpoint else None),
        "parent_feature_upgrade": ("v23_to_v31" if args.upgrade_feature_23_to_31
                                   else "v23_to_v30" if args.upgrade_feature_23_to_30
                                   else "v23_to_v29" if args.upgrade_feature_23_to_29
                                   else "v23_to_v28" if args.upgrade_feature_23_to_28
                                   else "v23_to_v27" if args.upgrade_feature_23_to_27
                                   else "v23_to_v26" if args.upgrade_feature_23_to_26
                                   else "v23_to_v25" if args.upgrade_feature_23_to_25
                                   else "v23_to_v24" if args.upgrade_feature_23_to_24
                                   else None),
        "seed": args.seed, "torch_version": str(torch.__version__),
        "batch_size": args.batch_size,
        "batched_forward": args.batched_forward,
        "fast_trajectory_json": args.fast_trajectory_json,
        "skip_forced_training": args.skip_forced_training,
        "omit_forced_forward": args.omit_forced_forward,
        "fit_decisions": (sum(len(record.legal_actions) > 1 for record in records)
                          if args.skip_forced_training and not preservation_metadata
                          else len(records)),
        "focus_cards": tuple(sorted(focus_codes)),
        "focus_weight": args.focus_weight,
        "on_policy_activation_focus_only": args.on_policy_teacher_activation_focus_only,
        "on_policy_disagreement_weight": args.on_policy_disagreement_weight,
        "on_policy_disagreements": sum(record_disagreements),
        "source_weights": source_weights,
        "label_kind_weights": label_kind_weights,
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
    summary["fit_decisions"] = checkpoint["fit_decisions"]
    if args.synthetic_thunder_search_correction:
        summary["synthetic_thunder_search_corrections"] = thunder_corrections
    if preservation_metadata:
        summary.update({"training_method": "parent_kl",
                        "final_labeled_loss": losses[-1],
                        "final_preservation_kl": preservation_losses[-1],
                        "preservation_states": len(preservation)})
    else:
        summary["epoch_loss"] = losses
    summary["run_wall_seconds"] = perf_counter() - started
    summary["verification_seconds"] = verification_seconds
    summary["fitting_seconds"] = fitting_seconds
    summary["verification_workers"] = args.verification_workers
    summary["batched_forward"] = args.batched_forward
    summary["fast_trajectory_json"] = args.fast_trajectory_json
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
