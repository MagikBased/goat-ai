"""The dated banlist parser checks restricted and unrestricted card IDs."""

import sqlite3

from scripts.audit_goat_limits import audit, parse_historical_limits


def test_historical_limit_sections_and_all_id_comparison(tmp_path):
    page = tmp_path / "cardpool.html"
    page.write_text(
        '<div class="paragraph"><strong>Forbidden Cards</strong><br />'
        '<font>Raigeki</font><br /></div>\n'
        '<div class="paragraph"><strong>Limited Cards</strong><br />'
        '<font>Pot of Greed</font><br /></div>\n'
        '<div class="paragraph"><strong>Semi-Limited Cards</strong><br />'
        '<font>Nobleman of Crossout</font><br /></div>\n')
    assert parse_historical_limits(page.read_text()) == {
        "raigeki": ("Raigeki", 0),
        "potofgreed": ("Pot of Greed", 1),
        "noblemanofcrossout": ("Nobleman of Crossout", 2),
    }
    root = tmp_path / "native"
    (root / "banlist").mkdir(parents=True)
    (root / "database").mkdir()
    whitelist = root / "banlist/GOAT.lflist.conf"
    whitelist.write_text("$whitelist\n1 0\n2 1\n3 1\n4 2\n5 3\n")
    for filename in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        with sqlite3.connect(root / "database" / filename) as database:
            database.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT)")
            if filename == "cards.cdb":
                database.executemany("INSERT INTO texts VALUES (?, ?)", (
                    (1, "Raigeki"), (2, "Pot of Greed"),
                    (3, "Pot of Greed"), (4, "Nobleman of Crossout"),
                    (5, "Book of Moon"),
                ))

    report = audit(root, page)
    assert report["source_restricted_names"] == 3
    assert report["whitelist_ids_checked"] == 5
    assert report["source_names_missing_from_whitelist"] == []
    assert report["limit_mismatches"] == []

    whitelist.write_text("$whitelist\n1 0\n2 1\n3 3\n4 2\n5 3\n")
    changed = audit(root, page)
    assert changed["limit_mismatches"] == [
        {"code": 3, "name": "Pot of Greed", "expected": 1, "actual": 3}]
