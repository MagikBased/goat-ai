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

from goat_ai.agents import (
    CombatHeuristicAgent,
    HeuristicAgent,
    RandomAgent,
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.agents.card_metadata import load_weak_flip_monster_attack
from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.evaluation import both_deck_assignments, run_tournament, run_tournament_parallel
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION
from scripts.evaluate_native import card_scripts_sha256, file_set_sha256


def make_policy_agent(_seed: int, checkpoint: str, tactical_guard: bool = False,
                      card_races: dict[int, int] | None = None,
                      weak_flip_attacks: dict[int, int] | None = None,
                      self_target_guard: bool = False,
                      own_loss_guard: bool = False,
                      own_loss_guard_version: int = 1,
                      card_facts: dict[int, tuple[int, int, int]] | None = None,
                      position_guard: bool = False):
    return load_policy_agent(checkpoint, tactical_guard=tactical_guard,
                             card_races=card_races,
                             weak_flip_attacks=weak_flip_attacks,
                             self_target_guard=self_target_guard,
                             own_loss_guard=own_loss_guard,
                             own_loss_guard_version=own_loss_guard_version,
                             card_facts=card_facts,
                             position_guard=position_guard)


def make_heuristic_agent(_seed: int):
    return HeuristicAgent()


def make_combat_heuristic_agent(_seed: int):
    return CombatHeuristicAgent()


def make_tactical_agent(_seed: int, flip_codes: frozenset[int],
                        card_races: dict[int, int],
                        card_facts: dict[int, tuple[int, int, int]]):
    return TacticalHeuristicAgent(flip_codes, card_races, card_facts=card_facts)


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


def policy_source_sha256(repository: Path) -> str:
    """Bind tournament outcomes to the policy evaluator and project Python code."""
    sources = list((repository / "src/goat_ai").rglob("*.py"))
    sources.extend((repository / "scripts/evaluate_policy.py",
                    repository / "scripts/evaluate_native.py",
                    repository / "pyproject.toml"))
    return file_set_sha256(repository, sources)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"), default="restricted")
    parser.add_argument("--matchup", nargs=2, action="append", metavar=("DECK_A", "DECK_B"))
    parser.add_argument("--both-deck-assignments", action="store_true",
                        help="evaluate either policy with each deck in every pair")
    parser.add_argument("--tactical-guard", action="store_true",
                        help="apply experimental visible-state action filter to candidate")
    parser.add_argument("--weak-flip-guard", action="store_true",
                        help="also prefer setting low-ATK Flip monsters; requires tactical guard")
    parser.add_argument("--self-target-guard", action="store_true",
                        help="avoid observed BLS and MST self-target losses; requires tactical guard")
    parser.add_argument("--own-loss-guard", action="store_true",
                        help="standalone visible own-only removal ablation")
    parser.add_argument("--own-loss-guard-version", type=int, choices=(1, 2, 3, 4, 5, 6), default=1,
                        help="v2 defers one-shot MST; v3 idle own-only Ring; "
                             "v4 prefers a safe opposing Ring target; v5 combines v2 and v3; "
                             "v6 also defers own one-shot MST responses")
    parser.add_argument("--position-guard", action="store_true",
                        help="standalone Sheep Token and empty-field position filter")
    parser.add_argument("--opponent-tactical-guard", action="store_true",
                        help="guard the opponent checkpoint for a direct ablation")
    parser.add_argument("--opponent-position-guard", action="store_true",
                        help="apply the position guard to the opponent checkpoint")
    parser.add_argument("--opponent-own-loss-guard", action="store_true",
                        help="apply an own-loss guard to the opponent checkpoint")
    parser.add_argument("--opponent-own-loss-guard-version", type=int,
                        choices=(1, 2, 3, 4, 5, 6), default=1,
                        help="own-loss guard version for the opponent checkpoint")
    opponents = parser.add_mutually_exclusive_group()
    opponents.add_argument("--opponent", choices=("random", "heuristic",
                                                  "combat_heuristic", "tactical"),
                           default="random")
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
    if args.weak_flip_guard and not args.tactical_guard:
        parser.error("--weak-flip-guard requires --tactical-guard")
    if args.self_target_guard and not args.tactical_guard:
        parser.error("--self-target-guard requires --tactical-guard")
    if args.self_target_guard and args.weak_flip_guard:
        parser.error("choose one experimental extension of guard v3")
    if args.position_guard and args.tactical_guard:
        parser.error("position guard is a standalone ablation")
    if args.own_loss_guard and (args.tactical_guard or args.position_guard):
        parser.error("own-loss guard is a standalone ablation")
    if args.own_loss_guard_version != 1 and not args.own_loss_guard:
        parser.error("--own-loss-guard-version requires --own-loss-guard")
    if args.opponent_tactical_guard and not args.opponent_checkpoint:
        parser.error("--opponent-tactical-guard requires --opponent-checkpoint")
    if args.opponent_position_guard and not args.opponent_checkpoint:
        parser.error("--opponent-position-guard requires --opponent-checkpoint")
    if args.opponent_position_guard and args.opponent_tactical_guard:
        parser.error("opponent position guard is a standalone ablation")
    if args.opponent_own_loss_guard and not args.opponent_checkpoint:
        parser.error("--opponent-own-loss-guard requires --opponent-checkpoint")
    if args.opponent_own_loss_guard_version != 1 and not args.opponent_own_loss_guard:
        parser.error("--opponent-own-loss-guard-version requires --opponent-own-loss-guard")
    if args.opponent_own_loss_guard and (args.opponent_tactical_guard
                                         or args.opponent_position_guard):
        parser.error("opponent own-loss guard is a standalone ablation")
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
    if args.both_deck_assignments:
        matchups = both_deck_assignments(matchups)
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
    tactical_opponent = partial(
        make_tactical_agent, flip_codes=load_flip_monster_codes(args.native_root),
        card_races=load_card_races(args.native_root),
        card_facts=load_card_facts(args.native_root)) if args.opponent == "tactical" else None
    opponent = (partial(make_policy_agent, checkpoint=str(args.opponent_checkpoint),
                        tactical_guard=args.opponent_tactical_guard,
                        position_guard=args.opponent_position_guard,
                        own_loss_guard=args.opponent_own_loss_guard,
                        own_loss_guard_version=args.opponent_own_loss_guard_version,
                        card_facts=(load_card_facts(args.native_root)
                                    if args.opponent_own_loss_guard
                                    and args.opponent_own_loss_guard_version in (2, 5, 6) else None),
                        card_races=(load_card_races(args.native_root)
                                    if args.opponent_tactical_guard else None))
                if args.opponent_checkpoint else {
                    "random": RandomAgent,
                    "heuristic": make_heuristic_agent,
                    "combat_heuristic": make_combat_heuristic_agent,
                    "tactical": tactical_opponent,
                }[args.opponent])
    started = perf_counter()
    card_races = load_card_races(args.native_root) if args.tactical_guard else None
    weak_flip_attacks = (load_weak_flip_monster_attack(args.native_root)
                         if args.weak_flip_guard else None)
    report = runner(
        matchups, seeds, partial(make_policy_agent, checkpoint=str(args.checkpoint),
                                 tactical_guard=args.tactical_guard,
                                 card_races=card_races,
                                 weak_flip_attacks=weak_flip_attacks,
                                 self_target_guard=args.self_target_guard,
                                 own_loss_guard=args.own_loss_guard,
                                 own_loss_guard_version=args.own_loss_guard_version,
                                 card_facts=(load_card_facts(args.native_root)
                                             if args.own_loss_guard_version in (2, 5, 6) else None),
                                 position_guard=args.position_guard),
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
            "unofficial_database": "database/cards-unofficial.cdb",
            "goat_whitelist": "banlist/GOAT.lflist.conf",
            "global_constants": "scripts/constant.lua",
            "global_utility": "scripts/utility.lua",
        }.items()
    }
    repository = Path(__file__).resolve().parents[1]
    result = {
        "checkpoint_sha256": sha256(args.checkpoint),
        "policy_inference_version": POLICY_INFERENCE_VERSION,
        "tactical_guard": args.tactical_guard,
        "own_loss_guard": args.own_loss_guard,
        "own_loss_guard_version": (args.own_loss_guard_version if args.own_loss_guard
                                    else None),
        "position_guard": args.position_guard,
        "position_guard_version": 2 if args.position_guard else None,
        "tactical_guard_version": (5 if args.self_target_guard else
                                   4 if args.weak_flip_guard else 3
                                   if args.tactical_guard else None),
        "opponent_tactical_guard": args.opponent_tactical_guard,
        "opponent_position_guard": args.opponent_position_guard,
        "opponent_position_guard_version": 2 if args.opponent_position_guard else None,
        "opponent_own_loss_guard": args.opponent_own_loss_guard,
        "opponent_own_loss_guard_version": (args.opponent_own_loss_guard_version
                                             if args.opponent_own_loss_guard else None),
        "policy_feature_version": checkpoint.get("feature_version", 1),
        "core_commit": "baa3881d0bae48e9994f915f5c931be53c1ba8ef",
        "asset_sha256": assets,
        "card_scripts_sha256": card_scripts_sha256(args.native_root),
        "source_code_sha256": policy_source_sha256(repository),
        "training_games": checkpoint["training_games"],
        "evaluation_seeds": seeds,
        "both_deck_assignments": args.both_deck_assignments,
        "opponent": "checkpoint" if args.opponent_checkpoint else args.opponent,
        "opponent_agent_version": (None if args.opponent_checkpoint else {
            "random": 1,
            "heuristic": HeuristicAgent.teacher_version,
            "combat_heuristic": CombatHeuristicAgent.teacher_version,
            "tactical": TacticalHeuristicAgent.teacher_version,
        }[args.opponent]),
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
