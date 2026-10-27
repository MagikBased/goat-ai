"""Compare player-visible critic architectures on held-out native duels."""

import argparse
import json
import random
from pathlib import Path
from time import perf_counter

import torch

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.self_play import (
    VisibleStateValue,
    predict_state_values,
    state_value_update,
)


def selected_records(trajectory, limit: int, source: str = "self_play_rl"):
    seat_key = "learner_seat" if source == "self_play_rl" else "demonstrator_seat"
    seat = (trajectory.skill_metadata or {}).get(seat_key)
    if (trajectory.source != source or type(seat) is not int
            or seat not in (0, 1)):
        raise ValueError(f"critic comparison needs {source} replays with {seat_key}")
    records = [record for record in trajectory.decisions
               if record.observation.acting_player == seat
               and len(record.legal_actions) > 1]
    if not records:
        raise ValueError("duel has no selected-seat decisions with alternatives")
    if len(records) > limit:
        indices = ([len(records) // 2] if limit == 1 else
                   [index * (len(records) - 1) // (limit - 1)
                    for index in range(limit)])
        records = [records[index] for index in indices]
    reward = 0.0 if trajectory.winner is None else (
        1.0 if trajectory.winner == seat else -1.0)
    return tuple(records), reward


def game_mse(model, games, vocabulary, feature_version):
    losses = []
    for records, target in games:
        predictions = predict_state_values(model, vocabulary, records, feature_version)
        losses.append(sum((value - target) ** 2 for value in predictions)
                      / len(predictions))
    return tuple(losses)


def paired_difference_interval(first, second, seed: int):
    """Percentile interval for the first minus second per-game MSE."""
    if len(first) != len(second) or not first:
        raise ValueError("paired MSE needs equal nonempty game sets")
    rng = random.Random(seed)
    differences = [a - b for a, b in zip(first, second, strict=True)]
    samples = sorted(sum(differences[rng.randrange(len(differences))]
                         for _ in differences) / len(differences)
                     for _ in range(5000))
    return (samples[125], samples[4875])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path,
                        help="policy checkpoint supplies the pinned vocabulary and feature version")
    parser.add_argument("replay_dir", type=Path)
    parser.add_argument("--corpus-source", choices=("self_play_rl", "policy_evaluation"),
                        default="self_play_rl")
    parser.add_argument("--independent-replay-dir", type=Path,
                        help="separate same-policy corpus for transfer validation")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--train-games", type=int, default=48)
    parser.add_argument("--max-records-per-game", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=171)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if (args.train_games < 1 or args.max_records_per_game < 1 or args.epochs < 1
            or args.width < 1 or args.learning_rate <= 0):
        parser.error("invalid critic comparison settings")
    pattern = ("episode_*.json" if args.corpus_source == "self_play_rl"
               else "matchup_*.json")

    def replay_order(path: Path):
        if args.corpus_source == "policy_evaluation":
            parts = path.stem.split("_")
            return (int(parts[3]), int(parts[1]), int(parts[5]))
        return path.name

    primary_paths = sorted(args.replay_dir.glob(pattern), key=replay_order)
    independent_paths = (sorted(args.independent_replay_dir.glob(pattern), key=replay_order)
                         if args.independent_replay_dir else [])
    paths = [*primary_paths, *independent_paths]
    if len(primary_paths) <= args.train_games:
        parser.error("replay directory needs training and held-out games")
    agent = load_policy_agent(args.checkpoint)
    games = []
    seeds = []
    game_keys = []
    fingerprints = {}
    verified = 0
    parent_digest = sha256_file(args.checkpoint)
    parent_key = ("parent_checkpoint_sha256" if args.corpus_source == "self_play_rl"
                  else "policy_checkpoint_sha256")
    started = perf_counter()
    for path in paths:
        digest = sha256_file(path)
        trajectory = read_trajectory(path)
        if (trajectory.skill_metadata or {}).get(parent_key) != parent_digest:
            raise ValueError(f"replay does not descend from selected parent: {path}")
        verified += verify_trajectory(
            trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        if sha256_file(path) != digest:
            raise ValueError(f"replay changed during verification: {path}")
        games.append(selected_records(trajectory, args.max_records_per_game,
                                      args.corpus_source))
        seeds.append(trajectory.seed)
        game_keys.append((trajectory.seed, trajectory.deck_sha256,
                          (trajectory.skill_metadata or {}).get(
                              "learner_seat" if args.corpus_source == "self_play_rl"
                              else "demonstrator_seat")))
        fingerprints[str(path)] = digest
    if len(set(game_keys)) != len(game_keys):
        raise ValueError("duplicate replay deck/seed/seat")
    train = games[:args.train_games]
    holdout = games[args.train_games:len(primary_paths)]
    independent = games[len(primary_paths):]
    baseline = sum(target for _, target in train) / len(train)
    baseline_mse = sum((target - baseline) ** 2 for _, target in holdout) / len(holdout)
    independent_baseline_mse = (sum((target - baseline) ** 2
                                    for _, target in independent) / len(independent)
                                if independent else None)
    number_width = agent.model.state_numbers[0].in_features
    scores = {}
    heldout_losses = {}
    independent_losses = {}
    for architecture in ("v1", "v2"):
        torch.manual_seed(args.seed)
        model = VisibleStateValue(agent.vocabulary.size, number_width,
                                  width=args.width, architecture=architecture)
        optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
        training_losses = []
        for _ in range(args.epochs):
            for records, target in train:
                training_losses.append(state_value_update(
                    model, agent.vocabulary, records, target,
                    agent.model.feature_version, optimizer))
        final_train_losses = game_mse(model, train, agent.vocabulary,
                                      agent.model.feature_version)
        holdout_losses = game_mse(model, holdout, agent.vocabulary,
                                  agent.model.feature_version)
        heldout_losses[architecture] = holdout_losses
        transfer_losses = (game_mse(model, independent, agent.vocabulary,
                                    agent.model.feature_version)
                           if independent else ())
        independent_losses[architecture] = transfer_losses
        scores[architecture] = {
            "last_epoch_training_mse": sum(training_losses[-len(train):]) / len(train),
            "final_training_mse_per_game": sum(final_train_losses) / len(train),
            "holdout_mse_per_game": sum(holdout_losses) / len(holdout),
            "independent_mse_per_game": (sum(transfer_losses) / len(transfer_losses)
                                         if transfer_losses else None),
        }
    result = {
        "corpus_source": args.corpus_source,
        "policy_checkpoint_sha256": parent_digest,
        "replay_sha256": fingerprints,
        "train_games": len(train), "holdout_games": len(holdout),
        "independent_games": len(independent),
        "train_seeds": seeds[:args.train_games],
        "holdout_seeds": seeds[args.train_games:len(primary_paths)],
        "independent_seeds": seeds[len(primary_paths):],
        "selected_train_decisions": sum(len(records) for records, _ in train),
        "selected_holdout_decisions": sum(len(records) for records, _ in holdout),
        "selected_independent_decisions": sum(len(records) for records, _ in independent),
        "verified_decisions": verified,
        "epochs": args.epochs, "max_records_per_game": args.max_records_per_game,
        "width": args.width, "learning_rate": args.learning_rate, "seed": args.seed,
        "constant_training_return": baseline,
        "constant_holdout_mse_per_game": baseline_mse,
        "constant_independent_mse_per_game": independent_baseline_mse,
        "v2_minus_v1_holdout_mse_95pct_paired_bootstrap":
            paired_difference_interval(heldout_losses["v2"], heldout_losses["v1"],
                                       args.seed),
        "v2_minus_v1_independent_mse_95pct_paired_bootstrap": (
            paired_difference_interval(independent_losses["v2"],
                                       independent_losses["v1"], args.seed)
            if independent else None),
        "scores": scores, "wall_seconds": perf_counter() - started,
    }
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
