"""Check one complete local EDOPro room save against its replay on matching assets."""

import argparse
import json
from pathlib import Path

from goat_ai.replay.edopro_live_verify import verify_edopro_live_recording


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path, help="room's .yrpX file")
    parser.add_argument("--native-root", required=True, type=Path,
                        help="matching external unpatched core and scripts")
    args = parser.parse_args()
    stem = args.replay.with_suffix("")
    report = verify_edopro_live_recording(
        args.replay, stem.with_suffix(".review.json"),
        stem.with_suffix(".meta.json"), args.native_root)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
