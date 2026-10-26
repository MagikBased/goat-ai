"""Printed card metadata must be independent of duel state."""

import sqlite3

from goat_ai.agents.card_metadata import (
    CARD_DATABASES,
    FLIP_MONSTER_TYPE,
    load_weak_flip_monster_attack,
)


def test_weak_flip_attack_uses_printed_type_and_threshold(tmp_path):
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    for name in CARD_DATABASES:
        with sqlite3.connect(database_dir / name) as database:
            database.execute("CREATE TABLE datas (id INTEGER, type INTEGER, atk INTEGER)")
            if name == "cards.cdb":
                database.executemany("INSERT INTO datas VALUES (?, ?, ?)", [
                    (1, FLIP_MONSTER_TYPE, 300),
                    (2, FLIP_MONSTER_TYPE, 700),
                    (3, 1, 100),
                ])
            if name == "goat-entries.cdb":
                database.execute("INSERT INTO datas VALUES (?, ?, ?)",
                                 (4, FLIP_MONSTER_TYPE, 450))
    assert load_weak_flip_monster_attack(tmp_path) == {1: 300, 4: 450}
    assert load_weak_flip_monster_attack(tmp_path, max_attack=300) == {1: 300}
