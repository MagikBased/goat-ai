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
    parser.add_argument("--schema", type=int,
                        help="audit only files with this trajectory schema version")
    args = parser.parse_args()
    files = sorted({child for path in args.paths
                    for child in (path.rglob("*.json") if path.is_dir() else (path,))})
    if not files:
        parser.error("no trajectory JSON files found")
    counts: Counter[str] = Counter()
    audited = 0
    for path in files:
        try:
            if args.schema is not None:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict) or raw.get("schema_version") != args.schema:
                    continue
            counts.update(audit_trajectory_visibility(read_trajectory(path)))
            audited += 1
        except (ValueError, KeyError) as error:
            parser.error(f"{path}: {error}")
    if not audited:
        parser.error("no matching trajectory files found")
    print(json.dumps({"files": audited, **counts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
