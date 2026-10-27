"""Compare visible-state critics on one fixed policy with seed-held-out duels."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from time import perf_counter

import torch

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION
from goat_ai.training.self_play import VisibleStateValue, state_value_update
from scripts.compare_value_architectures import (
    game_mse,
    paired_difference_interval,
)


def seed_holdout_split(rows: list[dict], holdout_seeds: int) -> tuple[list[dict], list[dict]]:
    """Reserve whole seeds while preserving every matchup and policy seat."""
    by_seed: dict[int, dict[tuple[int, int], dict]] = defaultdict(dict)
    for row in rows:
        seed, matchup, seat = row["seed"], row["matchup_index"], row["policy_seat"]
        if (type(seed) is not int or type(matchup) is not int
                or type(seat) is not int or seat not in (0, 1)
                or (matchup, seat) in by_seed[seed]):
            raise ValueError("fixed-policy corpus has invalid or duplicate game roles")
        by_seed[seed][matchup, seat] = row
    seeds = sorted(by_seed)
    if not 0 < holdout_seeds < len(seeds):
        raise ValueError("reserve at least one whole seed for train and holdout")
    roles = set(by_seed[seeds[0]])
    if not roles or any(set(group) != roles for group in by_seed.values()):
        raise ValueError("every fixed-policy seed must cover the same deck and seat roles")
    train = [row for seed in seeds[:-holdout_seeds]
             for _, row in sorted(by_seed[seed].items())]
    holdout = [row for seed in seeds[-holdout_seeds:]
               for _, row in sorted(by_seed[seed].items())]
    return train, holdout


def selected_policy_records(trajectory, seat: int, limit: int):
    """Sample only the policy seat's genuine multi-option visible decisions."""
    records = [record for record in trajectory.decisions
               if record.observation.acting_player == seat
               and len(record.legal_actions) > 1]
    if not records:
        raise ValueError("fixed-policy duel has no policy decisions with alternatives")
    if len(records) > limit:
        indices = ([len(records) // 2] if limit == 1 else
                   [index * (len(records) - 1) // (limit - 1)
                    for index in range(limit)])
        records = [records[index] for index in indices]
    reward = 0.0 if trajectory.winner is None else (
        1.0 if trajectory.winner == seat else -1.0)
    return tuple(records), reward


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--holdout-seeds", type=int, default=4)
    parser.add_argument("--max-records-per-game", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=171)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.max_records_per_game < 1 or args.epochs < 1 or args.width < 1
            or args.learning_rate <= 0
            or args.output.resolve() in (args.manifest.resolve(),
                                         args.checkpoint.resolve())):
        parser.error("invalid critic comparison settings")
    checkpoint_hash = sha256_file(args.checkpoint)
    manifest_hash = sha256_file(args.manifest)
    manifest = json.loads(args.manifest.read_text())
    if (manifest.get("schema_version") != 1
            or manifest.get("checkpoint_sha256") != checkpoint_hash
            or manifest.get("opponent") != "tactical"
            or not isinstance(manifest.get("games"), list)):
        raise ValueError("manifest needs a matching fixed policy and tactical opponent")
    if args.output.resolve() in {Path(row["trajectory"]).resolve()
                                 for row in manifest["games"]}:
        raise ValueError("comparison output cannot overwrite a source replay")
    train_rows, holdout_rows = seed_holdout_split(
        manifest["games"], args.holdout_seeds)
    deck_roles: dict[int, tuple[str, str]] = {}
    for row in manifest["games"]:
        deck_pair = (row["deck1"], row["deck2"])
        prior = deck_roles.setdefault(row["matchup_index"], deck_pair)
        if prior != deck_pair:
            raise ValueError("matchup decks changed across fixed-policy seeds")
    agent = load_policy_agent(args.checkpoint)
    started = perf_counter()
    games: dict[str, tuple[tuple, float]] = {}
    verified_decisions = 0
    policy_choices = 0
    for row in [*train_rows, *holdout_rows]:
        path = Path(row["trajectory"])
        digest = sha256_file(path)
        if digest != row["trajectory_sha256"] or str(path) in games:
            raise ValueError(f"replay hash or path differs from manifest: {path}")
        trajectory = read_trajectory(path)
        metadata = trajectory.skill_metadata or {}
        if (trajectory.source != "policy_evaluation"
                or trajectory.seed != row["seed"]
                or trajectory.decks != (row["deck1"], row["deck2"])
                or trajectory.deck_sha256 != tuple(row["deck_sha256"])
                or trajectory.winner != row["winner"]
                or metadata.get("demonstrator_seat") != row["policy_seat"]
                or metadata.get("policy_checkpoint_sha256") != checkpoint_hash
                or metadata.get("policy_feature_version") != agent.model.feature_version
                or metadata.get("policy_inference") != "greedy"
                or metadata.get("policy_inference_version") != POLICY_INFERENCE_VERSION):
            raise ValueError(f"replay is not the manifest's fixed-policy game: {path}")
        count = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        if count != row["verified_decisions"] or sha256_file(path) != digest:
            raise ValueError(f"replay changed or decision count differs: {path}")
        verified_decisions += count
        replay_agent = load_policy_agent(args.checkpoint)
        for record in trajectory.decisions:
            if record.observation.acting_player != row["policy_seat"]:
                continue
            if replay_agent.select_action(record.observation,
                                          record.legal_actions) != record.selected_action:
                raise ValueError(f"recorded policy choice differs: {path}")
            policy_choices += 1
        games[str(path)] = selected_policy_records(
            trajectory, row["policy_seat"], args.max_records_per_game)

    train = [games[row["trajectory"]] for row in train_rows]
    holdout = [games[row["trajectory"]] for row in holdout_rows]
    constant = sum(target for _, target in train) / len(train)
    constant_losses = [(target - constant) ** 2 for _, target in holdout]
    scores = {}
    per_game_losses = {}
    number_width = agent.model.state_numbers[0].in_features
    for architecture in ("v1", "v2"):
        torch.manual_seed(args.seed)
        model = VisibleStateValue(agent.vocabulary.size, number_width,
                                  width=args.width, architecture=architecture)
        optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
        for _ in range(args.epochs):
            for records, target in train:
                state_value_update(model, agent.vocabulary, records, target,
                                   agent.model.feature_version, optimizer)
        train_losses = game_mse(model, train, agent.vocabulary,
                                agent.model.feature_version)
        losses = game_mse(model, holdout, agent.vocabulary,
                          agent.model.feature_version)
        per_game_losses[architecture] = losses
        scores[architecture] = {
            "training_mse_per_game": sum(train_losses) / len(train_losses),
            "holdout_mse_per_game": sum(losses) / len(losses),
            "holdout_mse_by_matchup": {
                str(matchup): sum(loss for loss, row in zip(losses, holdout_rows,
                                                            strict=True)
                                  if row["matchup_index"] == matchup)
                / sum(row["matchup_index"] == matchup for row in holdout_rows)
                for matchup in sorted({row["matchup_index"] for row in holdout_rows})
            },
        }
    result = {
        "checkpoint_sha256": checkpoint_hash,
        "manifest_sha256": manifest_hash,
        "train_seeds": sorted({row["seed"] for row in train_rows}),
        "holdout_seeds": sorted({row["seed"] for row in holdout_rows}),
        "train_games": len(train), "holdout_games": len(holdout),
        "selected_train_decisions": sum(len(records) for records, _ in train),
        "selected_holdout_decisions": sum(len(records) for records, _ in holdout),
        "verified_decisions": verified_decisions,
        "reproduced_policy_choices": policy_choices,
        "epochs": args.epochs, "width": args.width,
        "learning_rate": args.learning_rate, "seed": args.seed,
        "max_records_per_game": args.max_records_per_game,
        "constant_training_return": constant,
        "constant_holdout_mse_per_game": sum(constant_losses) / len(constant_losses),
        "v2_minus_v1_holdout_mse_95pct_paired_bootstrap": paired_difference_interval(
            per_game_losses["v2"], per_game_losses["v1"], args.seed),
        "scores": scores,
        "wall_seconds": perf_counter() - started,
    }
    if sha256_file(args.checkpoint) != checkpoint_hash or \
            sha256_file(args.manifest) != manifest_hash:
        raise ValueError("checkpoint or manifest changed during comparison")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
