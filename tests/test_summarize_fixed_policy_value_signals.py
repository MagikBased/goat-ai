"""Visible-margin diagnostics keep seed groups and source hashes bound."""

import pytest

from scripts.summarize_fixed_policy_value_signals import summarize


def _source(tmp_path):
    games = []
    samples = []
    for seed in (10, 11):
        for seat in (0, 1):
            path = str(tmp_path / f"seed_{seed}_seat_{seat}.json")
            digest = f"digest_{seed}_{seat}"
            games.append({"trajectory": path, "trajectory_sha256": digest,
                          "seed": seed, "matchup_index": 0,
                          "policy_seat": seat, "winner": 0})
            samples.append({"path": path, "sha256": digest, "won": seat == 0,
                            "cards": 2 if seat == 0 else -1,
                            "life_points_thousands": 1.0 if seat == 0 else -1.0,
                            "snapshot_turn": 4})
    return ({"verified_games": 4, "games": games},
            {"files": 4, "sampled_games": 4, "samples": samples})


def test_fixed_policy_signal_summary_binds_games_and_resamples_seeds(tmp_path):
    manifest, audit = _source(tmp_path)
    report = summarize(audit, manifest, seed=1, replicates=100)
    assert report["source_games"] == report["sampled_games"] == 4
    assert report["card_margin_auc"] == report["lp_margin_auc"] == 1.0
    assert report["seed_bootstrap"]["valid_replicates"] == 100
    assert report["matchups"]["0"]["wins"] == 2


def test_fixed_policy_signal_summary_rejects_changed_or_duplicate_source(tmp_path):
    manifest, audit = _source(tmp_path)
    audit["samples"][0]["sha256"] = "changed"
    with pytest.raises(ValueError, match="disagrees"):
        summarize(audit, manifest, replicates=100)
    audit["samples"][0]["sha256"] = manifest["games"][0]["trajectory_sha256"]
    audit["samples"][1]["path"] = audit["samples"][0]["path"]
    with pytest.raises(ValueError, match="duplicate"):
        summarize(audit, manifest, replicates=100)
