"""Local review discovery must preserve the browser queue's exact identity."""

import hashlib
import json

import pytest

from scripts.consolidate_local_reviews import discover_pairs


def test_discovery_binds_labels_to_hashed_queue_and_skips_unbound_legacy(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    queue = repository / "queue.json"
    queue.write_text('{"selected": []}', encoding="utf-8")
    digest = hashlib.sha256(queue.read_bytes()).hexdigest()
    label_root = repository / "labels"
    group = label_root / digest[:12]
    (group / "_review_state").mkdir(parents=True)
    (group / "_review_state" / "queue_identity.json").write_text(
        json.dumps({"schema_version": 1, "queue_path": "queue.json",
                    "queue_sha256": digest, "reviewer": "local-reviewer"}),
        encoding="utf-8")
    label = group / "review.json"
    label.write_text('{"reviewer": "local-reviewer"}', encoding="utf-8")
    legacy = label_root / "legacy"
    legacy.mkdir()
    (legacy / "review.json").write_text("{}", encoding="utf-8")

    assert discover_pairs(label_root, repository) == ([(queue, label)], [legacy])
    queue.write_text('{"selected": [1]}', encoding="utf-8")
    with pytest.raises(ValueError, match="queue changed"):
        discover_pairs(label_root, repository)


def test_discovery_rejects_reviewer_identity_mismatch(tmp_path):
    queue = tmp_path / "queue.json"
    queue.write_text("{}", encoding="utf-8")
    digest = hashlib.sha256(queue.read_bytes()).hexdigest()
    root = tmp_path / "labels"
    group = root / digest[:12]
    (group / "_review_state").mkdir(parents=True)
    (group / "_review_state" / "queue_identity.json").write_text(
        json.dumps({"schema_version": 1, "queue_path": "queue.json",
                    "queue_sha256": digest, "reviewer": "alice"}), encoding="utf-8")
    (group / "review.json").write_text('{"reviewer": "bob"}', encoding="utf-8")
    with pytest.raises(ValueError, match="reviewer differs"):
        discover_pairs(root, tmp_path)
