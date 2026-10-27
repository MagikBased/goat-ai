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
from goat_ai.training.policy import encode_decision
from goat_ai.training.self_play import (
    VisibleStateValue,
    predict_state_values,
    state_value_update,
)


class VisibleResourceValue(torch.nn.Module):
    """Small visible-only outcome baseline: LP, hand, and field counts."""

    def __init__(self) -> None:
        super().__init__()
        self.value = torch.nn.Sequential(torch.nn.Linear(6, 1), torch.nn.Tanh())

    @staticmethod
    def _resources(features):
        numbers = features.state_numbers
        cards = features.state_cards
        own_monsters = ((cards[:, 1] == 2) & (cards[:, 2] == 1)).sum() / 5
        other_monsters = ((cards[:, 1] == 2) & (cards[:, 2] == 2)).sum() / 5
        own_backrow = ((cards[:, 1] == 3) & (cards[:, 2] == 1)).sum() / 5
        other_backrow = ((cards[:, 1] == 3) & (cards[:, 2] == 2)).sum() / 5
        return torch.stack((numbers[0] - numbers[1],
                            numbers[6] - numbers[7],
                            own_monsters - other_monsters,
                            own_backrow - other_backrow,
                            numbers[2] - numbers[3],
                            numbers[8]))

    def forward_batch(self, decisions):
        return self.value(torch.stack([self._resources(item) for item in decisions])
                          ).squeeze(1)


def fit_resource_ridge(games, vocabulary, feature_version, penalty: float = 0.1):
    """Fit six visible features with equal game weight and fixed L2 shrinkage."""
    if not games or penalty <= 0:
        raise ValueError("resource ridge needs games and positive shrinkage")

    def rows(records):
        return torch.stack([
            VisibleResourceValue._resources(encode_decision(
                record.observation, record.legal_actions, vocabulary,
                feature_version)).double()
            for record in records])

    game_rows = [rows(records) for records, _ in games]
    x = torch.cat(game_rows)
    y = torch.cat([torch.full((len(records),), target, dtype=torch.float64)
                   for records, target in games])
    weight = torch.cat([torch.full((len(records),), 1 / len(records),
                                   dtype=torch.float64)
                        for records, _ in games])
    mean = (x * weight[:, None]).sum(0) / weight.sum()
    scale = ((x - mean).square() * weight[:, None]).sum(0).div(
        weight.sum()).sqrt().clamp(min=1e-6)
    z = torch.cat(((x - mean) / scale, torch.ones((len(x), 1), dtype=x.dtype)), 1)
    regularizer = torch.diag(torch.tensor([penalty * len(games)] * 6 + [0.0],
                                          dtype=x.dtype))
    coefficients = torch.linalg.solve(z.T @ (weight[:, None] * z) + regularizer,
                                      z.T @ (weight * y))

    def mse(other_games):
        losses = []
        for records, target in other_games:
            inputs = rows(records)
            predictions = (((inputs - mean) / scale) @ coefficients[:-1]
                           + coefficients[-1]).clamp(-1, 1)
            losses.append(float((predictions - target).square().mean()))
        return tuple(losses)

    return mse, tuple(float(value) for value in coefficients)


def selected_records(trajectory, limit: int, source: str = "self_play_rl"):
    seat_key = "learner_seat" if source == "self_play_rl" else "demonstrator_seat"
    seat = (trajectory.skill_metadata or {}).get(seat_key)
    if (trajectory.source != source or type(seat) is not int
            or seat not in (0, 1)):
        label = f"learner-seat ({seat_key})" if source == "self_play_rl" else seat_key
        raise ValueError(f"critic comparison needs {source} replays with {label}")
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


