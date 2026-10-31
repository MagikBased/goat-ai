"""The shared DT01 watchlist has individually dated official print evidence."""

import csv
import hashlib
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SOURCE = (Path(__file__).resolve().parents[1] / "configs/historical"
          / "edison_shared_dt01_pre_cutoff_prints_2010_04_20.tsv")
CUTOFF = date(2010, 4, 20)
WATCHLIST_IDS_SHA256 = "802a95766801b2c0bcc5b46ed8ac17239ed9c534998933c58739bc0c9b39e613"


def test_shared_dt01_watchlist_has_pre_cutoff_non_terminal_prints():
    with SOURCE.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    codes = sorted(int(row["card_id"]) for row in rows)
    assert len(rows) == len(set(codes)) == 72
    assert hashlib.sha256(",".join(map(str, codes)).encode()).hexdigest() == (
        WATCHLIST_IDS_SHA256)
    assert len({row["konami_cid"] for row in rows}) == 72
    for row in rows:
        assert row["card_name"].strip()
        assert date.fromisoformat(row["dt01_date"]) == date(2010, 1, 29)
        assert row["dt01_set_code"].startswith("DT01-EN")
        assert date.fromisoformat(row["first_non_terminal_date"]) <= CUTOFF
        assert not row["first_non_terminal_set_code"].startswith(("DT01-", "DTP1-"))
        assert row["first_non_terminal_set_name"].strip()
        assert len(row["official_html_sha256"]) == 64
        int(row["official_html_sha256"], 16)
        url = urlparse(row["konami_card_url"])
        assert url.scheme == "https" and url.netloc == "www.db.yugioh-card.com"
        assert parse_qs(url.query)["cid"] == [row["konami_cid"]]


def test_shared_dt01_alias_and_key_synchro_prints():
    with SOURCE.open(encoding="utf-8", newline="") as stream:
        rows = {row["card_name"]: row for row in csv.DictReader(stream, delimiter="\t")}
    assert rows["Harpie Lady"]["alias_note"].startswith("DT01 printed Harpie Lady 1")
    assert rows["Harpie Lady"]["first_non_terminal_set_code"] == "RDS-EN017"
    assert rows["Ally of Justice Catastor"]["first_non_terminal_set_code"] == "HA01-EN026"
    assert rows["Brionac, Dragon of the Ice Barrier"]["first_non_terminal_set_code"] == "HA01-EN022"
    assert rows["Goyo Guardian"]["first_non_terminal_set_code"] == "TDGS-EN042"
