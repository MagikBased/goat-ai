"""Independent card-pool CSV comparison handles aliases and exposes real deltas."""

import sqlite3

from scripts.compare_goat_card_pool import compare


def test_comparison_matches_printed_alias_and_reports_source_omission(tmp_path):
    root = tmp_path / "native"
    (root / "banlist").mkdir(parents=True)
    (root / "database").mkdir()
    (root / "banlist/GOAT.lflist.conf").write_text(
        "$whitelist\n25345186 3\n28649820 3\n77585513 1\n999 0\n")
    for filename in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        with sqlite3.connect(root / "database" / filename) as database:
            database.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT)")
            if filename == "cards.cdb":
                database.executemany("INSERT INTO texts VALUES (?, ?)", (
                    (25345186, "After the Struggle"),
                    (28649820, "Embodiment of Apophis"),
                    (77585513, "Jinzo"),
                ))
    sheet = tmp_path / "pool.csv"
    sheet.write_text("Name\nAfter the Struggle (F.K.A. After Genocide)\n"
                     "Jinzo\nFuture Card\n")

    report = compare(root, sheet)

    assert report["sheet_names"] == 3
    assert report["whitelist_ids"] == 3
    assert report["matched_names"] == 2
    assert report["sheet_only"] == ["Future Card"]
    assert report["whitelist_only"] == [
        {"code": 28649820, "name": "Embodiment of Apophis"}]
    assert report["unexpected_whitelist_only"] == []
    assert report["name_equivalences_used"] == [
        "After the Struggle (F.K.A. After Genocide)"]