def seed_clustered_difference_interval(first, second, seeds, seed: int):
    """Resample whole seed blocks, preserving matchup and seat correlation."""
    if len(first) != len(second) or len(first) != len(seeds) or not first:
        raise ValueError("seed-clustered MSE needs equal nonempty game sets")
    grouped = {}
    for a, b, game_seed in zip(first, second, seeds, strict=True):
        grouped.setdefault(game_seed, []).append(a - b)
    blocks = [sum(values) / len(values) for values in grouped.values()]
    rng = random.Random(seed)
    samples = sorted(sum(blocks[rng.randrange(len(blocks))]
                         for _ in blocks) / len(blocks)
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
    parser.add_argument("--independent-mirror-policy", action="store_true",
                        help="require independent duels to use the same frozen checkpoint on both seats")
    parser.add_argument("--primary-mirror-policy", action="store_true",
                        help="require training and held-out duels to be frozen mirror self-play")
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
    if args.independent_mirror_policy and not args.independent_replay_dir:
        parser.error("--independent-mirror-policy requires --independent-replay-dir")
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
    for game_index, path in enumerate(paths):
        digest = sha256_file(path)
        trajectory = read_trajectory(path)
        if (trajectory.skill_metadata or {}).get(parent_key) != parent_digest:
            raise ValueError(f"replay does not descend from selected parent: {path}")
        if (((args.independent_mirror_policy and game_index >= len(primary_paths))
             or (args.primary_mirror_policy and game_index < len(primary_paths)))
                and (trajectory.skill_metadata or {}).get("opponent_checkpoint_sha256")
                != parent_digest):
            raise ValueError(f"duel is not frozen mirror self-play: {path}")
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
    baseline_losses = tuple((target - baseline) ** 2 for _, target in holdout)
    independent_baseline_losses = tuple((target - baseline) ** 2
                                        for _, target in independent)
    baseline_mse = sum(baseline_losses) / len(baseline_losses)
    independent_baseline_mse = (sum(independent_baseline_losses)
                                / len(independent_baseline_losses)
                                if independent_baseline_losses else None)
    number_width = agent.model.state_numbers[0].in_features
    scores = {}
    heldout_losses = {}
    independent_losses = {}
    for architecture in ("v1", "v2", "resource"):
        torch.manual_seed(args.seed)
        model = (VisibleResourceValue() if architecture == "resource" else
                 VisibleStateValue(agent.vocabulary.size, number_width,
                                   width=args.width, architecture=architecture))
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
    ridge_mse, ridge_coefficients = fit_resource_ridge(
        train, agent.vocabulary, agent.model.feature_version)
    ridge_train = ridge_mse(train)
    ridge_holdout = ridge_mse(holdout)
    ridge_independent = ridge_mse(independent) if independent else ()
    mirror_zero_losses = (tuple(target * target for _, target in independent)
                          if args.independent_mirror_policy else ())
    mirror_holdout_zero_losses = (tuple(target * target for _, target in holdout)
                                  if args.primary_mirror_policy else ())
    scores["resource_ridge"] = {
        "final_training_mse_per_game": sum(ridge_train) / len(ridge_train),
        "holdout_mse_per_game": sum(ridge_holdout) / len(ridge_holdout),
        "independent_mse_per_game": (sum(ridge_independent) / len(ridge_independent)
                                     if ridge_independent else None),
        "penalty_per_training_game": 0.1,
        "standardized_coefficients_and_intercept": ridge_coefficients,
    }
    result = {
        "corpus_source": args.corpus_source,
        "independent_mirror_policy": args.independent_mirror_policy,
        "primary_mirror_policy": args.primary_mirror_policy,
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
        "mirror_zero_independent_mse_per_game": (
            sum(mirror_zero_losses) / len(mirror_zero_losses)
            if mirror_zero_losses else None),
        "mirror_zero_holdout_mse_per_game": (
            sum(mirror_holdout_zero_losses) / len(mirror_holdout_zero_losses)
            if mirror_holdout_zero_losses else None),
        "v2_minus_v1_holdout_mse_95pct_paired_bootstrap":
            paired_difference_interval(heldout_losses["v2"], heldout_losses["v1"],
                                       args.seed),
        "v2_minus_v1_independent_mse_95pct_paired_bootstrap": (
            paired_difference_interval(independent_losses["v2"],
                                       independent_losses["v1"], args.seed)
            if independent else None),
        "ridge_minus_constant_holdout_mse_95pct_paired_bootstrap":
            paired_difference_interval(ridge_holdout, baseline_losses, args.seed),
        "ridge_minus_constant_independent_mse_95pct_paired_bootstrap": (
            paired_difference_interval(ridge_independent,
                                       independent_baseline_losses, args.seed)
            if independent else None),
        "ridge_minus_constant_holdout_mse_95pct_seed_clustered_bootstrap":
            seed_clustered_difference_interval(
                ridge_holdout, baseline_losses,
                seeds[args.train_games:len(primary_paths)], args.seed),
        "ridge_minus_constant_independent_mse_95pct_seed_clustered_bootstrap": (
            seed_clustered_difference_interval(
                ridge_independent, independent_baseline_losses,
                seeds[len(primary_paths):], args.seed)
            if independent else None),
        "ridge_minus_mirror_zero_independent_mse_95pct_seed_clustered_bootstrap": (
            seed_clustered_difference_interval(
                ridge_independent, mirror_zero_losses,
                seeds[len(primary_paths):], args.seed)
            if mirror_zero_losses else None),
        "ridge_minus_mirror_zero_holdout_mse_95pct_seed_clustered_bootstrap": (
            seed_clustered_difference_interval(
                ridge_holdout, mirror_holdout_zero_losses,
                seeds[args.train_games:len(primary_paths)], args.seed)
            if mirror_holdout_zero_losses else None),
        "scores": scores, "wall_seconds": perf_counter() - started,
    }
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
