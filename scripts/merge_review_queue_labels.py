"""Merge authorized replay review exports with unanimous choices.

Each input is validated against the original queue and native replay before
aggregation. Conflicting or under-reviewed decisions stay out of training.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from goat_ai.replay.fingerprint import sha256_file
from scripts.validate_review_queue_labels import validate_labels


def merge_labels(queue_path: Path, label_paths: list[Path], native_root: Path,
                 output_dir: Path, *, min_reviewers: int = 1) -> dict:
    """Write one parser-compatible annotation per replay with agreed choices."""
    if min_reviewers < 1 or not label_paths:
        raise ValueError("positive reviewer threshold and label exports required")
    if len({path.resolve() for path in label_paths}) != len(label_paths):
        raise ValueError("duplicate label export path")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("merge output directory must be absent or empty")
    sources = {}
    votes: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
    reviewer_names: dict[str, str] = {}
    input_labels = []
    checkpoint = None
    queue_hash = sha256_file(queue_path)
    for path in label_paths:
        report = validate_labels(queue_path, [path], native_root)
        if sha256_file(queue_path) != queue_hash:
            raise ValueError("review queue changed during label validation")
        if checkpoint is None:
            checkpoint = report["policy_checkpoint_sha256"]
        elif report["policy_checkpoint_sha256"] != checkpoint:
            raise ValueError("label reports disagree on policy checkpoint")
        case = report["cases"][0]
        raw = json.loads(path.read_text(encoding="utf-8"))
        if sha256_file(path) != case["labels_sha256"]:
            raise ValueError("label export changed during aggregation")
        digest = case["trajectory_sha256"]
        sources[digest] = case["trajectory"]
        reviewer = case["reviewer"]
        reviewer_key = " ".join(reviewer.split()).casefold()
        reviewer_names.setdefault(reviewer_key, reviewer)
        input_labels.append({"path": str(path.resolve()),
                             "sha256": case["labels_sha256"],
                             "trajectory_sha256": digest,
                             "reviewer": reviewer})
        for choice in raw["choices"]:
            index, action = choice["decision_index"], choice["action_index"]
            prior = votes[digest][index].get(reviewer_key)
            if prior is not None and prior != action:
                raise ValueError(f"reviewer {reviewer!r} contradicted their choice "
                                 f"for replay {digest} decision {index}")
            votes[digest][index][reviewer_key] = action
    if sha256_file(queue_path) != queue_hash:
        raise ValueError("review queue changed during aggregation")

    merged = []
    unresolved = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for digest, decisions in sorted(votes.items()):
        choices = []
        provenance = []
        reviewers = set()
        for index, reviewers_to_action in sorted(decisions.items()):
            actions = set(reviewers_to_action.values())
            if len(actions) != 1 or len(reviewers_to_action) < min_reviewers:
                unresolved.append({
                    "trajectory_sha256": digest,
                    "decision_index": index,
                    "reason": "conflict" if len(actions) != 1 else "insufficient_reviews",
                    "votes": {reviewer_names[name]: action
                              for name, action in reviewers_to_action.items()},
                })
                continue
            action = next(iter(actions))
            choices.append({"decision_index": index, "action_index": action})
            provenance.append({"decision_index": index,
                               "reviewers": sorted(reviewer_names[name]
                                                   for name in reviewers_to_action)})
            reviewers.update(reviewer_names[name] for name in reviewers_to_action)
        if not choices:
            continue
        annotation = {
            "schema_version": 1,
            "source_trajectory_sha256": digest,
            "authorization": "policy_review",
            "reviewer": "Merged review: " + ", ".join(sorted(reviewers)),
            "choices": choices,
            "aggregation": {"rule": "unanimous_distinct_reviewer_names",
                            "min_reviewers": min_reviewers,
                            "decision_provenance": provenance,
                            "source_label_sha256": sorted(
                                item["sha256"] for item in input_labels
                                if item["trajectory_sha256"] == digest)},
        }
        path = output_dir / f"{digest}.review.json"
        path.write_text(json.dumps(annotation, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        merged.append({"trajectory": sources[digest], "trajectory_sha256": digest,
                       "annotation": str(path.resolve()),
                       "annotation_sha256": sha256_file(path),
                       "decisions": len(choices)})
    if merged:
        validate_labels(queue_path, [Path(item["annotation"]) for item in merged],
                        native_root)
    manifest = {"schema_version": 1, "queue_sha256": queue_hash,
                "policy_checkpoint_sha256": checkpoint,
                "min_reviewers": min_reviewers,
                "input_labels": input_labels, "merged": merged,
                "unresolved": unresolved}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path)
    parser.add_argument("labels", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--min-reviewers", type=int, default=1)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    manifest = merge_labels(args.queue, args.labels, args.native_root,
                            args.output_dir, min_reviewers=args.min_reviewers)
    print(json.dumps({"output_dir": str(args.output_dir),
                      "merged_replays": len(manifest["merged"]),
                      "agreed_decisions": sum(item["decisions"]
                                              for item in manifest["merged"]),
                      "unresolved_decisions": len(manifest["unresolved"])}))


if __name__ == "__main__":
    main()
