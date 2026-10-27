"""Input provenance for reviewed-preference KL preservation."""

from pathlib import Path

import pytest

from scripts.train_review_preferences import validate_preservation_reference


def test_parent_preservation_requires_exact_parent_path_and_hash():
    path = Path("parent.json")
    inputs = {"parent_replay": True, "old_hashes": {str(path): "a"},
              "new_hashes": {}, "old_seeds": {3}, "reviewed_seeds": set()}
    validate_preservation_reference(path, "a", 3, **inputs)
    with pytest.raises(ValueError, match="absent from parent provenance"):
        validate_preservation_reference(path, "b", 3, **inputs)


def test_current_preservation_requires_new_replay_and_seed():
    path = Path("current.json")
    inputs = {"parent_replay": False, "old_hashes": {"parent.json": "a"},
              "new_hashes": {"review.json": "b"}, "old_seeds": {3},
              "reviewed_seeds": {5}}
    validate_preservation_reference(path, "c", 7, **inputs)
    for digest, seed, message in (("a", 7, "duplicates training data"),
                                  ("b", 7, "duplicates training data"),
                                  ("c", 3, "seed overlaps training"),
                                  ("c", 5, "seed overlaps training")):
        with pytest.raises(ValueError, match=message):
            validate_preservation_reference(path, digest, seed, **inputs)
