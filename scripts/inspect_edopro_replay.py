"""Inspect EDOPro replay containers without exporting private card data."""

import argparse
import json
from pathlib import Path

from goat_ai.replay import ReplayContainerError, read_edopro_container


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    args = parser.parse_args()
    summaries = []
    for path in args.replays:
        try:
            summaries.append({"path": str(path), **read_edopro_container(path).summary()})
        except (OSError, ReplayContainerError) as exc:
            parser.error(f"{path}: {exc}")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
