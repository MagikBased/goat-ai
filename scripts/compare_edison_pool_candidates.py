"""Compare two external Edison release-pool candidates without certifying either.

Pass a locally cached YGOPRODeck date-filtered cardinfo JSON response and a
separately obtained community CSV. Neither source file belongs in Git.
"""

import argparse
import csv
import json
import sqlite3
from pathlib import Path

from goat_ai.engine.decks import read_advanced_restrictions
from goat_ai.replay.fingerprint import sha256_file

TOKEN = 0x4000


def _api_ids(path: Path) -> set[int]:
    response = json.loads(path.read_text(encoding="utf-8"))
    rows = response.get("data") if isinstance(response, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("API JSON must contain a nonempty data list")
    ids: set[int] = set()
    for row in rows:
        code = row.get("id") if isinstance(row, dict) else None
        if type(code) is not int or code <= 0 or code in ids:
            raise ValueError("API JSON has an invalid or duplicate card ID")
        ids.add(code)
    return ids


def _community_ids(path: Path) -> set[int]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "id" not in reader.fieldnames:
            raise ValueError("community CSV needs an id column")
        ids: set[int] = set()
        for row in reader:
            try:
                code = int(row["id"])
            except (TypeError, ValueError) as error:
                raise ValueError("community CSV has an invalid card ID") from error
            if code <= 0 or code in ids:
                raise ValueError("community CSV has an invalid or duplicate card ID")
            ids.add(code)
    if not ids:
        raise ValueError("community CSV is empty")
    return ids


def compare(api_json: Path, community_csv: Path, database: Path,
            restrictions: Path) -> dict[str, object]:
    api_ids = _api_ids(api_json)
    community_ids = _community_ids(community_csv)
    limits = read_advanced_restrictions(restrictions)
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as connection:
        metadata = {code: (alias or code, card_type)
                    for code, alias, card_type in connection.execute(
                        "SELECT id, alias, type FROM datas")}
    api_missing = sorted(api_ids - metadata.keys())
    community_missing = sorted(community_ids - metadata.keys())
    api_canonical = {metadata.get(code, (code, 0))[0] for code in api_ids}
    community_canonical = {metadata.get(code, (code, 0))[0]
                           for code in community_ids}
    types = {canonical: card_type for canonical, card_type in metadata.values()}
    api_only = api_canonical - community_canonical
    token_ids = sorted(code for code in api_only if types.get(code, 0) & TOKEN)
    forbidden_ids = sorted(code for code in api_only
                           if code not in token_ids and limits.get(code, 3) == 0)
    missing_metadata_ids = sorted(code for code in api_only if code not in types)
    unresolved_ids = sorted(api_only - set(token_ids) - set(forbidden_ids)
                            - set(missing_metadata_ids))
    return {
        "purpose": "candidate_disagreement_not_edison_legality",
        "api_response_sha256": sha256_file(api_json),
        "community_csv_sha256": sha256_file(community_csv),
        "database_sha256": sha256_file(database),
        "restrictions_sha256": sha256_file(restrictions),
        "api_ids": len(api_ids),
        "community_ids": len(community_ids),
        "api_canonical_ids": len(api_canonical),
        "community_canonical_ids": len(community_canonical),
        "shared_canonical_ids": len(api_canonical & community_canonical),
        "api_ids_missing_database": api_missing,
        "community_ids_missing_database": community_missing,
        "api_only_forbidden_ids": forbidden_ids,
        "api_only_token_ids": token_ids,
        "api_only_missing_metadata_ids": missing_metadata_ids,
        "api_only_unresolved_ids": unresolved_ids,
        "community_only_ids": sorted(community_canonical - api_canonical),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("api_json", type=Path)
    parser.add_argument("community_csv", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("restrictions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(args.api_json, args.community_csv,
                     args.database, args.restrictions)
    body = json.dumps(report, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    print(body, end="")


if __name__ == "__main__":
    main()
