"""Compare two saved checkpoint tournaments only after their controls match."""

import argparse
import json
from pathlib import Path

from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.evaluation.tournament import (
    GameResult,
    TournamentReport,
    paired_score_difference,
)
from goat_ai.replay.fingerprint import sha256_file

CONTROL_FIELDS = (
    "engine", "core_commit", "asset_sha256", "deck_sha256",
    "main_deck_composition_sha256", "evaluation_seeds",
    "both_deck_assignments", "opponent", "opponent_agent_version",
    "opponent_checkpoint_sha256", "opponent_tactical_guard",
    "opponent_position_guard", "opponent_position_guard_version",
)
OPTIONAL_CONTROL_FIELDS = ("opponent_own_loss_guard",
                           "opponent_own_loss_guard_version")
EXTENDED_FINGERPRINTS = ("card_scripts_sha256", "source_code_sha256")


def load_report(path: Path, *, verify_local_decks: bool = False,
                require_unseen_main_decks: bool = False) -> tuple[dict, tuple[GameResult, ...]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"{path}: tournament report must be an object")
    if not isinstance(raw.get("games"), list):
        raise TypeError(f"{path}: missing tournament games list")
    if not raw["games"] or not isinstance(raw.get("summary"), dict):
        raise ValueError(f"{path}: empty games or missing summary")
    seeds = raw.get("evaluation_seeds")
    if (not isinstance(seeds, list) or not seeds
            or any(type(seed) is not int for seed in seeds)
            or len(set(seeds)) != len(seeds)):
        raise ValueError(f"{path}: invalid evaluation seeds")
    games = []
    for item in raw["games"]:
        if (not isinstance(item, dict)
                or any(key not in item for key in (
                    "deck_a", "deck_b", "seed", "a_seat", "winner", "decisions"))
                or not all(isinstance(item[key], str) for key in ("deck_a", "deck_b"))
                or type(item["seed"]) is not int
                or type(item["a_seat"]) is not int or item["a_seat"] not in (0, 1)
                or item["winner"] is not None and (
                    type(item["winner"]) is not int or item["winner"] not in (0, 1))
                or type(item["decisions"]) is not int or item["decisions"] < 1):
            raise ValueError(f"{path}: invalid game entry")
        game = GameResult(*(item[key] for key in (
            "deck_a", "deck_b", "seed", "a_seat", "winner", "decisions")))
        if item.get("a_outcome") != game.a_outcome:
            raise ValueError(f"{path}: game outcome disagrees with winner and seat")
        games.append(game)
    games = tuple(games)
    if set(seeds) != {game.seed for game in games}:
        raise ValueError(f"{path}: game seeds differ from declared evaluation seeds")
    if {game.seed for game in games} & {
            item["seed"] for item in raw.get("training_games", ())}:
        raise ValueError(f"{path}: training and evaluation seeds overlap")
    summary = TournamentReport(games).summary()["overall"]
    saved = raw["summary"].get("overall")
    if (not isinstance(saved, dict)
            or any(saved.get(key) != value for key, value in summary.items())):
        raise ValueError(f"{path}: saved tournament summary disagrees with games")
    deck_hashes = raw.get("deck_sha256")
    if (not isinstance(deck_hashes, dict)
            or set(deck_hashes) != {deck for game in games
                                    for deck in (game.deck_a, game.deck_b)}):
        raise ValueError(f"{path}: deck hashes do not cover the schedule")
    if verify_local_decks or require_unseen_main_decks:
        for deck, expected in deck_hashes.items():
            if sha256_file(Path(deck)) != expected:
                raise ValueError(f"{path}: local deck differs from report: {deck}")
    if require_unseen_main_decks:
        compositions = raw.get("main_deck_composition_sha256")
        if (not isinstance(compositions, dict)
                or set(compositions) != set(deck_hashes)):
            raise ValueError(f"{path}: Main Deck composition hashes do not cover the schedule")
        for deck, expected in compositions.items():
            if main_deck_composition_sha256(read_ydk(deck)) != expected:
                raise ValueError(f"{path}: local Main Deck differs from report: {deck}")
        training = raw.get("training_games")
        if not isinstance(training, list) or not training or any(
                not isinstance(game, dict)
                or not isinstance(game.get("main_deck_composition_sha256"), (list, tuple))
                or len(game["main_deck_composition_sha256"]) != 2
                or any(not isinstance(digest, str) for digest in
                       game["main_deck_composition_sha256"])
                for game in training):
            raise ValueError(f"{path}: checkpoint lacks Main Deck training provenance")
        used = {digest for game in training
                for digest in game["main_deck_composition_sha256"]}
        overlap = used.intersection(compositions.values())
        if overlap:
            raise ValueError(f"{path}: evaluation Main Deck overlaps training: "
                             f"{sorted(overlap)}")
    return raw, games


