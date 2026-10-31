"""Improve a saved policy through native episodic policy-gradient self-play."""

import argparse
import hashlib
import json
from dataclasses import replace
from functools import partial
from math import isfinite
from pathlib import Path
from time import perf_counter

import torch

from goat_ai.agents import RandomAgent, load_card_facts, load_card_races, load_flip_monster_codes
from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import (
    read_decision_preferences,
    read_trajectory,
    verify_trajectory,
    write_trajectory,
)
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import LegalActionPolicy, PolicyAgent, load_policy_agent
from goat_ai.training.resource_value import load_frozen_resource_ridge
from goat_ai.training.self_play import (
    VisibleStateValue,
    make_tactical_opponent,
    prepare_preference_anchors,
    train_against_snapshot_pool,
)
from scripts.derive_visible_rule_preferences import validate_automated_preferences
from scripts.train_behavioral_clone import load_parent_checkpoint


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replay_directory(output: Path, requested: Path | None) -> Path:
    """Give every checkpoint a separate, initially empty replay directory."""
    directory = requested or output.with_name(output.stem + "_replays")
    if (directory.resolve() == output.resolve()
            or directory.exists() and (not directory.is_dir()
                                           or any(directory.iterdir()))):
        raise ValueError("self-play replay directory must be empty and distinct from output")
    return directory


def load_training_agent(checkpoint: Path, *, upgrade_feature_23_to_32: bool = False
                        ) -> PolicyAgent:
    """Warm-start an experimental feature-v32 PPO policy from selected v23."""
    agent = load_policy_agent(checkpoint)
    if not upgrade_feature_23_to_32:
        return agent
    if agent.model.feature_version != 23:
        raise ValueError("feature-v32 self-play upgrade requires a v23 checkpoint")
    model = LegalActionPolicy(agent.vocabulary.size,
                              width=agent.model.card.embedding_dim,
                              feature_version=32)
    load_parent_checkpoint(checkpoint, model, agent.vocabulary,
                           allow_v23_to_v32=True)
    return PolicyAgent(model.eval(), agent.vocabulary)


def checked_replay_hashes(terminal_reports: list[dict],
                          recorded_games: dict[int, tuple[str, str]],
                          previous_hashes: dict[str, str]) -> dict[str, str]:
    """Bind each completed training game to unchanged, unique replay bytes."""
    if set(recorded_games) != {report["seed"] for report in terminal_reports}:
        raise ValueError("recorded self-play games differ from terminal training games")
    if any(sha256_file(path) != digest for path, digest in recorded_games.values()):
        raise ValueError("recorded self-play trajectory changed during training")
    new_hashes = dict(recorded_games.values())
    if len(new_hashes) != len(recorded_games) or set(new_hashes) & set(previous_hashes):
        raise ValueError("self-play replay path overlaps training provenance")
    return new_hashes


