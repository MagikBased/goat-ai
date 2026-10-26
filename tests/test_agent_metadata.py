"""Baseline card properties come from public, pinned databases."""

import sqlite3

import pytest

from goat_ai.agents import load_card_facts, load_card_races, load_flip_monster_codes


def test_flip_codes_merge_all_databases_and_exclude_plain_monsters(tmp_path):
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    for name, rows in (
        ("cards.cdb", ((31560081, 0x200021), (49881766, 0x11))),
        ("goat-entries.cdb", ((504700044, 0x200021),)),
        ("cards-unofficial.cdb", ((87621407, 0x200021),)),
    ):
        with sqlite3.connect(database_dir / name) as database:
            database.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY, type INTEGER)")
            database.executemany("INSERT INTO datas VALUES (?, ?)", rows)
    assert load_flip_monster_codes(tmp_path) == {
        31560081, 504700044, 87621407}


def test_flip_metadata_requires_all_pinned_databases(tmp_path):
    with pytest.raises(FileNotFoundError, match="cards.cdb"):
        load_flip_monster_codes(tmp_path)


def test_race_metadata_merges_pinned_databases(tmp_path):
    root = tmp_path / "database"
    root.mkdir()
    for name, rows in (
        ("cards.cdb", ((17881964, 8192), (33184167, 64))),
        ("goat-entries.cdb", ((504700044, 2),)),
        ("cards-unofficial.cdb", ((511000818, 524288),)),
    ):
        with sqlite3.connect(root / name) as database:
            database.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY, race INTEGER)")
            database.executemany("INSERT INTO datas VALUES (?, ?)", rows)
    assert load_card_races(tmp_path)[504700044] == 2
    assert load_card_races(tmp_path)[17881964] == 8192


def test_tactical_facts_include_effect_fusion_level_and_printed_attack(tmp_path):
    root = tmp_path / "database"
    root.mkdir()
    for name, rows in (
        ("cards.cdb", ((4335645, 33, 4, 1200),
                       (17881964, 65, 4, 1500))),
        ("goat-entries.cdb", ((504700102, 97, 1, 0),)),
        ("cards-unofficial.cdb", ()),
    ):
        with sqlite3.connect(root / name) as database:
            database.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY, "
                             "type INTEGER, level INTEGER, atk INTEGER)")
            database.executemany("INSERT INTO datas VALUES (?, ?, ?, ?)", rows)
    facts = load_card_facts(tmp_path)
    assert facts[4335645] == (33, 4, 1200)
    assert facts[17881964] == (65, 4, 1500)
    assert facts[504700102] == (97, 1, 0)
