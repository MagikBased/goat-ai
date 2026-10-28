"""Public printed card properties for data-driven baseline decisions."""

import sqlite3
from pathlib import Path

FLIP_MONSTER_TYPE = 0x200000  # TYPE_FLIP in pinned ocgcore constant.lua
CARD_DATABASES = ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb")


def load_card_names(native_root: str | Path) -> dict[int, str]:
    """Read static printed names for a human interface, never duel state."""
    root = Path(native_root)
    names: dict[int, str] = {}
    for name in CARD_DATABASES:
        path = root / "database" / name
        if not path.is_file():
            raise FileNotFoundError(f"card database missing: {path}")
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
            names.update((code, title) for code, title in database.execute(
                "SELECT id, name FROM texts"))
    return names


def load_card_properties(native_root: str | Path,
                         codes: set[int]) -> dict[int, tuple[int, int]]:
    """Read printed Type and ATK for allowed cards from pinned databases.

    Properties are static card text, so using them for a known card identity
    does not disclose anything about an opponent's hidden cards.
    """
    root = Path(native_root)
    properties: dict[int, tuple[int, int]] = {}
    for name in CARD_DATABASES:
        path = root / "database" / name
        if not path.is_file():
            raise FileNotFoundError(f"card database missing: {path}")
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
            properties.update((code, (card_type, attack))
                              for code, card_type, attack in database.execute(
                                  "SELECT id, type, atk FROM datas") if code in codes)
    return properties


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


def load_card_facts(native_root: str | Path) -> dict[int, tuple[int, int, int]]:
    """Read printed Type, Level, and ATK without consulting a duel's state."""
    root = Path(native_root)
    facts: dict[int, tuple[int, int, int]] = {}
    for name in CARD_DATABASES:
        path = root / "database" / name
        if not path.is_file():
            raise FileNotFoundError(f"card database missing: {path}")
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
            facts.update((code, (card_type, level & 0xff, attack))
                         for code, card_type, level, attack in database.execute(
                             "SELECT id, type, level, atk FROM datas"))
    return facts
