"""Verify explicit human choices from a local EDOPro room recording.

The output is a checked review artifact, not training admission.
"""

import argparse
import json
from pathlib import Path

from goat_ai.replay.edopro_live_verify import verify_edopro_human_annotations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path, help="saved room .yrpX")
    parser.add_argument("annotations", type=Path, help="self_recorded annotation JSON")
    parser.add_argument("--native-root", type=Path, required=True)
    args = parser.parse_args()
    stem = args.replay.with_suffix("")
    result = verify_edopro_human_annotations(
        args.replay, stem.with_suffix(".review.json"),
        stem.with_suffix(".meta.json"), args.annotations, args.native_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
