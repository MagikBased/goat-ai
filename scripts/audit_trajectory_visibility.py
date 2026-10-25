"""Audit saved player-visible trajectories for legal-choice identity leaks."""

import argparse
import json
from collections import Counter
from pathlib import Path

from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path,
                        help="trajectory JSON files or directories containing them")
    args = parser.parse_args()
    files = sorted({child for path in args.paths
                    for child in (path.rglob("*.json") if path.is_dir() else (path,))})
    if not files:
        parser.error("no trajectory JSON files found")
    counts: Counter[str] = Counter()
    for path in files:
        try:
            counts.update(audit_trajectory_visibility(read_trajectory(path)))
        except (ValueError, KeyError) as error:
            parser.error(f"{path}: {error}")
    print(json.dumps({"files": len(files), **counts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
