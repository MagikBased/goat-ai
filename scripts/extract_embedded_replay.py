"""Restore the exact trajectory JSON embedded in a standalone replay viewer."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def extract_embedded_replay(viewer: Path, output: Path) -> str:
    html = viewer.read_text(encoding="utf-8")
    replay = re.search(
        r'<script id="embedded-replay" type="application/json">(.*?)</script>',
        html, re.DOTALL,
    )
    digest = re.search(
        r'<script id="embedded-sha256" type="application/json">(.*?)</script>',
        html, re.DOTALL,
    )
    if replay is None or digest is None:
        raise ValueError("viewer has no embedded replay and SHA-256")
    expected = json.loads(digest.group(1))
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("viewer has an invalid embedded SHA-256")
    payload = replay.group(1) + "\n"
    actual = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if actual != expected:
        raise ValueError(f"embedded replay SHA-256 mismatch: {actual} != {expected}")
    if not isinstance(json.loads(payload), dict):
        raise ValueError("embedded replay is not a JSON object")
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    return actual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("viewer", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(extract_embedded_replay(args.viewer, args.output))


if __name__ == "__main__":
    main()
