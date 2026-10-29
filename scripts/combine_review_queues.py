"""Combine compatible policy review queues into one save-enabled local session.

Suggestions remain review candidates. Saved labels in the original queues are
not copied or interpreted as approvals in the combined queue.
"""

import argparse
import json
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.shortlist_policy_disagreements import write_review_index
from scripts.validate_review_queue_labels import queue_sources, verify_queue_items


def combine_selected(queues: list[tuple[Path, dict]], output: Path) -> dict:
    """Require one checkpoint and unique source decisions across input queues."""
    if len(queues) < 2:
        raise ValueError("at least two source queues are required")
    output_parent = output.resolve().parent
    checkpoint = None
    selected = []
    source_hashes = {}
    seen = set()
    for path, queue in queues:
        path = path.resolve()
        if path == output.resolve() or path in source_hashes:
            raise ValueError("source queues and combined output must be distinct")
        sources = queue_sources(queue, path)
        if checkpoint is None:
            checkpoint = queue["checkpoint_sha256"]
        elif queue["checkpoint_sha256"] != checkpoint:
            raise ValueError("source queues use different policy checkpoints")
        source_hashes[str(path)] = sha256_file(path)
        for item in queue["selected"]:
            key = (item["trajectory_sha256"], item["decision_index"])
            if key in seen:
                raise ValueError("source queues contain a duplicate review decision")
            seen.add(key)
            replay = sources[item["trajectory_sha256"]][0]
            viewer_name, fragment = item["viewer"].split("#", 1)
            viewer = Path(viewer_name).resolve()
            if (not viewer.is_file() or not viewer.is_relative_to(output_parent)
                    or not fragment.startswith("decision=")):
                raise ValueError("review viewer must exist below combined queue folder")
            selected.append({**item, "trajectory": str(replay),
                             "viewer": f"{viewer}#{fragment}"})
    return {
        "schema_version": 1,
        "purpose": "human_review_candidates_not_training_labels",
        "checkpoint_sha256": checkpoint,
        "source_queue_sha256": source_hashes,
        "selected": selected,
    }


def combine_review_queues(paths: list[Path], output: Path, native_root: Path) -> dict:
    """Verify exact source duels and visibility before publishing the queue."""
    queues = [(path.resolve(), json.loads(path.read_text(encoding="utf-8")))
              for path in paths]
    result = combine_selected(queues, output)
    sources = queue_sources(result, output.resolve())
    checked = 0
    for digest, (replay, offered) in sorted(sources.items()):
        if sha256_file(replay) != digest:
            raise ValueError(f"source replay changed: {replay}")
        trajectory = read_trajectory(replay)
        verify_queue_items(trajectory, offered, result["checkpoint_sha256"])
        checked += verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
        audit_trajectory_visibility(trajectory)
        if sha256_file(replay) != digest:
            raise ValueError(f"source replay changed during verification: {replay}")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != rendered:
        raise ValueError("combined queue already exists with different contents")
    output.write_text(rendered, encoding="utf-8")
    write_review_index(result["selected"], output, native_root,
                       comparison_label="Unreviewed suggestion")
    return {"output": str(output), "items": len(result["selected"]),
            "source_replays": len(sources), "verified_decisions": checked,
            "queue_sha256": sha256_file(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queues", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    args = parser.parse_args()
    print(json.dumps(combine_review_queues(args.queues, args.output, args.native_root)))


if __name__ == "__main__":
    main()
