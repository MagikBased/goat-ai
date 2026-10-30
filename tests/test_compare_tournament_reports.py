"""Saved tournament comparisons require the same opponent and pinned controls."""

import json
from copy import deepcopy

import pytest

from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.evaluation.tournament import GameResult, TournamentReport
from goat_ai.replay.fingerprint import sha256_file
from scripts.compare_tournament_reports import compare_reports


def report(deck_a, deck_b, *, candidate):
    games = (
        GameResult(str(deck_a), str(deck_b), 100, 0, 0 if candidate else 1, 12),
        GameResult(str(deck_a), str(deck_b), 100, 1, 1 if candidate else 0, 13),
    )
    return {
        "engine": "experimental", "core_commit": "pinned",
        "asset_sha256": {"core_library": "a" * 64},
        "deck_sha256": {str(path): sha256_file(path) for path in (deck_a, deck_b)},
        "main_deck_composition_sha256": {str(path): "b" * 64
                                         for path in (deck_a, deck_b)},
        "evaluation_seeds": [100], "both_deck_assignments": False,
        "opponent": "tactical", "opponent_agent_version": 14,
        "opponent_checkpoint_sha256": None,
        "opponent_tactical_guard": False, "opponent_position_guard": False,
        "opponent_position_guard_version": None,
        "opponent_own_loss_guard": False, "opponent_own_loss_guard_version": None,
        "training_games": [{"seed": 99}],
        "games": [vars(game) | {"a_outcome": game.a_outcome} for game in games],
        "summary": TournamentReport(games).summary(),
    }


def saved_pair(tmp_path):
    deck_a = tmp_path / "a.ydk"
    deck_b = tmp_path / "b.ydk"
    deck_a.write_text("#main\n1\n")
    deck_b.write_text("#main\n2\n")
    left = report(deck_a, deck_b, candidate=True)
    right = report(deck_a, deck_b, candidate=False)
    a = tmp_path / "candidate.json"
    b = tmp_path / "control.json"
    a.write_text(json.dumps(left))
    b.write_text(json.dumps(right))
    return a, b, left, right, deck_a


def test_comparison_checks_local_decks_and_reports_paired_difference(tmp_path):
    a, b, _, _, deck = saved_pair(tmp_path)
    result = compare_reports(a, b, verify_local_decks=True)
    assert result["games_per_report"] == 2
    assert result["paired_score_difference"] == 1.0
    assert result["paired_score_difference_95pct_interval"] == [-1.0, 1.0]
    assert result["by_candidate_deck"] == [{
        "deck": str(deck), "games_per_report": 2,
        "candidate_score_rate": 1.0, "control_score_rate": 0.0,
        "paired_score_difference": 1.0,
        "paired_score_difference_95pct_interval": [-1.0, 1.0],
    }]
    deck.write_text("#main\n3\n")
    with pytest.raises(ValueError, match="local deck differs"):
        compare_reports(a, b, verify_local_decks=True)


def test_per_deck_comparison_exposes_reversal_hidden_by_overall_tie(tmp_path):
    a, b, left, right, deck_a = saved_pair(tmp_path)
    deck_b = tmp_path / "b.ydk"
    for report, first_wins in ((left, True), (right, False)):
        games = (
            GameResult(str(deck_a), str(deck_b), 100, 0,
                       0 if first_wins else 1, 12),
            GameResult(str(deck_a), str(deck_b), 100, 1,
                       1 if first_wins else 0, 13),
            GameResult(str(deck_b), str(deck_a), 100, 0,
                       1 if first_wins else 0, 14),
            GameResult(str(deck_b), str(deck_a), 100, 1,
                       0 if first_wins else 1, 15),
        )
        report["both_deck_assignments"] = True
        report["games"] = [vars(game) | {"a_outcome": game.a_outcome}
                           for game in games]
        report["summary"] = TournamentReport(games).summary()
    a.write_text(json.dumps(left))
    b.write_text(json.dumps(right))
    result = compare_reports(a, b, verify_local_decks=True)
    assert result["paired_score_difference"] == 0.0
    assert [(row["deck"], row["paired_score_difference"])
            for row in result["by_candidate_deck"]] == [
                (str(deck_a), 1.0), (str(deck_b), -1.0)]


def test_comparison_accepts_matching_archived_reports_without_opponent_own_loss_fields(
    tmp_path,
):
    a, b, left, right, _ = saved_pair(tmp_path)
    for report in (left, right):
        report.pop("opponent_own_loss_guard")
        report.pop("opponent_own_loss_guard_version")
    a.write_text(json.dumps(left))
    b.write_text(json.dumps(right))
    assert compare_reports(a, b)["games_per_report"] == 2
    right["opponent_own_loss_guard"] = False
    b.write_text(json.dumps(right))
    with pytest.raises(ValueError, match="opponent_own_loss_guard"):
        compare_reports(a, b)


