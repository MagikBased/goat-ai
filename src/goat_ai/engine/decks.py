"""Strict YDK loading and GOAT whitelist validation before native play."""

import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Decklist:
    main: tuple[int, ...]
    extra: tuple[int, ...] = ()
    side: tuple[int, ...] = ()


def read_ydk(path: str | Path) -> Decklist:
    sections: dict[str, list[int]] = {"main": [], "extra": [], "side": []}
    section = "main"
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line == "#main":
            section = "main"
            continue
        if line == "#extra":
            section = "extra"
            continue
        if line == "!side":
            section = "side"
            continue
        if line.startswith("#"):
            continue  # YDK comments, including '#created by ...'
        if not line.isdecimal():
            raise ValueError(f"invalid YDK card code at line {number}: {line!r}")
        sections[section].append(int(line))
    return Decklist(*(tuple(sections[name]) for name in ("main", "extra", "side")))


def read_goat_whitelist(path: str | Path) -> dict[int, int]:
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    if "$whitelist" not in lines:
        raise ValueError("GOAT list must declare $whitelist")
    limits: dict[int, int] = {}
    for number, raw in enumerate(lines, 1):
        line = raw.split("--", 1)[0].strip()
        if not line or line.startswith(("#", "!", "$")):
            continue
        parts = line.split()
        if len(parts) != 2 or not all(part.isdecimal() for part in parts):
            raise ValueError(f"invalid whitelist entry at line {number}")
        code, limit = map(int, parts)
        if limit not in (0, 1, 2, 3) or (code in limits and limits[code] != limit):
            raise ValueError(f"invalid or duplicate whitelist entry at line {number}")
        limits[code] = limit
    if not limits:
        raise ValueError("empty GOAT whitelist")
    return limits


def validate_goat_deck(deck: Decklist, limits: dict[int, int], database: Path,
                       goat_database: Path | None = None) -> None:
    """Validate list membership/copies; deeper historical card rulings are separate."""
    if not 40 <= len(deck.main) <= 60:
        raise ValueError("GOAT main deck must contain 40 to 60 cards")
    if len(deck.side) > 15:
        raise ValueError("side deck exceeds 15 cards")
    counts: Counter[int] = Counter()
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as connection:
        if goat_database is not None:
            connection.execute("ATTACH DATABASE ? AS goat",
                               (f"file:{goat_database.resolve()}?mode=ro",))
        for zone, cards in (("main", deck.main), ("extra", deck.extra), ("side", deck.side)):
            for code in cards:
                if code not in limits or limits[code] == 0:
                    raise ValueError(f"card {code} is outside the GOAT whitelist or forbidden")
                row = None
                if goat_database is not None:
                    row = connection.execute(
                        "SELECT alias, type FROM goat.datas WHERE id=?", (code,),
                    ).fetchone()
                if row is None:
                    row = connection.execute(
                        "SELECT alias, type FROM main.datas WHERE id=?", (code,),
                    ).fetchone()
                if row is None:
                    raise ValueError(f"card {code} is absent from pinned cards.cdb")
                alias, card_type = row
                is_fusion = bool(card_type & 0x40)
                if zone == "extra" and not is_fusion:
                    raise ValueError(f"card {code} is not a Fusion monster")
                if zone == "main" and is_fusion:
                    raise ValueError(f"Fusion monster {code} cannot be in the main deck")
                canonical = alias or code
                counts[canonical] += 1
                if counts[canonical] > limits[code]:
                    raise ValueError(f"card {code} exceeds GOAT copy limit {limits[code]}")
