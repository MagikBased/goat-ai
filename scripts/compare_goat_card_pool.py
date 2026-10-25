"""Compare a downloaded GoatFormat card-pool CSV with the pinned GOAT whitelist.

The third-party spreadsheet is read locally and never bundled with this project.
This checks card-name membership, not historical rulings or individual copy limits.
"""

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

from goat_ai.engine.decks import read_goat_whitelist

SOURCE_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1MTSrvS9M17woSjMUhqLAQyq7Bb-eLI6hpWd0pRLwHag/export?format=csv"
)

# Printed-name and transcription differences between this spreadsheet and
# the pinned databases. These are explicit equivalences, not fuzzy matching.
SHEET_NAME_EQUIVALENTS = {
    "After the Struggle (F.K.A. After Genocide)": "After the Struggle",
    "Amazoness Archer (F.K.A. Amazon Archer)": "Amazoness Archer",
    "B. Skull Dragon": "Black Skull Dragon",
    "Cemetery Bomb": "Cemetary Bomb",
    "Cyber Soldier of the Darkworld": "Cyber Soldier of Darkworld",
    "Flame Cerberus": "Flame Cerebrus",
    "Kuwagata Alpha": "Kuwagata α",
    "Obnoxious Celtic Guardian": "Obnoxious Celtic Guard",
    "Red-Eyes B. Dragon": "Red-Eyes Black Dragon",
    "Vampire Orchis": "Vampiric Orchis",
}

# These cards are legal by the dated set/promo cutoff even though the linked
# spreadsheet omitted them. The report lists them instead of hiding the delta.
SOURCE_OMISSION_IDS = {28649820, 83258273}


def normalize_name(name: str) -> str:
    name = name.removesuffix(" (GOAT)").removesuffix(" (Pre-Errata)")
    name = unicodedata.normalize("NFKC", name).casefold()
    return re.sub(r"[^a-z0-9]+", "", name)


def compare(native_root: Path, sheet: Path) -> dict:
    sheet_bytes = sheet.read_bytes()
    with sheet.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or "Name" not in reader.fieldnames:
            raise ValueError("card-pool CSV needs a Name column")
        sheet_names: dict[str, str] = {}
        used_equivalents = set()
        for row in reader:
            display_name = row["Name"].strip()
            if not display_name:
                continue
            if display_name in SHEET_NAME_EQUIVALENTS:
                used_equivalents.add(display_name)
            key = normalize_name(SHEET_NAME_EQUIVALENTS.get(display_name, display_name))
            if key in sheet_names:
                raise ValueError(f"duplicate normalized sheet name: {display_name}")
            sheet_names[key] = display_name

    limits = read_goat_whitelist(native_root / "banlist/GOAT.lflist.conf")
    db_path = native_root / "database/cards.cdb"
    whitelist_names: dict[str, list[tuple[int, str]]] = defaultdict(list)
    with sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True) as database:
        for schema, filename in (("goat", "goat-entries.cdb"),
                                 ("unofficial", "cards-unofficial.cdb")):
            database.execute(f"ATTACH DATABASE ? AS {schema}",
                             (str((native_root / "database" / filename).resolve()),))
        for code, limit in limits.items():
            if limit <= 0:
                continue
            name = None
            for schema in ("goat", "main", "unofficial"):
                row = database.execute(
                    f"SELECT name FROM {schema}.texts WHERE id=?", (code,)).fetchone()
                if row is not None:
                    name = row[0]
                    break
            if name is None:
                raise ValueError(f"whitelisted card {code} has no pinned name")
            whitelist_names[normalize_name(name)].append((code, name))

    sheet_only = [sheet_names[key] for key in sorted(sheet_names.keys()
                                                     - whitelist_names.keys())]
    whitelist_only = sorted(
        (code, name) for key in whitelist_names.keys() - sheet_names.keys()
        for code, name in whitelist_names[key])
    unexpected_whitelist_only = [
        (code, name) for code, name in whitelist_only if code not in SOURCE_OMISSION_IDS]
    return {
        "source_url": SOURCE_URL,
        "sheet_sha256": hashlib.sha256(sheet_bytes).hexdigest(),
        "sheet_names": len(sheet_names),
        "whitelist_ids": sum(limit > 0 for limit in limits.values()),
        "whitelist_names": len(whitelist_names),
        "matched_names": len(sheet_names.keys() & whitelist_names.keys()),
        "name_equivalences_used": sorted(used_equivalents),
        "alternate_id_names": {
            whitelist_names[key][0][1].removesuffix(" (GOAT)").removesuffix(" (Pre-Errata)"):
                [code for code, _ in whitelist_names[key]]
            for key in sorted(whitelist_names)
            if len(whitelist_names[key]) > 1
        },
        "sheet_only": sheet_only,
        "whitelist_only": [{"code": code, "name": name}
                           for code, name in whitelist_only],
        "unexpected_whitelist_only": [{"code": code, "name": name}
                                      for code, name in unexpected_whitelist_only],
        "scope": "name membership only; sheet omissions do not change deck legality",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sheet", type=Path, help="downloaded card-pool CSV")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--expect-sheet-sha256", help="reject a changed source snapshot")
    args = parser.parse_args()
    report = compare(args.native_root, args.sheet)
    print(json.dumps(report, indent=2))
    if args.expect_sheet_sha256 and report["sheet_sha256"] != args.expect_sheet_sha256:
        parser.error("card-pool CSV SHA-256 differs from expected snapshot")
    if report["sheet_only"] or report["unexpected_whitelist_only"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
