"""Select learner outcomes from saved self-play trajectories for training.

This only selects files. The downstream trainer must still native-replay-verify
each trajectory and audit player-visible observations before using its actions.
"""

import argparse
from pathlib import Path

from goat_ai.replay import read_trajectory


def select(paths: list[Path], outcome: str, *, expected_games: int | None = None,
           fast_json: bool = False) -> list[Path]:
    if outcome not in ("win", "loss", "draw"):
        raise ValueError("outcome must be win, loss, or draw")
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("supply distinct self-play trajectories")
    if expected_games is not None and expected_games < 1:
        raise ValueError("expected games must be positive")
    selected = []
    episodes = set()
    seeds = set()
    for path in sorted(paths):
        replay = read_trajectory(path, fast_json=fast_json)
        metadata = replay.skill_metadata or {}
        seat = metadata.get("learner_seat")
        index = metadata.get("self_play_episode_index")
        if (replay.source != "self_play_rl" or type(seat) is not int
                or seat not in (0, 1)
                or type(metadata.get("demonstrator_seat")) is not int
                or metadata["demonstrator_seat"] != seat
                or type(index) is not int or index < 0
                or type(replay.seed) is not int or type(replay.winner) not in (int, type(None))
                or replay.winner not in (0, 1, None)):
            raise ValueError(f"{path}: invalid self-play outcome provenance")
        if index in episodes or replay.seed in seeds:
            raise ValueError(f"{path}: duplicate self-play episode or seed")
        episodes.add(index)
        seeds.add(replay.seed)
        result = "draw" if replay.winner is None else (
            "win" if replay.winner == seat else "loss")
        if result == outcome:
            selected.append(path)
    if expected_games is not None and (len(paths) != expected_games
                                       or episodes != set(range(expected_games))):
        raise ValueError("input is not a complete contiguous self-play collection")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay_dir", type=Path)
    parser.add_argument("--outcome", choices=("win", "loss", "draw"), default="win")
    parser.add_argument("--expected-games", type=int)
    parser.add_argument("--fast-trajectory-json", action="store_true")
    parser.add_argument("--output", type=Path, required=True,
                        help="newline-delimited replay paths for a shell mapfile")
    args = parser.parse_args()
    paths = sorted(args.replay_dir.glob("episode_*.json"))
    selected = select(paths, args.outcome, expected_games=args.expected_games,
                      fast_json=args.fast_trajectory_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(f"{path}\n" for path in selected), encoding="utf-8")
    print(f"selected {len(selected)} {args.outcome} replays from {len(paths)} games: "
          f"{args.output}")


if __name__ == "__main__":
    main()
