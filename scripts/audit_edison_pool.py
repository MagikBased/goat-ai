"""Compare an external Edison card-pool candidate with pinned card metadata.

No candidate data is bundled or accepted as authoritative by this script.
"""

import argparse
import csv
import json
import sqlite3
from pathlib import Path

from goat_ai.engine.decks import read_advanced_restrictions


def audit(candidate: Path, database: Path, restrictions: Path) -> dict[str, object]:
    limits = read_advanced_restrictions(restrictions)
    with candidate.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"id", "num_copies"}.issubset(reader.fieldnames):
            raise ValueError("candidate CSV requires id and num_copies columns")
        rows = list(reader)
    seen_ids: set[int] = set()
    represented: set[int] = set()
    missing: list[int] = []
    mismatches: list[dict[str, int]] = []
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as connection:
        for row in rows:
            try:
                card_id = int(row["id"])
                candidate_cap = int(row["num_copies"])
            except (TypeError, ValueError) as error:
                raise ValueError("candidate has a nonnumeric ID or copy limit") from error
            if card_id <= 0 or candidate_cap not in (0, 1, 2, 3) or card_id in seen_ids:
                raise ValueError(f"invalid or duplicate candidate card ID: {card_id}")
            seen_ids.add(card_id)
            data = connection.execute("SELECT alias FROM datas WHERE id=?", (card_id,)).fetchone()
            if data is None:
                missing.append(card_id)
                continue
            canonical = data[0] or card_id
            represented.add(canonical)
            official_cap = limits.get(canonical, 3)
            if candidate_cap != official_cap:
                mismatches.append({"id": card_id, "candidate": candidate_cap,
                                   "official_restriction": official_cap})
    absent_restricted = sorted(card_id for card_id, cap in limits.items()
                               if cap > 0 and card_id not in represented)
    return {
        "candidate_rows": len(rows),
        "missing_database_ids": sorted(missing),
        "copy_limit_mismatches": mismatches,
        "restricted_cards_absent_from_candidate": absent_restricted,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="external CSV, kept outside Git")
    parser.add_argument("database", type=Path, help="pinned Project Ignis cards.cdb")
    parser.add_argument("restrictions", type=Path, help="Konami March 2010 restriction TSV")
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.database, args.restrictions), indent=2))


if __name__ == "__main__":
    main()
