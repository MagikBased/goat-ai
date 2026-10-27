import csv
import sqlite3
from pathlib import Path

from scripts.audit_edison_pool import audit


def test_pool_audit_resolves_aliases_and_separates_release_from_restriction(
    tmp_path: Path,
) -> None:
    database = tmp_path / "cards.cdb"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY, alias INTEGER)")
        connection.executemany("INSERT INTO datas VALUES (?, ?)", [
            (10, 0), (11, 10), (20, 0), (30, 0),
        ])
    restrictions = tmp_path / "limits.tsv"
    restrictions.write_text(
        "card_id\tmax_copies\tcard_name\n"
        "10\t1\tAlias card\n"
        "30\t2\tPost-cutoff card\n"
    )
    candidate = tmp_path / "pool.csv"
    with candidate.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerows([
            ("id", "num_copies"),
            (11, 1),  # Alias of restricted card 10
            (20, 3),  # Unrestricted card
            (40, 3),  # No pinned metadata
        ])
    result = audit(candidate, database, restrictions)
    assert result == {
        "candidate_rows": 3,
        "missing_database_ids": [40],
        "copy_limit_mismatches": [],
        "restricted_cards_absent_from_candidate": [30],
    }