def load_retained_preferences(manifest_path: Path, parent: dict,
                              native_root: Path) -> list:
    """Revalidate only preferences already present in the starting checkpoint."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("rule_set_id") not in (
            "visible_selected_own_loss_v10",
            "visible_selected_own_loss_with_responses_v11")
            or manifest.get("labels_are_human_reviewed") is not False
            or not isinstance(manifest.get("replays"), list)
            or not manifest["replays"]):
        raise ValueError("retention requires a nonempty V10/V11 automated-rule manifest")
    old_replays = parent.get("trajectory_sha256", {})
    old_preferences = parent.get("preference_sha256", {})
    if not isinstance(old_replays, dict) or not isinstance(old_preferences, dict):
        raise TypeError("starting checkpoint lacks preference provenance")
    facts = load_card_facts(native_root)
    seen = set()
    reviewed = []
    for row in manifest["replays"]:
        if not isinstance(row, dict):
            raise TypeError("invalid retention manifest row")
        replay_path = Path(row["replay"])
        preference_path = Path(row["output"])
        pair = (str(replay_path), str(preference_path))
        replay_hash = sha256_file(replay_path)
        preference_hash = sha256_file(preference_path)
        if (pair in seen or old_replays.get(str(replay_path)) != replay_hash
                or old_preferences.get(str(preference_path)) != preference_hash
                or row.get("replay_sha256") != replay_hash
                or row.get("output_sha256") != preference_hash):
            raise ValueError("retained preference differs from parent provenance")
        seen.add(pair)
        trajectory = read_trajectory(replay_path)
        verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
        audit_trajectory_visibility(trajectory)
        preference = read_decision_preferences(preference_path, replay_hash, trajectory)
        validate_automated_preferences(trajectory, preference, {}, facts)
        reviewed.extend((trajectory.decisions[item.decision_index], item)
                        for item in preference.preferences)
    return reviewed


def main() -> None:
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--upgrade-feature-23-to-32", action="store_true",
                        help="zero-extend a v23 checkpoint for opt-in v32 self-play")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"), default="restricted")
    parser.add_argument("--matchup", nargs=2, action="append", metavar=("DECK_A", "DECK_B"))
    parser.add_argument("--schedule-mode", choices=("paired_seats", "four_roles"),
                        default="paired_seats",
                        help="four_roles trains both decks in both seats per pairing")
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--games", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--historical-probability", type=float, default=0.75)
    parser.add_argument("--independent-opponent-rng", action="store_true",
                        help="give a frozen policy opponent a separate deterministic sampling stream")
    parser.add_argument("--baseline-opponent", choices=("random", "tactical"),
                        default="random",
                        help="opponent when a frozen snapshot is not sampled")
    parser.add_argument("--snapshot-every", type=int, default=4)
    parser.add_argument("--max-snapshots", type=int, default=8)
    parser.add_argument("--entropy-coefficient", type=float, default=0.001)
    parser.add_argument("--policy-gradient-reduction", choices=("sum", "mean"),
                        default="sum", help="REINFORCE only: sum preserves earlier runs; mean normalizes by learner decisions")
    parser.add_argument("--reinforce-batch-size", type=int, default=1,
                        help="REINFORCE only: batch visible decisions for fewer forward/backward calls")
    parser.add_argument("--parent-kl-weight", type=float, default=0.0,
                        help="penalize divergence from the frozen starting policy on learner decisions")
    parser.add_argument("--retain-preferences-manifest", type=Path,
                        help="revalidate starting-checkpoint V10/V11 preferences as PPO anchors")
    parser.add_argument("--retain-preference-weight", type=float, default=0.0)
    parser.add_argument("--retain-preference-batch-size", type=int, default=8)
    parser.add_argument("--policy-update", choices=("reinforce", "clipped_ppo"),
                        default="reinforce",
                        help="clipped_ppo reuses each on-policy duel for minibatch updates")
    parser.add_argument("--ppo-epochs", type=int, default=2)
    parser.add_argument("--ppo-batch-size", type=int, default=16)
    parser.add_argument("--ppo-clip-epsilon", type=float, default=0.2)
    parser.add_argument("--ppo-rollout-games", type=int, default=1,
                        help="collect this many terminal duels under one frozen policy before PPO updates")
    parser.add_argument("--rollout-workers", type=int, default=0,
                        help="opt-in independent CPU processes per frozen PPO rollout; 0 preserves prior sampling")
    parser.add_argument("--rollout-batch-inference", action="store_true",
                        help="opt-in single-process native PPO duels with batched learner inference")
    parser.add_argument("--trace-rollout-inference", action="store_true",
                        help="opt-in TorchScript tracing of each frozen v23 learner rollout")
    parser.add_argument("--reuse-rollout-features", action="store_true",
                        help="opt-in single-process PPO reuse of learner features during the update")
    parser.add_argument("--ppo-rollout-weighting", choices=("per_decision", "per_episode"),
                        default="per_decision",
                        help="per_episode equalizes total decision weight across rollout duels")
    parser.add_argument("--ppo-normalize-advantages", action="store_true",
                        help="opt-in weighted centering and scaling of each PPO rollout's advantages")
    parser.add_argument("--ppo-baseline-timing",
                        choices=("online", "frozen_rollout", "leave_one_out"),
                        default="online",
                        help="frozen_rollout uses a pre-rollout estimate; leave_one_out "
                             "uses other terminal duels of the same learner deck in that rollout")
    parser.add_argument("--ppo-gae-lambda", type=float,
                        help="optional undiscounted terminal GAE from a frozen visible-resource ridge")
    parser.add_argument("--ppo-material-potential", type=float, default=0.0,
                        help="experimental visible hand/field material potential (0 to 1); "
                             "requires --ppo-gae-lambda and held-out evaluation")
    parser.add_argument("--learner-temperature", type=float, default=1.0,
                        help="softmax temperature for learner sampling and its policy update")
    parser.add_argument("--learner-own-loss-guard", action="store_true",
                        help="sample and update clipped PPO under the deployed visible own-loss guard v1")
    parser.add_argument("--baseline-scope", choices=("global", "learner_deck", "state_value",
                                                     "resource_ridge"),
                        default="global",
                        help="moving return, online critic, or frozen visible-resource ridge")
    parser.add_argument("--resource-ridge-artifact", type=Path,
                        help="verified frozen mirror regression artifact for resource_ridge")
    parser.add_argument("--value-width", type=int, default=32,
                        help="hidden width of experimental visible-state critic")
    parser.add_argument("--value-architecture", choices=("v1", "v2"), default="v1",
                        help="v2 separates visible player zones and adds public card stats")
    parser.add_argument("--value-learning-rate", type=float, default=1e-3)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--skip-capped-games", action="store_true",
                        help="record over-cap duels as censored; exclude them from updates and provenance")
    parser.add_argument("--skip-unsupported-games", action="store_true",
                        help="record native protocol gaps; exclude those games from updates and provenance")
    parser.add_argument("--record-dir", type=Path,
                        help="directory for exact self-play trajectories; defaults beside the checkpoint")
    trajectory_json = parser.add_mutually_exclusive_group()
    trajectory_json.add_argument("--fast-trajectory-json", action="store_true",
                                 help="require optional orjson for replay writing; install .[speed]")
    trajectory_json.add_argument("--standard-trajectory-json", action="store_true",
                                 help="force the standard JSON writer for comparisons")
    args = parser.parse_args()
    if args.standard_trajectory_json:
        fast_trajectory_json = False
    elif args.fast_trajectory_json:
        fast_trajectory_json = True
    else:
        try:
            import orjson  # noqa: F401
        except ImportError:
            fast_trajectory_json = False
        else:
            fast_trajectory_json = True
    if (args.games < 1 or args.learning_rate <= 0 or args.snapshot_every < 1
            or args.max_snapshots < 1 or args.max_decisions < 1
            or args.entropy_coefficient < 0
            or not 0 <= args.parent_kl_weight < float("inf")
            or not isfinite(args.retain_preference_weight)
            or args.retain_preference_weight < 0
            or args.retain_preference_batch_size < 1
            or (args.retain_preferences_manifest is None)
            != (args.retain_preference_weight == 0)
            or args.retain_preference_weight > 0
            and args.policy_update != "clipped_ppo"
            or args.learner_temperature <= 0
            or args.value_width < 1 or args.value_learning_rate <= 0
            or args.reinforce_batch_size < 1
            or args.ppo_epochs < 1 or args.ppo_batch_size < 1
            or args.ppo_rollout_games < 1
            or args.rollout_workers < 0
            or not 0 < args.ppo_clip_epsilon < 1
            or not 0 <= args.historical_probability <= 1):
        parser.error("invalid training schedule or hyperparameters")
    if (args.baseline_scope == "resource_ridge") != bool(args.resource_ridge_artifact):
        parser.error("resource_ridge baseline requires --resource-ridge-artifact")
    if args.ppo_normalize_advantages and args.policy_update != "clipped_ppo":
        parser.error("advantage normalization requires clipped PPO")
    if args.learner_own_loss_guard and args.policy_update != "clipped_ppo":
        parser.error("learner own-loss guard requires clipped PPO")
    if args.ppo_gae_lambda is not None and (
            args.policy_update != "clipped_ppo"
            or args.baseline_scope != "resource_ridge"
            or args.ppo_baseline_timing == "leave_one_out"
            or not 0 <= args.ppo_gae_lambda <= 1):
        parser.error("--ppo-gae-lambda requires clipped PPO, a frozen resource "
                     "ridge, online/frozen rollout timing, and lambda in [0, 1]")
    if (not 0 <= args.ppo_material_potential <= 1
            or args.ppo_material_potential > 0 and args.ppo_gae_lambda is None):
        parser.error("--ppo-material-potential requires --ppo-gae-lambda and a weight in [0, 1]")
    parent = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(parent, dict) or parent.get("schema_version") != 1:
        parser.error("unsupported parent checkpoint schema")
    previous = parent.get("training_games")
    if not isinstance(previous, list):
        parser.error("parent checkpoint lacks training-game provenance")
    seeds = list(range(args.seed, args.seed + args.games))
    overlap = {game["seed"] for game in previous}.intersection(seeds)
    if overlap:
        parser.error(f"self-play seeds overlap existing training seeds: {sorted(overlap)}")
    try:
        record_dir = replay_directory(args.output, args.record_dir)
    except ValueError as exc:
        parser.error(str(exc))
    agent = load_training_agent(args.checkpoint,
                                upgrade_feature_23_to_32=args.upgrade_feature_23_to_32)
    retained = (load_retained_preferences(args.retain_preferences_manifest,
                                          parent, args.native_root)
                if args.retain_preferences_manifest else [])
    preference_anchors = (prepare_preference_anchors(
        agent.model, agent.vocabulary, retained) if retained else ())
    value_model = None
    resource_value_model = None
    resource_artifact = None
    if args.resource_ridge_artifact:
        resource_value_model, resource_artifact = load_frozen_resource_ridge(
            args.resource_ridge_artifact, sha256(args.checkpoint),
            agent.model.feature_version)
    if args.baseline_scope == "state_value":
        torch.manual_seed(args.seed)
        number_width = agent.model.state_numbers[0].in_features
        value_model = VisibleStateValue(agent.vocabulary.size, number_width,
                                        width=args.value_width,
                                        architecture=args.value_architecture,
                                        card_number_width=(6 if agent.model.feature_version >= 29
                                                           else 5))
        if "value_model_state" in parent:
            if (parent.get("value_model_width") != args.value_width
                    or parent.get("value_state_number_width") != number_width
                    or parent.get("value_model_architecture", "v1")
                    != args.value_architecture):
                parser.error("parent critic architecture differs from requested value model")
            value_model.load_state_dict(parent["value_model_state"], strict=True)
    fixtures = Path(__file__).resolve().parent.parent / "examples/decks"
    matchups = args.matchup or [[str(fixtures / "vanilla_probe.ydk"),
                                  str(fixtures / "vanilla_reverse.ydk")]]
    if args.schedule_mode == "four_roles" and args.games % (4 * len(matchups)):
        parser.error("four_roles requires a whole four-role cycle for every matchup")
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    baseline_factory = (partial(
        make_tactical_opponent,
        flip_codes=load_flip_monster_codes(args.native_root),
        card_races=load_card_races(args.native_root),
        card_facts=load_card_facts(args.native_root))
        if args.baseline_opponent == "tactical" else None)
    parent_checkpoint_sha256 = sha256(args.checkpoint)
    recorded_games: dict[int, tuple[str, str]] = {}

    def record(index, episode):
        record_dir.mkdir(parents=True, exist_ok=True)
        trajectory = replace(
            episode.trajectory,
            skill_metadata={
                **(episode.trajectory.skill_metadata or {}),
                "parent_checkpoint_sha256": parent_checkpoint_sha256,
                "self_play_episode_index": index,
                "learner_temperature": args.learner_temperature,
                "learner_action_selection": (
                    "sampled_softmax_visible_own_loss_guard_v1"
                    if args.learner_own_loss_guard else "sampled_softmax"),
                "learner_own_loss_guard_version": (
                    1 if args.learner_own_loss_guard else None),
                "selection_progress_mask": 1,
                "independent_opponent_rng": args.independent_opponent_rng,
            },
        )
        path = record_dir / f"episode_{index:05d}_seed_{episode.seed}.json"
        write_trajectory(path, trajectory, fast_json=fast_trajectory_json)
        recorded_games[episode.seed] = (str(path), sha256_file(path))

    reports = train_against_snapshot_pool(
        agent.model, agent.vocabulary, matchups, seeds,
        partial(engine_type, args.native_root),
        learning_rate=args.learning_rate,
        historical_probability=args.historical_probability,
        snapshot_every=args.snapshot_every, max_snapshots=args.max_snapshots,
        entropy_coefficient=args.entropy_coefficient,
        learner_temperature=args.learner_temperature,
        learner_own_loss_guard=args.learner_own_loss_guard,
        baseline_scope=args.baseline_scope,
        policy_gradient_reduction=args.policy_gradient_reduction,
        reinforce_batch_size=args.reinforce_batch_size,
        parent_kl_weight=args.parent_kl_weight,
        preference_anchors=preference_anchors,
        preference_weight=args.retain_preference_weight,
        preference_batch_size=args.retain_preference_batch_size,
        policy_update=args.policy_update,
        ppo_epochs=args.ppo_epochs,
        ppo_batch_size=args.ppo_batch_size,
        ppo_clip_epsilon=args.ppo_clip_epsilon,
        ppo_rollout_games=args.ppo_rollout_games,
        rollout_workers=args.rollout_workers,
        rollout_batch_inference=args.rollout_batch_inference,
        trace_rollout_inference=args.trace_rollout_inference,
        reuse_rollout_features=args.reuse_rollout_features,
        ppo_rollout_weighting=args.ppo_rollout_weighting,
        ppo_normalize_advantages=args.ppo_normalize_advantages,
        ppo_baseline_timing=args.ppo_baseline_timing,
        ppo_gae_lambda=args.ppo_gae_lambda,
        ppo_material_potential=args.ppo_material_potential,
        ppo_material_card_facts=(load_card_facts(args.native_root)
                                 if args.ppo_material_potential else None),
        schedule_mode=args.schedule_mode,
        value_model=value_model,
        resource_value_model=resource_value_model,
        value_learning_rate=args.value_learning_rate,
        max_decisions=args.max_decisions, random_seed=args.seed,
        skip_capped_games=args.skip_capped_games,
        skip_unsupported_games=args.skip_unsupported_games,
        baseline_opponent_factory=baseline_factory or RandomAgent,
        baseline_opponent_name=("tactical_v14" if baseline_factory else "random"),
        independent_opponent_rng=args.independent_opponent_rng,
        record_episode=record,
    )
    terminal_reports = [report for report in reports if report["status"] == "terminal"]
    if not terminal_reports:
        parser.error("no terminal self-play games; checkpoint was not written")
    previous_hashes = parent.get("trajectory_sha256", {})
    if not isinstance(previous_hashes, dict):
        parser.error("parent checkpoint has invalid trajectory hashes")
    new_hashes = checked_replay_hashes(terminal_reports, recorded_games,
                                      previous_hashes)
    training_games = list(previous)
    for report in terminal_reports:
        trajectory_path, trajectory_digest = recorded_games[report["seed"]]
        training_games.append({
            "seed": report["seed"],
            "deck_sha256": report["deck_sha256"],
            "main_deck_composition_sha256": tuple(
                main_deck_composition_sha256(read_ydk(deck))
                for deck in report["decks"]),
            "asset_sha256": report["asset_sha256"],
            "rules_profile": report["rules_profile"],
            "source": "self_play_rl", "opponent": report["opponent"],
            "trajectory": trajectory_path,
            "trajectory_sha256": trajectory_digest,
        })
    config = {"engine": args.engine, "learning_rate": args.learning_rate,
              "historical_probability": args.historical_probability,
              "independent_opponent_rng": args.independent_opponent_rng,
              "baseline_opponent": args.baseline_opponent,
              "snapshot_every": args.snapshot_every, "max_snapshots": args.max_snapshots,
              "entropy_coefficient": args.entropy_coefficient,
              "learner_temperature": args.learner_temperature,
              "learner_own_loss_guard_version": (
                  1 if args.learner_own_loss_guard else None),
              "selection_progress_mask": 1,
              "baseline_scope": args.baseline_scope,
              "policy_gradient_reduction": args.policy_gradient_reduction,
              "reinforce_batch_size": (args.reinforce_batch_size
                                       if args.policy_update == "reinforce" else None),
              "parent_kl_weight": args.parent_kl_weight,
              "retain_preferences_manifest_sha256": (
                  sha256_file(args.retain_preferences_manifest)
                  if args.retain_preferences_manifest else None),
              "retain_preference_weight": args.retain_preference_weight,
              "retain_preference_batch_size": (
                  args.retain_preference_batch_size if preference_anchors else None),
              "retained_preference_decisions": len(preference_anchors),
              "policy_update": args.policy_update,
              "ppo_epochs": args.ppo_epochs if args.policy_update == "clipped_ppo" else None,
              "ppo_batch_size": (args.ppo_batch_size
                                 if args.policy_update == "clipped_ppo" else None),
              "ppo_clip_epsilon": (args.ppo_clip_epsilon
                                   if args.policy_update == "clipped_ppo" else None),
              "ppo_rollout_games": (args.ppo_rollout_games
                                    if args.policy_update == "clipped_ppo" else None),
              "rollout_workers": args.rollout_workers,
              "parent_feature_upgrade": ("v23_to_v32"
                                         if args.upgrade_feature_23_to_32 else None),
              "rollout_batch_inference": args.rollout_batch_inference,
              "trace_rollout_inference": args.trace_rollout_inference,
              "reuse_rollout_features": args.reuse_rollout_features,
              "ppo_rollout_weighting": (args.ppo_rollout_weighting
                                        if args.policy_update == "clipped_ppo" else None),
              "ppo_normalize_advantages": args.ppo_normalize_advantages,
              "ppo_baseline_timing": (args.ppo_baseline_timing
                                      if args.policy_update == "clipped_ppo" else None),
              "ppo_gae_lambda": args.ppo_gae_lambda,
              "ppo_material_potential": args.ppo_material_potential,
              "ppo_gae_gamma": 1.0 if args.ppo_gae_lambda is not None else None,
              "baseline_accumulation": "all_terminal_rewards_v2",
              "value_width": args.value_width if value_model is not None else None,
              "value_architecture": (args.value_architecture
                                     if value_model is not None else None),
              "value_learning_rate": (args.value_learning_rate
                                      if value_model is not None else None),
              "resource_ridge_artifact_sha256": (sha256(args.resource_ridge_artifact)
                                                  if resource_artifact is not None else None),
              "schedule_mode": args.schedule_mode,
              "record_dir": str(record_dir),
              "max_decisions": args.max_decisions, "seed": args.seed,
              "skip_capped_games": args.skip_capped_games}
    config["skip_unsupported_games"] = args.skip_unsupported_games
    source_decisions = dict(parent.get("source_decisions", {}))
    source_decisions["self_play_rl"] = (source_decisions.get("self_play_rl", 0)
                                        + sum(report["learner_decisions"] for report in reports))
    checkpoint = {
        "schema_version": 1, "model_state": agent.model.state_dict(),
        "vocabulary_codes": agent.vocabulary.codes,
        "vocabulary_card_properties": agent.vocabulary.card_properties,
        "width": agent.model.card.embedding_dim,
        "feature_version": agent.model.feature_version,
        "parent_checkpoint_sha256": parent_checkpoint_sha256,
        "training_games": training_games,
        "trajectory_sha256": previous_hashes | new_hashes,
        "source_decisions": source_decisions,
        "self_play_config": config, "self_play_reports": reports,
        "torch_version": str(torch.__version__),
    }
    if preference_anchors:
        # Future rounds must be able to revalidate the retained labels against
        # the exact files admitted by this checkpoint's parent.
        checkpoint["preference_sha256"] = dict(parent["preference_sha256"])
    if value_model is not None:
        checkpoint["value_model_state"] = value_model.state_dict()
        checkpoint["value_model_width"] = args.value_width
        checkpoint["value_model_architecture"] = args.value_architecture
        checkpoint["value_state_number_width"] = agent.model.state_numbers[0].in_features
    if resource_artifact is not None:
        checkpoint["resource_ridge_artifact"] = resource_artifact
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, args.output)
    wins = sum(report["reward"] > 0 for report in terminal_reports)
    losses = sum(report["reward"] < 0 for report in terminal_reports)
    print(json.dumps({"output": str(args.output), "games": len(terminal_reports),
                      "scheduled_games": len(reports),
                      "censored_games": len(reports) - len(terminal_reports),
                      "unsupported_games": sum(report["status"] == "simulator_unavailable"
                                               for report in reports),
                      "decision_limit_games": sum(report["status"] == "decision_limit"
                                                  for report in reports),
                      "wins": wins, "losses": losses,
                      "draws": len(terminal_reports) - wins - losses,
                      "learner_decisions": sum(report["learner_decisions"]
                                               for report in terminal_reports),
                      "run_wall_seconds": perf_counter() - started,
                      "reports": reports}, indent=2))


if __name__ == "__main__":
    main()