def compare_reports(candidate_path: Path, control_path: Path, *,
                    verify_local_decks: bool = False,
                    require_unseen_main_decks: bool = False) -> dict:
    candidate, left = load_report(candidate_path,
                                  verify_local_decks=verify_local_decks,
                                  require_unseen_main_decks=require_unseen_main_decks)
    control, right = load_report(control_path,
                                 verify_local_decks=verify_local_decks,
                                 require_unseen_main_decks=require_unseen_main_decks)
    for key in CONTROL_FIELDS:
        if key not in candidate or key not in control or candidate[key] != control[key]:
            raise ValueError(f"tournament controls differ: {key}")
    for key in OPTIONAL_CONTROL_FIELDS:
        if ((key in candidate) != (key in control)
                or key in candidate and candidate[key] != control[key]):
            raise ValueError(f"tournament controls differ: {key}")
    for key in EXTENDED_FINGERPRINTS:
        if ((key in candidate) != (key in control)
                or key in candidate and candidate[key] != control[key]):
            raise ValueError(f"tournament controls differ: {key}")
    point, low, high = paired_score_difference(left, right)
    by_candidate_deck = []
    for deck in sorted({game.deck_a for game in left}):
        deck_left = tuple(game for game in left if game.deck_a == deck)
        deck_right = tuple(game for game in right if game.deck_a == deck)
        deck_point, deck_low, deck_high = paired_score_difference(
            deck_left, deck_right)
        by_candidate_deck.append({
            "deck": deck,
            "games_per_report": len(deck_left),
            "candidate_score_rate": TournamentReport(deck_left).summary()["overall"]["score_rate"],
            "control_score_rate": TournamentReport(deck_right).summary()["overall"]["score_rate"],
            "paired_score_difference": deck_point,
            "paired_score_difference_95pct_interval": [deck_low, deck_high],
        })
    return {
        "candidate_report": str(candidate_path),
        "candidate_report_sha256": sha256_file(candidate_path),
        "control_report": str(control_path),
        "control_report_sha256": sha256_file(control_path),
        "games_per_report": len(left),
        "unseen_main_decks_verified": require_unseen_main_decks,
        "opponent": candidate["opponent"],
        "card_scripts_sha256": candidate.get("card_scripts_sha256"),
        "source_code_sha256": candidate.get("source_code_sha256"),
        "candidate_wins": candidate["summary"]["overall"]["wins"],
        "control_wins": control["summary"]["overall"]["wins"],
        "paired_score_difference": point,
        "paired_score_difference_95pct_interval": [low, high],
        "by_candidate_deck": by_candidate_deck,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_report", type=Path)
    parser.add_argument("control_report", type=Path)
    parser.add_argument("--verify-local-decks", action="store_true")
    parser.add_argument("--require-unseen-main-decks", action="store_true",
                        help="verify local Main Decks are absent from both checkpoints' training games")
    args = parser.parse_args()
    print(json.dumps(compare_reports(args.candidate_report, args.control_report,
                                     verify_local_decks=args.verify_local_decks,
                                     require_unseen_main_decks=args.require_unseen_main_decks),
                     indent=2))


if __name__ == "__main__":
    main()
