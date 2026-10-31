"""Independent release-pool candidates keep their disagreements explicit."""

import json
import sqlite3

import pytest

from scripts.compare_edison_pool_candidates import compare


def test_candidate_comparison_resolves_aliases_and_exposes_disagreements(tmp_path):
    database = tmp_path / "cards.cdb"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE datas (id INTEGER, alias INTEGER, type INTEGER)")
        connection.executemany("INSERT INTO datas VALUES (?, ?, ?)", [
            (1, 0, 1), (2, 1, 1), (3, 0, 1), (4, 0, 0x4000),
            (5, 0, 1), (6, 0, 1),
        ])
    restrictions = tmp_path / "limits.tsv"
    restrictions.write_text("card_id\tmax_copies\tcard_name\n3\t0\tForbidden\n")
    api = tmp_path / "api.json"
    api.write_text(json.dumps({"data": [
        {"id": code, **({"card_sets": [{"set_name": "Duel Terminal 1"}]}
                      if code in (2, 5) else {})}
        for code in (1, 2, 3, 4, 5, 7)]}))
    community = tmp_path / "community.csv"
    community.write_text("id,num_copies\n1,3\n6,3\n8,3\n")

    report = compare(api, community, database, restrictions)
    assert report["purpose"] == "candidate_disagreement_not_edison_legality"
    assert report["jurisdiction_status"] == "not_established_by_candidate_sources"
    assert (report["api_canonical_ids"], report["community_canonical_ids"],
            report["shared_canonical_ids"]) == (5, 3, 1)
    assert report["api_ids_missing_database"] == [7]
    assert report["community_ids_missing_database"] == [8]
    assert report["api_only_forbidden_ids"] == [3]
    assert report["api_only_token_ids"] == [4]
    assert report["api_only_missing_metadata_ids"] == [7]
    assert report["api_only_unresolved_ids"] == [5]
    assert report["api_only_unresolved_with_duel_terminal_1_print_ids"] == [5]
    assert report["shared_with_duel_terminal_1_print_ids"] == [1]
    assert report["community_only_ids"] == [6, 8]

    api.write_text(json.dumps({"data": [{"id": 1}, {"id": 1}]}))
    with pytest.raises(ValueError, match="duplicate"):
        compare(api, community, database, restrictions)
    api.write_text(json.dumps({"data": [{"id": 1, "card_sets": "Duel Terminal 1"}]}))
    with pytest.raises(ValueError, match="card_sets"):
        compare(api, community, database, restrictions)
