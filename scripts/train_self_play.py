"""Improve a saved policy through native episodic policy-gradient self-play."""

import argparse
import hashlib
import json
from pathlib import Path

import torch

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.replay import write_trajectory
from goat_ai.training import load_policy_agent
from goat_ai.training.self_play import train_against_snapshot_pool


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"), default="restricted")
    parser.add_argument("--matchup", nargs=2, action="append", metavar=("DECK_A", "DECK_B"))
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--games", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--historical-probability", type=float, default=0.75)
    parser.add_argument("--snapshot-every", type=int, default=4)
    parser.add_argument("--max-snapshots", type=int, default=8)
    parser.add_argument("--entropy-coefficient", type=float, default=0.001)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--record-dir", type=Path,
                        help="optional ignored directory for exact self-play trajectories")
    args = parser.parse_args()
    if (args.games < 1 or args.learning_rate <= 0 or args.snapshot_every < 1
            or args.max_snapshots < 1 or args.max_decisions < 1
            or args.entropy_coefficient < 0
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
    fixtures = Path(__file__).resolve().parent.parent / "examples/decks"
    matchups = args.matchup or [[str(fixtures / "vanilla_probe.ydk"),
                                  str(fixtures / "vanilla_reverse.ydk")]]
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)

    def record(index, episode):
        if args.record_dir is not None:
            args.record_dir.mkdir(parents=True, exist_ok=True)
            write_trajectory(args.record_dir / f"episode_{index:05d}_seed_{episode.seed}.json",
                             episode.trajectory)

    reports = train_against_snapshot_pool(
        agent.model, agent.vocabulary, matchups, seeds,
        lambda: engine_type(args.native_root),
        learning_rate=args.learning_rate,
        historical_probability=args.historical_probability,
        snapshot_every=args.snapshot_every, max_snapshots=args.max_snapshots,
        entropy_coefficient=args.entropy_coefficient,
        max_decisions=args.max_decisions, random_seed=args.seed,
        record_episode=record,
    )
    training_games = list(previous)
    for report in reports:
        training_games.append({
            "seed": report["seed"],
            "deck_sha256": report["deck_sha256"],
            "asset_sha256": report["asset_sha256"],
            "rules_profile": report["rules_profile"],
            "source": "self_play_rl", "opponent": report["opponent"],
        })
    config = {"engine": args.engine, "learning_rate": args.learning_rate,
              "historical_probability": args.historical_probability,
              "snapshot_every": args.snapshot_every, "max_snapshots": args.max_snapshots,
              "entropy_coefficient": args.entropy_coefficient,
              "max_decisions": args.max_decisions, "seed": args.seed}
    source_decisions = dict(parent.get("source_decisions", {}))
    source_decisions["self_play_rl"] = (source_decisions.get("self_play_rl", 0)
                                        + sum(report["learner_decisions"] for report in reports))
    checkpoint = {
        "schema_version": 1, "model_state": agent.model.state_dict(),
        "vocabulary_codes": agent.vocabulary.codes,
        "width": agent.model.card.embedding_dim,
        "feature_version": agent.model.feature_version,
        "parent_checkpoint_sha256": sha256(args.checkpoint),
        "training_games": training_games,
        "trajectory_sha256": parent.get("trajectory_sha256", {}),
        "source_decisions": source_decisions,
        "self_play_config": config, "self_play_reports": reports,
        "torch_version": str(torch.__version__),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, args.output)
    wins = sum(report["reward"] > 0 for report in reports)
    losses = sum(report["reward"] < 0 for report in reports)
    print(json.dumps({"output": str(args.output), "games": len(reports),
                      "wins": wins, "losses": losses,
                      "draws": len(reports) - wins - losses,
                      "learner_decisions": sum(report["learner_decisions"] for report in reports),
                      "reports": reports}, indent=2))


if __name__ == "__main__":
    main()
