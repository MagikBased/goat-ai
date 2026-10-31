"""A partial source ledger cannot silently become Edison legality."""

import csv
import json
from pathlib import Path

import pytest

from scripts.adjudicate_edison_pool_disagreements import adjudicate


def _inputs(tmp_path):
    report = tmp_path / "comparison.json"
    report.write_text(json.dumps({
        "purpose": "candidate_disagreement_not_edison_legality",
        "api_only_unresolved_ids": [1, 2, 3],
        "api_only_unresolved_with_duel_terminal_1_print_ids": [1],
        "community_only_ids": [4],
        "shared_canonical_ids": 2,
        "api_canonical_ids": 5,
        "community_canonical_ids": 3,
        "api_only_forbidden_ids": [],
        "api_only_token_ids": [],
        "api_only_missing_metadata_ids": [],
    }))
    dt01 = tmp_path / "dt01.tsv"
    dt01.write_text("card_id\tdt01_set_code\tfirst_non_dt_date\tfirst_non_dt_set_code\n"
                    "1\tDT01-EN001\t2010-05-11\tTSHD-EN001\n")
    other = tmp_path / "other.tsv"
    other.write_text("card_id\tassessment\n"
                     "2\tinclude_pre_cutoff_booster\n"
                     "3\tpending_north_america_promo\n")
    community = tmp_path / "community.tsv"
    community.write_text("card_id\tassessment\n"
                         "4\tpending_north_america_subscription_promo\n")
    return report, dt01, other, community


def test_adjudication_keeps_unresolved_cards_and_refuses_whitelist(tmp_path):
    result = adjudicate(*_inputs(tmp_path))
    assert result["api_only_excluded_ids"] == [1]
    assert result["api_only_included_ids"] == [2]
    assert result["api_only_pending_ids"] == [3]
    assert result["community_only_pending_ids"] == [4]
    assert result["complete_release_pool"] is False
    assert result["shared_candidate_count"] == 2
    assert result["shared_release_audited"] is False
    assert len(result["candidate_comparison_sha256"]) == 64


def test_adjudication_rejects_missing_or_conflicting_evidence(tmp_path):
    report, dt01, other, community = _inputs(tmp_path)
    other.write_text("card_id\tassessment\n2\tinclude_pre_cutoff_booster\n")
    with pytest.raises(ValueError, match="exactly cover"):
        adjudicate(report, dt01, other, community)
    other.write_text("card_id\tassessment\n1\texclude_north_america\n"
                     "2\tinclude_pre_cutoff_booster\n3\tpending_north_america_promo\n")
    with pytest.raises(ValueError, match="exactly cover"):
        adjudicate(report, dt01, other, community)
    other.write_text("card_id\tassessment\n2\tinclude_pre_cutoff_booster\n"
                     "3\tpending_north_america_promo\n")
    dt01.write_text("card_id\tdt01_set_code\tfirst_non_dt_date\tfirst_non_dt_set_code\n"
                    "1\tDT01-EN001\t2010-04-01\tTSHD-EN001\n")
    with pytest.raises(ValueError, match="pre-cutoff"):
        adjudicate(report, dt01, other, community)


def test_adjudication_rejects_unrecognized_assessment(tmp_path):
    report, dt01, other, community = _inputs(tmp_path)
    other.write_text("card_id\tassessment\n2\tlegal_because_api_says_so\n"
                     "3\tpending_north_america_promo\n")
    with pytest.raises(ValueError, match="unknown evidence assessment"):
        adjudicate(report, dt01, other, community)


def test_promo_inclusion_requires_pre_cutoff_north_american_release(tmp_path):
    report, dt01, other, community = _inputs(tmp_path)
    header = "card_id\tassessment\trelease_date\trelease_region\n"
    for release_date, region in (("2010-04-21", "north_america"),
                                 ("2006-08-01", "europe"),
                                 ("unknown", "north_america")):
        other.write_text(header + "2\tinclude_pre_cutoff_booster\t\t\n"
                         + f"3\tinclude_pre_cutoff_promo\t{release_date}\t{region}\n")
        with pytest.raises(ValueError, match="promotional inclusion"):
            adjudicate(report, dt01, other, community)
    other.write_text(header + "2\tinclude_pre_cutoff_booster\t\t\n"
                     "3\tinclude_pre_cutoff_promo\t2006-08-01\tnorth_america\n")
    result = adjudicate(report, dt01, other, community)
    assert result["api_only_included_ids"] == [2, 3]
    assert result["complete_release_pool"] is False


