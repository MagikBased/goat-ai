"""Check the source-backed North American DT01 release-exclusion asset."""

import csv
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SOURCE = (Path(__file__).resolve().parents[1] / "configs/historical"
          / "edison_dt01_new_card_exclusions_2010_04_20.tsv")
CUTOFF = date(2010, 4, 20)


def test_dt01_new_card_exclusions_have_dated_official_print_evidence():
    with SOURCE.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    assert len(rows) == 28
    assert len({row["card_id"] for row in rows}) == len(rows)
    assert len({row["konami_cid"] for row in rows}) == len(rows)
    for row in rows:
        assert int(row["card_id"]) > 0
        assert row["card_name"].strip()
        assert date.fromisoformat(row["dt01_date"]) == date(2010, 1, 29)
        assert row["dt01_set_code"].startswith("DT01-EN")
        assert date.fromisoformat(row["first_non_dt_date"]) > CUTOFF
        assert not row["first_non_dt_set_code"].startswith("DT01-")
        url = urlparse(row["konami_card_url"])
        assert url.scheme == "https"
        assert url.netloc == "www.db.yugioh-card.com"
        assert parse_qs(url.query)["cid"] == [row["konami_cid"]]


def test_dt01_examples_span_multiple_post_cutoff_products():
    with SOURCE.open(encoding="utf-8", newline="") as stream:
        rows = {row["card_name"]: row for row in csv.DictReader(stream, delimiter="\t")}
    assert rows["Genex Undine"]["first_non_dt_set_code"] == "TSHD-EN091"
    assert rows["X-Saber Wayne"]["first_non_dt_set_code"] == "5DS3-EN042"
    assert rows["Mist Valley Watcher"]["first_non_dt_set_code"] == "GLD3-EN001"
