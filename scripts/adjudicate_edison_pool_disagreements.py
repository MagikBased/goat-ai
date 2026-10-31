"""Reconcile documented Edison candidate differences without making a whitelist.

The external candidate report and source-evidence tables remain separate inputs.
This command rejects missing, duplicate, or conflicting assessments, and leaves
community-only cards unresolved until they receive their own evidence.
"""

import argparse
import calendar
import csv
import json
from datetime import date
from pathlib import Path

from goat_ai.replay.fingerprint import sha256_file

CUTOFF = date(2010, 4, 20)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not reader.fieldnames or "card_id" not in reader.fieldnames:
            raise ValueError(f"{path}: missing card_id column")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path}: empty evidence table")
    try:
        ids = [int(row["card_id"]) for row in rows]
    except (TypeError, ValueError) as error:
        raise ValueError(f"{path}: invalid card_id") from error
    if any(code <= 0 for code in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{path}: invalid or duplicate card_id")
    return rows


def adjudicate(report_path: Path, dt01_path: Path,
               non_dt01_path: Path, community_path: Path) -> dict[str, object]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("purpose") != "candidate_disagreement_not_edison_legality":
        raise ValueError("input is not an Edison candidate comparison")
    api_only = set(report["api_only_unresolved_ids"])
    shared_count = report["shared_canonical_ids"]
    if type(shared_count) is not int or shared_count <= 0:
        raise ValueError("candidate comparison has invalid shared count")
    dt01_candidates = set(report["api_only_unresolved_with_duel_terminal_1_print_ids"])
    dt01_rows = _rows(dt01_path)
    other_rows = _rows(non_dt01_path)
    community_rows = _rows(community_path)
    dt01_ids = {int(row["card_id"]) for row in dt01_rows}
    other_ids = {int(row["card_id"]) for row in other_rows}
    if dt01_ids != dt01_candidates:
        raise ValueError("DT01 evidence does not exactly cover DT01 candidate differences")
    if dt01_ids & other_ids or dt01_ids | other_ids != api_only:
        raise ValueError("evidence does not exactly cover API-only candidate differences")

    for row in dt01_rows:
        if not row["dt01_set_code"].startswith("DT01-"):
            raise ValueError("DT01 evidence has a non-DT01 first printing")
        if date.fromisoformat(row["first_non_dt_date"]) <= CUTOFF:
            raise ValueError("DT01 evidence has a pre-cutoff ordinary printing")
        if row["first_non_dt_set_code"].startswith("DT01-"):
            raise ValueError("DT01 evidence has no ordinary printing")

    decisions = {"exclude": set(dt01_ids), "include": set(), "pending": set()}
    for row in other_rows:
        assessment = row["assessment"]
        if assessment not in {
            "include_pre_cutoff_booster", "include_pre_cutoff_promo",
            "include_pre_cutoff_magazine_issue",
            "exclude_north_america",
            "pending_north_america_promo", "pending_cross_territory_video_promo",
        }:
            raise ValueError(f"unknown evidence assessment: {assessment}")
        if assessment == "include_pre_cutoff_promo":
            try:
                release_date = date.fromisoformat(row["release_date"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("promotional inclusion requires a release date") from error
            if release_date > CUTOFF or row.get("release_region") != "north_america":
                raise ValueError("promotional inclusion must predate the North American cutoff")
        if assessment == "include_pre_cutoff_magazine_issue":
            issue = row.get("issue_month", "")
            try:
                if len(issue) != 7 or issue[4] != "-":
                    raise ValueError("invalid issue month")
                first = date.fromisoformat(issue + "-01")
                latest = date(first.year, first.month,
                              calendar.monthrange(first.year, first.month)[1])
            except ValueError as error:
                raise ValueError("magazine inclusion requires a valid issue month") from error
            if latest > CUTOFF or row.get("release_region") != "north_america":
                raise ValueError("magazine inclusion must predate the North American cutoff")
        category = assessment.split("_", 1)[0]
        decisions[category].add(int(row["card_id"]))

    community_only = set(report["community_only_ids"])
    community_evidence_ids = {int(row["card_id"]) for row in community_rows}
    if community_evidence_ids != community_only:
        raise ValueError("community evidence does not exactly cover community-only differences")
    if api_only & community_only:
        raise ValueError("candidate-only sets overlap")
    api_difference_count = sum(len(report[key]) for key in (
        "api_only_forbidden_ids", "api_only_token_ids",
        "api_only_missing_metadata_ids", "api_only_unresolved_ids"))
    if (report["api_canonical_ids"] != shared_count + api_difference_count
            or report["community_canonical_ids"] != shared_count + len(community_only)):
        raise ValueError("shared candidate count conflicts with one-sided differences")
    if set.union(*decisions.values()) != api_only:
        raise ValueError("evidence decisions do not partition API-only differences")
    community_decisions = {"exclude": set(), "include": set(), "pending": set()}
    for row in community_rows:
        if row["assessment"] not in {
            "pending_north_america_subscription_promo",
            "include_pre_cutoff_sanctioned_play",
        }:
            raise ValueError(f"unknown community assessment: {row['assessment']}")
        if row["assessment"] == "include_pre_cutoff_sanctioned_play":
            try:
                event_date = date.fromisoformat(row["event_date"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("sanctioned-play inclusion requires an event date") from error
            if event_date > CUTOFF or row.get("event_region") != "north_america":
                raise ValueError("sanctioned-play inclusion must predate the North American cutoff")
        community_decisions[row["assessment"].split("_", 1)[0]].add(int(row["card_id"]))
    return {
        "purpose": "partial_edison_candidate_disagreement_adjudication_not_whitelist",
        "cutoff": CUTOFF.isoformat(),
        "candidate_comparison_sha256": sha256_file(report_path),
        "shared_candidate_count": shared_count,
        "shared_release_audited": False,
        "dt01_evidence_sha256": sha256_file(dt01_path),
        "other_evidence_sha256": sha256_file(non_dt01_path),
        "community_evidence_sha256": sha256_file(community_path),
        "api_only_excluded_ids": sorted(decisions["exclude"]),
        "api_only_included_ids": sorted(decisions["include"]),
        "api_only_pending_ids": sorted(decisions["pending"]),
        "community_only_excluded_ids": sorted(community_decisions["exclude"]),
        "community_only_included_ids": sorted(community_decisions["include"]),
        "community_only_pending_ids": sorted(community_decisions["pending"]),
        "complete_release_pool": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("dt01_evidence", type=Path)
    parser.add_argument("non_dt01_evidence", type=Path)
    parser.add_argument("community_evidence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = adjudicate(args.comparison, args.dt01_evidence,
                        args.non_dt01_evidence, args.community_evidence)
    body = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    print(body, end="")


if __name__ == "__main__":
    main()
