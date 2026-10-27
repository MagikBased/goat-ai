"""Fixed-policy critic splits whole seeds with balanced deck and seat roles."""

import pytest

from scripts.compare_fixed_policy_values import seed_holdout_split


def _rows():
    return [
        {"seed": seed, "matchup_index": matchup, "policy_seat": seat}
        for matchup in (0, 1) for seed in (10, 11, 12, 13) for seat in (0, 1)
    ]


def test_fixed_policy_holdout_reserves_complete_seeds_and_roles():
    train, holdout = seed_holdout_split(_rows(), 1)
    assert len(train) == 12 and len(holdout) == 4
    assert {row["seed"] for row in train} == {10, 11, 12}
    assert {row["seed"] for row in holdout} == {13}
    assert {(row["matchup_index"], row["policy_seat"]) for row in holdout} == {
        (0, 0), (0, 1), (1, 0), (1, 1)}


def test_fixed_policy_holdout_rejects_missing_or_duplicate_roles():
    rows = _rows()
    with pytest.raises(ValueError, match="same deck and seat roles"):
        seed_holdout_split(rows[:-1], 1)
    with pytest.raises(ValueError, match="duplicate"):
        seed_holdout_split([*rows, rows[0]], 1)
    with pytest.raises(ValueError, match="whole seed"):
        seed_holdout_split(rows, 4)
