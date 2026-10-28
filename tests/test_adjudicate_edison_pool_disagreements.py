"""A partial source ledger cannot silently become Edison legality."""

import json

import pytest

from scripts.adjudicate_edison_pool_disagreements import adjudicate


def _inputs(tmp_path):
    report = tmp_path / "comparison.json"
    report.write_text(json.dumps({
        "purpose": "candidate_disagreement_not_edison_legality",
        "api_only_unresolved_ids": [1, 2, 3],
        "api_only_unresolved_with_duel_terminal_1_print_ids": [1],
        "community_only_ids": [4],
    }))
    dt01 = tmp_path / "dt01.tsv"
    dt01.write_text("card_id\tdt01_set_code\tfirst_non_dt_date\tfirst_non_dt_set_code\n"
                    "1\tDT01-EN001\t2010-05-11\tTSHD-EN001\n")
    other = tmp_path / "other.tsv"
    other.write_text("card_id\tassessment\n"
                     "2\tinclude_pre_cutoff_booster\n"
                     "3\tpending_north_america_promo\n")
    return report, dt01, other


def test_adjudication_keeps_unresolved_cards_and_refuses_whitelist(tmp_path):
    result = adjudicate(*_inputs(tmp_path))
    assert result["api_only_excluded_ids"] == [1]
    assert result["api_only_included_ids"] == [2]
    assert result["api_only_pending_ids"] == [3]
    assert result["community_only_pending_ids"] == [4]
    assert result["complete_release_pool"] is False
    assert len(result["candidate_comparison_sha256"]) == 64


def test_adjudication_rejects_missing_or_conflicting_evidence(tmp_path):
    report, dt01, other = _inputs(tmp_path)
    other.write_text("card_id\tassessment\n2\tinclude_pre_cutoff_booster\n")
    with pytest.raises(ValueError, match="exactly cover"):
        adjudicate(report, dt01, other)
    other.write_text("card_id\tassessment\n1\texclude_north_america\n"
                     "2\tinclude_pre_cutoff_booster\n3\tpending_north_america_promo\n")
    with pytest.raises(ValueError, match="exactly cover"):
        adjudicate(report, dt01, other)
    other.write_text("card_id\tassessment\n2\tinclude_pre_cutoff_booster\n"
                     "3\tpending_north_america_promo\n")
    dt01.write_text("card_id\tdt01_set_code\tfirst_non_dt_date\tfirst_non_dt_set_code\n"
                    "1\tDT01-EN001\t2010-04-01\tTSHD-EN001\n")
    with pytest.raises(ValueError, match="pre-cutoff"):
        adjudicate(report, dt01, other)


def test_adjudication_rejects_unrecognized_assessment(tmp_path):
    report, dt01, other = _inputs(tmp_path)
    other.write_text("card_id\tassessment\n2\tlegal_because_api_says_so\n"
                     "3\tpending_north_america_promo\n")
    with pytest.raises(ValueError, match="unknown evidence assessment"):
        adjudicate(report, dt01, other)
