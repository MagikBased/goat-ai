"""Audit every pinned GOAT copy limit against GoatFormat's April 2005 list.

Download the source HTML separately; third-party pages are not committed here.
"""

import argparse
import hashlib
import html
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

from goat_ai.engine.decks import read_goat_whitelist
from scripts.compare_goat_card_pool import normalize_name

SOURCE_URL = "https://www.goatformat.com/cardpool.html"
SECTION_LIMITS = {"Forbidden Cards": 0, "Limited Cards": 1,
                  "Semi-Limited Cards": 2}


def parse_historical_limits(page: str) -> dict[str, tuple[str, int]]:
    """Extract the three named restriction sections from the source page."""
    limits: dict[str, tuple[str, int]] = {}
    for title, limit in SECTION_LIMITS.items():
        match = re.search(
            r"<strong>\s*" + re.escape(title) + r"\s*</strong>(.*?)</div>",
            page, re.DOTALL | re.IGNORECASE)
        if match is None:
            raise ValueError(f"missing {title} section")
        entries = [html.unescape(re.sub(r"<[^>]+>", "", part)).strip()
                   for part in re.split(r"<br\s*/?>", match.group(1),
                                        flags=re.IGNORECASE)]
        entries = [name for name in entries if name]
        if not entries:
            raise ValueError(f"empty {title} section")
        for name in entries:
            key = normalize_name(name)
            if key in limits:
                raise ValueError(f"duplicate restricted card name: {name}")
            limits[key] = (name, limit)
    return limits


def audit(native_root: Path, page_path: Path) -> dict:
    page_bytes = page_path.read_bytes()
    source_limits = parse_historical_limits(page_bytes.decode("utf-8"))
    whitelist = read_goat_whitelist(native_root / "banlist/GOAT.lflist.conf")
    database_path = native_root / "database/cards.cdb"
    checked_names = set()
    mismatches = []
    with sqlite3.connect(f"file:{database_path.resolve()}?mode=ro", uri=True) as db:
        for schema, filename in (("goat", "goat-entries.cdb"),
                                 ("unofficial", "cards-unofficial.cdb")):
            db.execute(f"ATTACH DATABASE ? AS {schema}",
                       (str((native_root / "database" / filename).resolve()),))
        for code, actual in whitelist.items():
            name = None
            for schema in ("goat", "main", "unofficial"):
                row = db.execute(
                    f"SELECT name FROM {schema}.texts WHERE id=?", (code,)).fetchone()
                if row is not None:
                    name = row[0]
                    break
            if name is None:
                raise ValueError(f"whitelisted card {code} has no pinned name")
            key = normalize_name(name)
            checked_names.add(key)
            expected = source_limits.get(key, (name, 3))[1]
            if actual != expected:
                mismatches.append({"code": code, "name": name,
                                   "expected": expected, "actual": actual})
    missing = [source_limits[key][0] for key in sorted(source_limits.keys()
                                                      - checked_names)]
    source_counts = Counter(limit for _, limit in source_limits.values())
    return {
        "source_url": SOURCE_URL,
        "page_sha256": hashlib.sha256(page_bytes).hexdigest(),
        "source_restricted_names": len(source_limits),
        "source_names_by_limit": {str(limit): source_counts[limit]
                                  for limit in (0, 1, 2)},
        "whitelist_ids_checked": len(whitelist),
        "whitelist_ids_by_limit": {str(limit): sum(value == limit
                                                   for value in whitelist.values())
                                   for limit in (0, 1, 2, 3)},
        "source_names_missing_from_whitelist": missing,
        "limit_mismatches": sorted(mismatches, key=lambda row: row["code"]),
        "scope": "copy limits for pinned whitelist IDs; not card effects or release dates",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page", type=Path, help="downloaded GoatFormat card-pool HTML")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--expect-page-sha256", help="reject a changed source snapshot")
    args = parser.parse_args()
    report = audit(args.native_root, args.page)
    print(json.dumps(report, indent=2))
    if args.expect_page_sha256 and report["page_sha256"] != args.expect_page_sha256:
        parser.error("card-pool page SHA-256 differs from expected snapshot")
    if report["source_names_missing_from_whitelist"] or report["limit_mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
