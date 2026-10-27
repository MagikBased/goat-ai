"""Compare a policy tournament with matched identical-agent deck controls.

The mirror quantifies deck/seat effects on the exact schedule. It is not an
estimate of the best move at any individual decision.
"""

import argparse
import json
from pathlib import Path

from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.evaluation.tournament import GameResult, TournamentReport, paired_score_difference
from goat_ai.replay.fingerprint import sha256_file
from scripts.compare_tournament_reports import load_report


def _games(raw: dict, path: Path) -> tuple[GameResult, ...]:
    if not isinstance(raw.get("games"), list) or not raw["games"]:
        raise ValueError(f"{path}: mirror has no games")
    games = []
    for item in raw["games"]:
        try:
            game = GameResult(*(item[key] for key in (
                "deck_a", "deck_b", "seed", "a_seat", "winner", "decisions")))
        except (KeyError, TypeError) as error:
            raise ValueError(f"{path}: invalid mirror game") from error
        if (type(game.seed) is not int or type(game.a_seat) is not int
                or not isinstance(game.deck_a, str)
                or not isinstance(game.deck_b, str)
                or game.a_seat not in (0, 1)
                or game.winner is not None and (type(game.winner) is not int
                                                or game.winner not in (0, 1))
                or type(game.decisions) is not int or game.decisions < 1
                or item.get("a_outcome") != game.a_outcome):
            raise ValueError(f"{path}: invalid mirror game outcome")
        games.append(game)
    result = tuple(games)
    summary = raw.get("summary")
    if (not isinstance(summary, dict)
            or summary.get("overall") != TournamentReport(result).summary()["overall"]):
        raise ValueError(f"{path}: mirror summary disagrees with games")
    return result


def compare_policy_to_mirrors(policy_path: Path, mirror_paths: list[Path]) -> dict:
    """Require identical decks, pins, seeds, roles, and baseline versions."""
    if not mirror_paths:
        raise ValueError("at least one baseline mirror report is required")
    policy, candidate = load_report(policy_path, require_unseen_main_decks=True)
    if not policy.get("both_deck_assignments") or policy.get("opponent") is None:
        raise ValueError("policy report needs both deck assignments and a baseline opponent")
    if policy.get("opponent_checkpoint_sha256") is not None:
        raise ValueError("a policy checkpoint opponent is not a baseline mirror")
    if policy.get("opponent_tactical_guard") or policy.get("opponent_position_guard"):
        raise ValueError("guarded policy opponent is not the requested baseline mirror")
    baseline = []
    mirror_hashes = {}
    for path in mirror_paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError(f"{path}: mirror report must be an object")
        controls = (
            raw.get("agent_a") == raw.get("agent_b") == policy["opponent"],
            raw.get("agent_a_version") == raw.get("agent_b_version")
            == policy.get("opponent_agent_version"),
            raw.get("both_deck_assignments") is True,
            raw.get("seeds") == policy["evaluation_seeds"],
            raw.get("ruleset_scope") == f"{policy['engine']} GOAT-mode native adapter",
            str(raw.get("core", "")).rsplit(" ", 1)[-1] == policy["core_commit"],
            raw.get("asset_sha256") == policy["asset_sha256"],
            raw.get("card_scripts_sha256") == policy.get("card_scripts_sha256"),
        )
        if not all(controls):
            raise ValueError(f"{path}: baseline mirror controls differ from policy")
        hashes = raw.get("deck_sha256")
        compositions = raw.get("main_deck_composition_sha256")
        if (not isinstance(hashes, dict) or not isinstance(compositions, dict)
                or not hashes or hashes.keys() != compositions.keys()
                or any(policy["deck_sha256"].get(deck) != digest
                       or sha256_file(Path(deck)) != digest
                       or policy["main_deck_composition_sha256"].get(deck)
                       != compositions[deck]
                       or main_deck_composition_sha256(read_ydk(deck))
                       != compositions[deck]
                       for deck, digest in hashes.items())):
            raise ValueError(f"{path}: mirror deck hashes differ from policy or local files")
        games = _games(raw, path)
        if ({deck for game in games for deck in (game.deck_a, game.deck_b)}
                != set(hashes)):
            raise ValueError(f"{path}: mirror deck hashes do not cover games")
        baseline.extend(games)
        mirror_hashes[str(path)] = sha256_file(path)
    point, low, high = paired_score_difference(candidate, baseline)
    control = TournamentReport(tuple(baseline)).summary()
    by_deck = []
    for row in TournamentReport(candidate).summary()["by_deck_a"]:
        deck = row["deck_a"]
        matched = next(item for item in control["by_deck_a"] if item["deck_a"] == deck)
        by_deck.append({"deck": deck, "policy_wins": row["wins"],
                        "policy_games": row["games"], "mirror_wins": matched["wins"],
                        "mirror_games": matched["games"]})
    return {"schema_version": 1, "policy_report": str(policy_path),
            "policy_report_sha256": sha256_file(policy_path),
            "mirror_report_sha256": mirror_hashes,
            "checkpoint_sha256": policy["checkpoint_sha256"],
            "opponent": policy["opponent"],
            "baseline_version": policy["opponent_agent_version"],
            "core_commit": policy["core_commit"],
            "asset_sha256": policy["asset_sha256"],
            "card_scripts_sha256": policy.get("card_scripts_sha256"),
            "games_per_arm": len(candidate),
            "policy_score": policy["summary"]["overall"]["score_rate"],
            "mirror_score": control["overall"]["score_rate"],
            "paired_score_difference": point,
            "paired_score_difference_95pct_interval": [low, high],
            "by_deck": by_deck}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy_report", type=Path)
    parser.add_argument("mirror_reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare_policy_to_mirrors(args.policy_report, args.mirror_reports)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
