"""Replay a recorded duel against pinned native assets and compare every choice."""

import argparse
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.replay import read_trajectory, verify_trajectory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--deck1", type=Path)
    parser.add_argument("--deck2", type=Path)
    parser.add_argument("--experimental", action="store_true")
    args = parser.parse_args()
    trajectory = read_trajectory(args.trajectory)
    paths = None
    if args.deck1 or args.deck2:
        if not args.deck1 or not args.deck2:
            parser.error("--deck1 and --deck2 must be supplied together")
        paths = (args.deck1, args.deck2)
    engine_type = ExperimentalOcgcoreEngine if args.experimental else RestrictedOcgcoreEngine
    count = verify_trajectory(trajectory, engine_type(args.native_root), paths)
    print(f"verified {count} decisions; winner={trajectory.winner}")


if __name__ == "__main__":
    main()
