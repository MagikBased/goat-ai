"""Print a pinned ocgcore GOAT or MR1 startup decision as JSON."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from goat_ai.engine.ocgcore_probe import OcgcoreProbe
from goat_ai.engine.probe_deck import VANILLA_DECK


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mode", choices=("goat", "mr1_startup"), default="goat")
    args = parser.parse_args()
    root = args.native_root
    with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                      root / "scripts", mode=args.mode) as probe:
        result = probe.first_decision(args.seed, VANILLA_DECK)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