@pytest.mark.parametrize("issue_month,region,accepted", [
    ("2008-01", "north_america", True),
    ("2010-04", "north_america", False),
    ("2010-05", "north_america", False),
    ("2008-01", "europe", False),
    ("2008-13", "north_america", False),
    ("2008", "north_america", False),
])
def test_magazine_issue_inclusion_uses_latest_possible_day(
        tmp_path, issue_month, region, accepted):
    report, dt01, other, community = _inputs(tmp_path)
    other.write_text(
        "card_id\tassessment\tissue_month\trelease_region\n"
        "2\tinclude_pre_cutoff_booster\t\t\n"
        f"3\tinclude_pre_cutoff_magazine_issue\t{issue_month}\t{region}\n")
    if accepted:
        result = adjudicate(report, dt01, other, community)
        assert result["api_only_included_ids"] == [2, 3]
        assert result["complete_release_pool"] is False
    else:
        with pytest.raises(ValueError, match="magazine inclusion"):
            adjudicate(report, dt01, other, community)


def test_adjudication_requires_community_evidence(tmp_path):
    report, dt01, other, community = _inputs(tmp_path)
    community.write_text("card_id\tassessment\n5\tpending_north_america_subscription_promo\n")
    with pytest.raises(ValueError, match="community evidence does not exactly cover"):
        adjudicate(report, dt01, other, community)


@pytest.mark.parametrize("shared", (0, -1, 3, "2"))
def test_adjudication_rejects_invalid_shared_candidate_counts(tmp_path, shared):
    report, dt01, other, community = _inputs(tmp_path)
    payload = json.loads(report.read_text())
    payload["shared_canonical_ids"] = shared
    report.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="shared"):
        adjudicate(report, dt01, other, community)


def test_adjudication_accepts_period_sanctioned_community_card(tmp_path):
    report, dt01, other, community = _inputs(tmp_path)
    community.write_text(
        "card_id\tassessment\tevent_date\tevent_region\n"
        "4\tinclude_pre_cutoff_sanctioned_play\t2010-01-10\tnorth_america\n")
    result = adjudicate(report, dt01, other, community)
    assert result["community_only_included_ids"] == [4]
    assert result["community_only_pending_ids"] == []
    assert result["complete_release_pool"] is False


@pytest.mark.parametrize("event_date,region", [
    ("2010-04-21", "north_america"),
    ("2010-01-10", "europe"),
    ("unknown", "north_america"),
])
def test_adjudication_rejects_unverified_sanctioned_play_date_or_region(
        tmp_path, event_date, region):
    report, dt01, other, community = _inputs(tmp_path)
    community.write_text(
        "card_id\tassessment\tevent_date\tevent_region\n"
        f"4\tinclude_pre_cutoff_sanctioned_play\t{event_date}\t{region}\n")
    with pytest.raises(ValueError, match="sanctioned-play inclusion"):
        adjudicate(report, dt01, other, community)


def test_community_only_ledger_preserves_promotional_provenance():
    path = (Path(__file__).resolve().parents[1] / "configs/historical"
            / "edison_community_only_candidate_discrepancies_2010_04_20.tsv")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = {int(row["card_id"]): row for row in csv.DictReader(stream, delimiter="\t")}
    assert set(rows) == {13893596, 31038159}
    assert rows[13893596]["pre_cutoff_record"].startswith("JUMP-EN025 (May 2008")
    assert rows[31038159]["pre_cutoff_record"].startswith("JUMP-EN034 (March 2010")
    assert rows[13893596]["assessment"] == "pending_north_america_subscription_promo"
    assert rows[31038159]["assessment"] == "include_pre_cutoff_sanctioned_play"
    assert rows[31038159]["event_date"] == "2010-01-10"
    assert rows[31038159]["event_region"] == "north_america"
    assert rows[31038159]["primary_evidence"].startswith(
        "https://yugiohblog.konami.com/2010/sjc/")


def test_yu_jo_friendship_partial_inclusion_keeps_release_provenance():
    path = (Path(__file__).resolve().parents[1] / "configs/historical"
            / "edison_non_dt01_candidate_discrepancies_2010_04_20.tsv")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = {int(row["card_id"]): row for row in csv.DictReader(stream, delimiter="\t")}
    card = rows[81332143]
    assert card["assessment"] == "include_pre_cutoff_promo"
    assert card["release_date"] == "2006-08-01"
    assert card["release_region"] == "north_america"
    assert "Duelist volume 16" in card["pre_cutoff_record"]
    assert card["primary_evidence"].startswith("https://www.db.yugioh-card.com/")
    for code, month in ((62180201, "2008-01"), (57793869, "2007-09")):
        promo = rows[code]
        assert promo["assessment"] == "include_pre_cutoff_magazine_issue"
        assert promo["release_region"] == "north_america"
        assert promo["issue_month"] == month
        assert "provisional" in promo["basis"]
