"""Run a checkpoint against a baseline on paired native duels with held-out seeds."""

import argparse
import hashlib
import json
import platform
from dataclasses import asdict
from functools import partial
from pathlib import Path
from time import perf_counter

import torch

from goat_ai.agents import HeuristicAgent, RandomAgent
from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.evaluation import run_tournament, run_tournament_parallel
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION


def make_policy_agent(_seed: int, checkpoint: str):
    return load_policy_agent(checkpoint)


def make_heuristic_agent(_seed: int):
    return HeuristicAgent()


def validate_heldout_seeds(checkpoint: dict, seeds: list[int]) -> None:
    games = checkpoint.get("training_games")
    if not isinstance(games, list) or not games:
        raise ValueError("checkpoint has no training-game provenance")
    training_seeds = {game["seed"] for game in games}
    overlap = training_seeds.intersection(seeds)
    if overlap:
        raise ValueError(f"evaluation seeds overlap training seeds: {sorted(overlap)}")


def validate_unseen_deck_hashes(checkpoint: dict,
                                matchups: list[list[str]]) -> None:
    """Reject exact training YDK file bytes in an evaluation schedule."""
    games = checkpoint.get("training_games")
    if not isinstance(games, list) or not games or any(
            not isinstance(game, dict)
            or not isinstance(game.get("deck_sha256"), (list, tuple))
            or len(game["deck_sha256"]) != 2 for game in games):
        raise ValueError("checkpoint lacks training deck-hash provenance")
    training_hashes = {digest for game in games for digest in game["deck_sha256"]}
    evaluation_hashes = {sha256(Path(deck)) for pair in matchups for deck in pair}
    overlap = training_hashes & evaluation_hashes
    if overlap:
        raise ValueError(f"evaluation deck file hash overlaps training: {sorted(overlap)}")


def validate_unseen_main_decks(checkpoint: dict,
                               matchups: list[list[str]]) -> None:
    """Reject any Main Deck multiset used in checkpoint training games."""
    games = checkpoint.get("training_games")
    if not isinstance(games, list) or not games or any(
            not isinstance(game, dict)
            or not isinstance(game.get("main_deck_composition_sha256"), (list, tuple))
            or len(game["main_deck_composition_sha256"]) != 2 for game in games):
        raise ValueError("checkpoint lacks Main Deck composition provenance")
    training = {digest for game in games
                for digest in game["main_deck_composition_sha256"]}
    evaluation = {main_deck_composition_sha256(read_ydk(deck))
                  for pair in matchups for deck in pair}
    overlap = training & evaluation
    if overlap:
        raise ValueError(f"evaluation Main Deck composition overlaps training: "
                         f"{sorted(overlap)}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"), default="restricted")
    parser.add_argument("--matchup", nargs=2, action="append", metavar=("DECK_A", "DECK_B"))
    opponents = parser.add_mutually_exclusive_group()
    opponents.add_argument("--opponent", choices=("random", "heuristic"), default="random")
    opponents.add_argument("--opponent-checkpoint", type=Path,
                           help="evaluate directly against another saved policy")
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--reject-training-deck-hashes", action="store_true",
                        help="reject exact YDK file bytes present in checkpoint training games")
    parser.add_argument("--require-unseen-main-decks", action="store_true",
                        help="reject Main Deck multisets present in checkpoint training games")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seeds < 1 or args.workers < 1 or args.max_decisions < 1:
        parser.error("seeds, workers, and max decisions must be positive")
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict) or checkpoint.get("schema_version") != 1:
        parser.error("unsupported policy checkpoint schema")
    seeds = list(range(args.seed, args.seed + args.seeds))
    validate_heldout_seeds(checkpoint, seeds)
    if args.opponent_checkpoint:
        opponent_checkpoint = torch.load(args.opponent_checkpoint, map_location="cpu",
                                         weights_only=True)
        if (not isinstance(opponent_checkpoint, dict)
                or opponent_checkpoint.get("schema_version") != 1):
            parser.error("unsupported opponent checkpoint schema")
        validate_heldout_seeds(opponent_checkpoint, seeds)
    fixtures = Path(__file__).resolve().parent.parent / "examples/decks"
    matchups = args.matchup or [[str(fixtures / "vanilla_probe.ydk"),
                                  str(fixtures / "vanilla_reverse.ydk")]]
    if args.reject_training_deck_hashes:
        validate_unseen_deck_hashes(checkpoint, matchups)
        if args.opponent_checkpoint:
            validate_unseen_deck_hashes(opponent_checkpoint, matchups)
    if args.require_unseen_main_decks:
        validate_unseen_main_decks(checkpoint, matchups)
        if args.opponent_checkpoint:
            validate_unseen_main_decks(opponent_checkpoint, matchups)
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    runner = run_tournament_parallel if args.workers > 1 else run_tournament
    opponent = (partial(make_policy_agent, checkpoint=str(args.opponent_checkpoint))
                if args.opponent_checkpoint else
                RandomAgent if args.opponent == "random" else make_heuristic_agent)
    started = perf_counter()
    report = runner(
        matchups, seeds, partial(make_policy_agent, checkpoint=str(args.checkpoint)),
        opponent, partial(engine_type, args.native_root), args.max_decisions,
        **({"workers": args.workers} if args.workers > 1 else {}),
    )
    wall = perf_counter() - started
    assets = {
        name: sha256(args.native_root / relative)
        for name, relative in {
            "core_library": "build/libocgcore.so",
            "cards_database": "database/cards.cdb",
            "goat_database": "database/goat-entries.cdb",
            "goat_whitelist": "banlist/GOAT.lflist.conf",
            "global_constants": "scripts/constant.lua",
            "global_utility": "scripts/utility.lua",
        }.items()
    }
    result = {
        "checkpoint_sha256": sha256(args.checkpoint),
        "policy_inference_version": POLICY_INFERENCE_VERSION,
        "policy_feature_version": checkpoint.get("feature_version", 1),
        "core_commit": "baa3881d0bae48e9994f915f5c931be53c1ba8ef",
        "asset_sha256": assets,
        "training_games": checkpoint["training_games"],
        "evaluation_seeds": seeds,
        "opponent": "checkpoint" if args.opponent_checkpoint else args.opponent,
        "opponent_checkpoint_sha256": (sha256(args.opponent_checkpoint)
                                        if args.opponent_checkpoint else None),
        "engine": args.engine,
        "platform": platform.platform(), "cpu": platform.processor(),
        "workers": args.workers, "wall_seconds_tournament": wall,
        "duels_per_second": len(report.games) / wall,
        "decisions_per_second": sum(game.decisions for game in report.games) / wall,
        "deck_sha256": {deck: sha256(Path(deck)) for matchup in matchups for deck in matchup},
        "main_deck_composition_sha256": {
            deck: main_deck_composition_sha256(read_ydk(deck))
            for matchup in matchups for deck in matchup},
        "summary": report.summary(),
        "games": [asdict(game) | {"a_outcome": game.a_outcome} for game in report.games],
    }
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
