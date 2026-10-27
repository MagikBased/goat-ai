"""Compare early player-visible card and LP margins with eventual duel outcomes.

One snapshot per game avoids counting hundreds of correlated decisions as
independent examples. This is a diagnostic, not a policy or reward function.
"""

import argparse
import json
from pathlib import Path

from goat_ai.agents.tactical_guard import SHEEP_TOKENS
from goat_ai.replay import read_trajectory
from goat_ai.replay.fingerprint import sha256_file


def win_loss_auc(wins: list[float], losses: list[float]) -> float | None:
    """Pairwise ranking accuracy, with half credit for ties."""
    if not wins or not losses:
        return None
    return sum((win > loss) + 0.5 * (win == loss)
               for win in wins for loss in losses) / (len(wins) * len(losses))


def visible_margins(observation) -> tuple[int, float]:
    """Count visible real cards, not Sheep Tokens; never inspect hidden IDs."""
    own = observation.viewer
    field_margin = sum((1 if card.controller == own else -1)
                       for card in observation.field if card.code not in SHEEP_TOKENS)
    card_margin = len(observation.hand) - observation.opponent_hand_count + field_margin
    lp_margin = (observation.life_points[own] - observation.life_points[1 - own]) / 1000
    return card_margin, lp_margin


def audit(paths: list[Path], *, turn: int = 4) -> dict:
    if turn < 1 or not paths:
        raise ValueError("audit needs paths and a positive turn")
    samples = []
    for path in paths:
        trajectory = read_trajectory(path)
        seat = (trajectory.skill_metadata or {}).get("demonstrator_seat")
        if seat not in (0, 1):
            raise ValueError(f"{path}: missing demonstrator seat")
        if trajectory.winner is None:
            continue  # A draw has no binary outcome label.
        selected = next((record.observation for record in trajectory.decisions
                         if record.observation.acting_player == seat
                         and record.observation.phase == "main1"
                         and record.observation.turn >= turn), None)
        if selected is None:
            continue
        cards, life_points = visible_margins(selected)
        samples.append({"path": str(path), "sha256": sha256_file(path),
                        "won": trajectory.winner == seat, "cards": cards,
                        "life_points_thousands": life_points,
                        "snapshot_turn": selected.turn})
    wins = [row for row in samples if row["won"]]
    losses = [row for row in samples if not row["won"]]
    return {
        "files": len(paths), "sampled_games": len(samples),
        "wins": len(wins), "losses": len(losses),
        "card_margin_auc": win_loss_auc([row["cards"] for row in wins],
                                        [row["cards"] for row in losses]),
        "lp_margin_auc": win_loss_auc([row["life_points_thousands"] for row in wins],
                                      [row["life_points_thousands"] for row in losses]),
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--turn", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    paths = sorted({child for path in args.paths
                    for child in (path.glob("*.json") if path.is_dir() else (path,))
                    if child.name != "manifest.json"})
    result = audit(paths, turn=args.turn)
    data = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(data)
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