@pytest.mark.parametrize("field,value", [
    ("asset_sha256", {"core_library": "c" * 64}),
    ("opponent", "random"),
    ("evaluation_seeds", [101]),
    ("deck_sha256", {"other.ydk": "d" * 64}),
    ("opponent_own_loss_guard_version", 3),
])
def test_comparison_rejects_mismatched_controls(tmp_path, field, value):
    a, b, _, right, _ = saved_pair(tmp_path)
    changed = deepcopy(right)
    changed[field] = value
    b.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="differ|do not cover|seeds differ"):
        compare_reports(a, b)


def test_comparison_rejects_tampered_outcome_and_training_seed(tmp_path):
    a, b, left, _, _ = saved_pair(tmp_path)
    changed = deepcopy(left)
    changed["games"][0]["a_outcome"] = "loss"
    a.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="outcome disagrees"):
        compare_reports(a, b)
    changed = deepcopy(left)
    changed["summary"]["overall"]["score_rate_95pct_paired_bootstrap"] = [0.1, 0.9]
    a.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="summary disagrees"):
        compare_reports(a, b)
    changed = deepcopy(left)
    changed["training_games"][0]["seed"] = 100
    a.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="training and evaluation seeds overlap"):
        compare_reports(a, b)


def test_comparison_rejects_matching_reports_with_incomplete_schedule(tmp_path):
    a, b, left, right, _ = saved_pair(tmp_path)
    complete = (deepcopy(left), deepcopy(right))
    for saved in (left, right):
        games = tuple(GameResult(*(entry[key] for key in (
            "deck_a", "deck_b", "seed", "a_seat", "winner", "decisions")))
            for entry in saved["games"][:1])
        saved["games"] = saved["games"][:1]
        saved["summary"] = TournamentReport(games).summary()
    a.write_text(json.dumps(left))
    b.write_text(json.dumps(right))
    with pytest.raises(ValueError, match="missing or duplicate games"):
        compare_reports(a, b)

    left, right = complete
    for saved in (left, right):
        saved["games"].append(saved["games"][0])
        saved["summary"] = TournamentReport(tuple(GameResult(*(
            entry[key] for key in ("deck_a", "deck_b", "seed", "a_seat",
                                   "winner", "decisions")))
            for entry in saved["games"])).summary()
    a.write_text(json.dumps(left))
    b.write_text(json.dumps(right))
    with pytest.raises(ValueError, match="missing or duplicate games"):
        compare_reports(a, b)


def test_comparison_requires_reverse_decks_when_declared(tmp_path):
    a, b, left, right, _ = saved_pair(tmp_path)
    for saved in (left, right):
        saved["both_deck_assignments"] = True
    a.write_text(json.dumps(left))
    b.write_text(json.dumps(right))
    with pytest.raises(ValueError, match="reverse deck assignment"):
        compare_reports(a, b)


def test_comparison_requires_matching_extended_fingerprints_when_recorded(tmp_path):
    a, b, left, right, _ = saved_pair(tmp_path)
    left["card_scripts_sha256"] = "a" * 64
    left["source_code_sha256"] = "b" * 64
    a.write_text(json.dumps(left))
    with pytest.raises(ValueError, match="card_scripts_sha256"):
        compare_reports(a, b)
    right["card_scripts_sha256"] = "c" * 64
    right["source_code_sha256"] = "b" * 64
    b.write_text(json.dumps(right))
    with pytest.raises(ValueError, match="card_scripts_sha256"):
        compare_reports(a, b)
    right["card_scripts_sha256"] = "a" * 64
    b.write_text(json.dumps(right))
    assert compare_reports(a, b)["card_scripts_sha256"] == "a" * 64


def test_unseen_main_deck_comparison_checks_both_training_histories(tmp_path):
    a, b, left, right, _ = saved_pair(tmp_path)
    compositions = {deck: main_deck_composition_sha256(read_ydk(deck))
                    for deck in left["deck_sha256"]}
    for report in (left, right):
        report["main_deck_composition_sha256"] = compositions
        report["training_games"][0]["main_deck_composition_sha256"] = ["c" * 64,
                                                                         "d" * 64]
    a.write_text(json.dumps(left))
    b.write_text(json.dumps(right))
    assert compare_reports(a, b, require_unseen_main_decks=True)[
        "unseen_main_decks_verified"] is True

    right["training_games"][0]["main_deck_composition_sha256"][0] = next(
        iter(compositions.values()))
    b.write_text(json.dumps(right))
    with pytest.raises(ValueError, match="overlaps training"):
        compare_reports(a, b, require_unseen_main_decks=True)

    right["training_games"][0].pop("main_deck_composition_sha256")
    b.write_text(json.dumps(right))
    with pytest.raises(ValueError, match="lacks Main Deck training provenance"):
        compare_reports(a, b, require_unseen_main_decks=True)

    right["training_games"][0]["main_deck_composition_sha256"] = ["c" * 64,
                                                                    "d" * 64]
    right["main_deck_composition_sha256"] = {deck: "e" * 64 for deck in compositions}
    b.write_text(json.dumps(right))
    with pytest.raises(ValueError, match="local Main Deck differs"):
        compare_reports(a, b, require_unseen_main_decks=True)
