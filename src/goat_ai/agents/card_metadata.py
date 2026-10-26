"""Public printed card properties for data-driven baseline decisions."""

import sqlite3
from pathlib import Path

FLIP_MONSTER_TYPE = 0x200000  # TYPE_FLIP in pinned ocgcore constant.lua
CARD_DATABASES = ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb")


def load_flip_monster_codes(native_root: str | Path) -> frozenset[int]:
    """Read Flip type from pinned CDBs; never query a duel's hidden state."""
    root = Path(native_root)
    codes = set()
    for name in CARD_DATABASES:
        path = root / "database" / name
        if not path.is_file():
            raise FileNotFoundError(f"card database missing: {path}")
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
            codes.update(code for (code,) in database.execute(
                "SELECT id FROM datas WHERE (type & ?) != 0", (FLIP_MONSTER_TYPE,)))
    return frozenset(codes)


def load_weak_flip_monster_attack(native_root: str | Path,
                                  max_attack: int = 500) -> dict[int, int]:
    """Printed ATK of low-ATK Flip monsters in the pinned card databases."""
    root = Path(native_root)
    attacks: dict[int, int] = {}
    for name in CARD_DATABASES:
        path = root / "database" / name
        if not path.is_file():
            raise FileNotFoundError(f"card database missing: {path}")
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
            attacks.update((code, attack) for code, attack in database.execute(
                "SELECT id, atk FROM datas WHERE (type & ?) != 0 "
                "AND atk BETWEEN 0 AND ?", (FLIP_MONSTER_TYPE, max_attack)))
    return attacks


def load_card_races(native_root: str | Path) -> dict[int, int]:
    """Read printed race by public card ID from the pinned simulator CDBs."""
    root = Path(native_root)
    races: dict[int, int] = {}
    for name in CARD_DATABASES:
        path = root / "database" / name
        if not path.is_file():
            raise FileNotFoundError(f"card database missing: {path}")
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
            races.update((code, race) for code, race in database.execute(
                "SELECT id, race FROM datas WHERE race > 0"))
    return races
