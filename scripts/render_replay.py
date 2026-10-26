"""Build an offline, player-visible HTML viewer for a saved JSON trajectory."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from goat_ai.engine.decks import read_goat_whitelist
from goat_ai.replay import read_trajectory

TEMPLATE = Path(__file__).resolve().parent.parent / "examples/replay_viewer.html"


def _card_codes(value) -> set[int]:
    """Collect only card IDs already present in the recorded visible decisions."""
    if isinstance(value, list):
        return set().union(*(_card_codes(item) for item in value)) if value else set()
    if not isinstance(value, dict):
        return set()
    codes = {int(code) for key, code in value.items()
             if key in ("code", "card_code") and isinstance(code, int) and code > 0}
    if "codes" in value and isinstance(value["codes"], list):
        codes.update(code for code in value["codes"] if isinstance(code, int) and code > 0)
    if "own_main_deck" in value and isinstance(value["own_main_deck"], list):
        codes.update(code for code in value["own_main_deck"]
                     if isinstance(code, int) and code > 0)
    if ("known_opponent_hand_cards" in value
            and isinstance(value["known_opponent_hand_cards"], list)):
        codes.update(code for code in value["known_opponent_hand_cards"]
                     if isinstance(code, int) and code > 0)
    for item in value.values():
        if isinstance(item, (dict, list)):
            codes.update(_card_codes(item))
    return codes


def _card_names(codes: set[int], native_root: Path) -> dict[int, str]:
    names = {}
    for filename in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        path = native_root / "database" / filename
        if not path.is_file():
            continue
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
            for code in codes:
                row = database.execute("SELECT name FROM texts WHERE id=?", (code,)).fetchone()
                if row and row[0]:
                    names[code] = row[0]
    return names


def _catalog_codes(native_root: Path) -> set[int]:
    """Include legal cards and generated Tokens, without game-specific hidden cards."""
    whitelist = native_root / "banlist/GOAT.lflist.conf"
    if not whitelist.is_file():
        return set()
    codes = {code for code, limit in read_goat_whitelist(whitelist).items() if limit > 0}
    for filename in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        path = native_root / "database" / filename
        if not path.is_file():
            continue
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
            if database.execute("SELECT 1 FROM sqlite_master WHERE name='datas'").fetchone():
                # ocgcore TYPE_TOKEN is 0x4000. Scapegoat's generated Sheep
                # Tokens, for example, are absent from the legal Deck list.
                codes.update(code for (code,) in database.execute(
                    "SELECT id FROM datas WHERE type & 16384 != 0"))
    return codes


def _embed_viewer(raw: dict | None, source_sha256: str, names: dict[int, str]) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    # Escaping '<' prevents replay or database text from closing a script element.
    replay_json = json.dumps(raw, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    names_json = json.dumps(names, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    return (template.replace("__SOURCE_SHA256__", source_sha256)
            .replace("__EMBEDDED_NAMES__", names_json)
            .replace("__EMBEDDED_REPLAY__", replay_json))


def render_replay(source: Path, output: Path, native_root: Path) -> tuple[int, int]:
    """Validate a trajectory and embed only its recorded views in an offline page."""
    trajectory = read_trajectory(source)
    source_bytes = source.read_bytes()
    raw = json.loads(source_bytes)
    if not trajectory.decisions:
        raise ValueError("trajectory contains no decisions to view")
    codes = (_card_codes(raw["decisions"]) |
             _card_codes(raw.get("terminal_observation")))
    names = _card_names(codes | _catalog_codes(native_root), native_root)
    html = _embed_viewer(raw, hashlib.sha256(source_bytes).hexdigest(), names)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return len(trajectory.decisions), len(names)


def render_catalog_viewer(output: Path, native_root: Path) -> int:
    """Build one offline viewer for legal GOAT cards and generated Tokens."""
    codes = _catalog_codes(native_root)
    if not codes:
        raise FileNotFoundError("GOAT whitelist missing; run scripts/setup_native.py first")
    names = _card_names(codes, native_root)
    missing = codes - names.keys()
    if missing:
        raise ValueError(f"card databases lack {len(missing)} GOAT/Token names; "
                         "run scripts/setup_native.py first")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_embed_viewer(None, "", names), encoding="utf-8")
    return len(names)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--catalog-viewer", action="store_true",
                        help="make one offline viewer with names for all GOAT cards")
    args = parser.parse_args()
    if args.catalog_viewer:
        if args.trajectory:
            parser.error("--catalog-viewer does not take a trajectory")
        output = args.output or Path("replays/goat_viewer.html")
        names = render_catalog_viewer(output, args.native_root)
        print(f"wrote {output} ({names} GOAT card/Token names); "
              "open it and choose a replay JSON")
        return
    if args.trajectory is None:
        parser.error("provide a trajectory or use --catalog-viewer")
    output = args.output or args.trajectory.with_suffix(".html")
    decisions, names = render_replay(args.trajectory, output, args.native_root)
    print(f"wrote {output} ({decisions} decisions, {names} card names); open it in a browser")


if __name__ == "__main__":
    main()
