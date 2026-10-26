"""Improve a saved policy through native episodic policy-gradient self-play."""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import torch

from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.replay import write_trajectory
from goat_ai.training import load_policy_agent
from goat_ai.training.self_play import VisibleStateValue, train_against_snapshot_pool


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--output", type=Path, required=True)
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
    parser.add_argument("--snapshot-every", type=int, default=4)
    parser.add_argument("--max-snapshots", type=int, default=8)
    parser.add_argument("--entropy-coefficient", type=float, default=0.001)
    parser.add_argument("--policy-gradient-reduction", choices=("sum", "mean"),
                        default="sum", help="REINFORCE only: sum preserves earlier runs; mean normalizes by learner decisions")
    parser.add_argument("--parent-kl-weight", type=float, default=0.0,
                        help="penalize divergence from the frozen starting policy on learner decisions")
    parser.add_argument("--policy-update", choices=("reinforce", "clipped_ppo"),
                        default="reinforce",
                        help="clipped_ppo reuses each on-policy duel for minibatch updates")
    parser.add_argument("--ppo-epochs", type=int, default=2)
    parser.add_argument("--ppo-batch-size", type=int, default=16)
    parser.add_argument("--ppo-clip-epsilon", type=float, default=0.2)
    parser.add_argument("--learner-temperature", type=float, default=1.0,
                        help="softmax temperature for learner sampling and its policy update")
    parser.add_argument("--baseline-scope", choices=("global", "learner_deck", "state_value"),
                        default="global",
                        help="moving global/per-deck return or experimental visible-state critic")
    parser.add_argument("--value-width", type=int, default=32,
                        help="hidden width of experimental visible-state critic")
    parser.add_argument("--value-learning-rate", type=float, default=1e-3)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--skip-capped-games", action="store_true",
                        help="record over-cap duels as censored; exclude them from updates and provenance")
    parser.add_argument("--skip-unsupported-games", action="store_true",
                        help="record native protocol gaps; exclude those games from updates and provenance")
    parser.add_argument("--record-dir", type=Path,
                        help="optional ignored directory for exact self-play trajectories")
    args = parser.parse_args()
    if (args.games < 1 or args.learning_rate <= 0 or args.snapshot_every < 1
            or args.max_snapshots < 1 or args.max_decisions < 1
            or args.entropy_coefficient < 0
            or not 0 <= args.parent_kl_weight < float("inf")
            or args.learner_temperature <= 0
            or args.value_width < 1 or args.value_learning_rate <= 0
            or args.ppo_epochs < 1 or args.ppo_batch_size < 1
            or not 0 < args.ppo_clip_epsilon < 1
            or not 0 <= args.historical_probability <= 1):
        parser.error("invalid training schedule or hyperparameters")
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
    agent = load_policy_agent(args.checkpoint)
    value_model = None
    if args.baseline_scope == "state_value":
        torch.manual_seed(args.seed)
        number_width = agent.model.state_numbers[0].in_features
        value_model = VisibleStateValue(agent.vocabulary.size, number_width,
                                        width=args.value_width)
        if "value_model_state" in parent:
            if (parent.get("value_model_width") != args.value_width
                    or parent.get("value_state_number_width") != number_width):
                parser.error("parent critic architecture differs from requested value model")
            value_model.load_state_dict(parent["value_model_state"], strict=True)
    fixtures = Path(__file__).resolve().parent.parent / "examples/decks"
    matchups = args.matchup or [[str(fixtures / "vanilla_probe.ydk"),
                                  str(fixtures / "vanilla_reverse.ydk")]]
    if args.schedule_mode == "four_roles" and args.games % (4 * len(matchups)):
        parser.error("four_roles requires a whole four-role cycle for every matchup")
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    parent_checkpoint_sha256 = sha256(args.checkpoint)

    def record(index, episode):
        if args.record_dir is not None:
            args.record_dir.mkdir(parents=True, exist_ok=True)
            trajectory = replace(
                episode.trajectory,
                skill_metadata={
                    **(episode.trajectory.skill_metadata or {}),
                    "parent_checkpoint_sha256": parent_checkpoint_sha256,
                    "self_play_episode_index": index,
                    "learner_temperature": args.learner_temperature,
                    "learner_action_selection": "sampled_softmax",
                },
            )
            write_trajectory(args.record_dir / f"episode_{index:05d}_seed_{episode.seed}.json",
                             trajectory)

    reports = train_against_snapshot_pool(
        agent.model, agent.vocabulary, matchups, seeds,
        lambda: engine_type(args.native_root),
        learning_rate=args.learning_rate,
        historical_probability=args.historical_probability,
        snapshot_every=args.snapshot_every, max_snapshots=args.max_snapshots,
        entropy_coefficient=args.entropy_coefficient,
        learner_temperature=args.learner_temperature,
        baseline_scope=args.baseline_scope,
        policy_gradient_reduction=args.policy_gradient_reduction,
        parent_kl_weight=args.parent_kl_weight,
        policy_update=args.policy_update,
        ppo_epochs=args.ppo_epochs,
        ppo_batch_size=args.ppo_batch_size,
        ppo_clip_epsilon=args.ppo_clip_epsilon,
        schedule_mode=args.schedule_mode,
        value_model=value_model,
        value_learning_rate=args.value_learning_rate,
        max_decisions=args.max_decisions, random_seed=args.seed,
        skip_capped_games=args.skip_capped_games,
        skip_unsupported_games=args.skip_unsupported_games,
        record_episode=record,
    )
    terminal_reports = [report for report in reports if report["status"] == "terminal"]
    if not terminal_reports:
        parser.error("no terminal self-play games; checkpoint was not written")
    training_games = list(previous)
    for report in terminal_reports:
        training_games.append({
            "seed": report["seed"],
            "deck_sha256": report["deck_sha256"],
            "main_deck_composition_sha256": tuple(
                main_deck_composition_sha256(read_ydk(deck))
                for deck in report["decks"]),
            "asset_sha256": report["asset_sha256"],
            "rules_profile": report["rules_profile"],
            "source": "self_play_rl", "opponent": report["opponent"],
        })
    config = {"engine": args.engine, "learning_rate": args.learning_rate,
              "historical_probability": args.historical_probability,
              "snapshot_every": args.snapshot_every, "max_snapshots": args.max_snapshots,
              "entropy_coefficient": args.entropy_coefficient,
              "learner_temperature": args.learner_temperature,
              "baseline_scope": args.baseline_scope,
              "policy_gradient_reduction": args.policy_gradient_reduction,
              "parent_kl_weight": args.parent_kl_weight,
              "policy_update": args.policy_update,
              "ppo_epochs": args.ppo_epochs if args.policy_update == "clipped_ppo" else None,
              "ppo_batch_size": (args.ppo_batch_size
                                 if args.policy_update == "clipped_ppo" else None),
              "ppo_clip_epsilon": (args.ppo_clip_epsilon
                                   if args.policy_update == "clipped_ppo" else None),
              "value_width": args.value_width if value_model is not None else None,
              "value_learning_rate": (args.value_learning_rate
                                      if value_model is not None else None),
              "schedule_mode": args.schedule_mode,
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
        "trajectory_sha256": parent.get("trajectory_sha256", {}),
        "source_decisions": source_decisions,
        "self_play_config": config, "self_play_reports": reports,
        "torch_version": str(torch.__version__),
    }
    if value_model is not None:
        checkpoint["value_model_state"] = value_model.state_dict()
        checkpoint["value_model_width"] = args.value_width
        checkpoint["value_state_number_width"] = agent.model.state_numbers[0].in_features
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
