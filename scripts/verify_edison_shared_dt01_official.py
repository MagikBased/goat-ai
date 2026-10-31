"""Recheck the shared DT01 print ledger against current official card pages.

This is a network audit, not a complete North American Edison legality check.
The dated ledger remains the reproducible snapshot if Konami changes its pages.
"""

import argparse
import csv
import hashlib
import html
import re
from pathlib import Path
from urllib.request import Request, urlopen

LEDGER = (Path(__file__).resolve().parents[1] / "configs/historical"
          / "edison_shared_dt01_pre_cutoff_prints_2010_04_20.tsv")
SET_ROW = re.compile(r'<div class="t_row\s+pack_iid_\d+">')
SET_FIELDS = re.compile(
    r'class="time">\s*(\d{4}-\d{2}-\d{2}).*?'
    r'class="card_number">\s*([^<]+).*?'
    r'class="pack_name flex_1"\s*>\s*([^<]+)', re.DOTALL)


def parse_official_sets(body: str) -> set[tuple[str, str, str]]:
    """Extract dated set entries from a Konami card-detail page."""
    sections = SET_ROW.split(body)[1:]
    result = set()
    for section in sections:
        match = SET_FIELDS.search(section)
        if match:
            result.add((match.group(1), html.unescape(match.group(2)).strip(),
                        html.unescape(match.group(3)).strip()))
    return result


def verify(ledger: Path = LEDGER, *, card_id: int | None = None) -> tuple[int, int]:
    with ledger.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    if card_id is not None:
        rows = [row for row in rows if int(row["card_id"]) == card_id]
        if not rows:
            raise ValueError(f"card {card_id} is absent from the shared DT01 ledger")
    changed = 0
    for row in rows:
        request = Request(row["konami_card_url"],
                          headers={"User-Agent": "GOAT-AI historical-source-audit/1.0"})
        with urlopen(request, timeout=20) as response:
            raw = response.read()
        sets = parse_official_sets(raw.decode("utf-8", "replace"))
        expected = {
            (row["dt01_date"], row["dt01_set_code"]),
            (row["first_non_terminal_date"], row["first_non_terminal_set_code"]),
        }
        actual = {(date, code) for date, code, _ in sets}
        missing = expected - actual
        if missing:
            raise ValueError(f"{row['card_name']}: official page no longer shows {sorted(missing)}")
        if hashlib.sha256(raw).hexdigest() != row["official_html_sha256"]:
            changed += 1
        print(f"{row['card_name']}: dated print evidence present")
    return len(rows), changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--card-id", type=int,
                        help="recheck one card; omit to recheck all 72 pages")
    args = parser.parse_args()
    checked, changed = verify(args.ledger, card_id=args.card_id)
    print(f"checked={checked} page_hash_changed={changed}; "
          "print evidence only, not a complete Edison legality decision")


if __name__ == "__main__":
    main()
