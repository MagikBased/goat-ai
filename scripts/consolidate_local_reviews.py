"""Discover save-server reviews and convert their changed choices to preferences.

Only queue folders with a recorded queue identity are admitted. Legacy label
folders without that identity require an explicit, separately verified queue.
"""

import argparse
import json
import re
from pathlib import Path

from goat_ai.replay.fingerprint import sha256_file
from scripts.convert_multi_queue_reviews import convert_pairs


def discover_pairs(label_root: Path, repository: Path,
                   ) -> tuple[list[tuple[Path, Path]], list[Path]]:
    """Bind each saved label to the exact queue used by its browser server."""
    pairs = []
    legacy = []
    for group in sorted(label_root.iterdir()):
        if not group.is_dir():
            continue
        labels = sorted(group.glob("*.json"))
        if not labels:
            continue
        identity_path = group / "_review_state" / "queue_identity.json"
        if not identity_path.is_file():
            legacy.append(group)
            continue
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        if (identity.get("schema_version") != 1
                or not isinstance(identity.get("queue_path"), str)
                or not isinstance(identity.get("queue_sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", identity["queue_sha256"]) is None
                or not isinstance(identity.get("reviewer"), str)):
            raise ValueError(f"invalid queue identity: {identity_path}")
        queue = (repository / identity["queue_path"]).resolve()
        if not queue.is_relative_to(repository.resolve()) or not queue.is_file():
            raise ValueError(f"queue is missing or outside repository: {queue}")
        if sha256_file(queue) != identity["queue_sha256"]:
            raise ValueError(f"queue changed since reviews were saved: {queue}")
        if not group.name.startswith(identity["queue_sha256"][:12]):
            raise ValueError(f"label folder differs from queue hash: {group}")
        for label in labels:
            raw = json.loads(label.read_text(encoding="utf-8"))
            if raw.get("reviewer") != identity["reviewer"]:
                raise ValueError(f"reviewer differs from queue identity: {label}")
            pairs.append((queue, label))
    return pairs, legacy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label-root", type=Path,
                        default=Path(".cache/goat-ai/review_labels"))
    parser.add_argument("--repository", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--native-root", type=Path,
                        default=Path(".cache/goat-ai"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    pairs, legacy = discover_pairs(args.label_root, args.repository)
    if not pairs:
        parser.error("no queue-bound labels found")
    manifest = convert_pairs(pairs, args.native_root, args.output_dir)
    print(json.dumps({"label_files": len(pairs),
                      "legacy_folders_skipped": len(legacy),
                      "reviewed_decisions": manifest["reviewed_decisions"],
                      "changed_preferences": manifest["changed_preferences"],
                      "output_dir": str(args.output_dir)}))


if __name__ == "__main__":
    main()
