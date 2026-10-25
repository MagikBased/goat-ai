"""Build an offline, player-visible HTML viewer for a saved JSON trajectory."""

import argparse
import json
import sqlite3
from pathlib import Path

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


def render_replay(source: Path, output: Path, native_root: Path) -> tuple[int, int]:
    """Validate a trajectory and embed only its recorded views in an offline page."""
    trajectory = read_trajectory(source)
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not trajectory.decisions:
        raise ValueError("trajectory contains no decisions to view")
    names = _card_names(_card_codes(raw["decisions"]) |
                        _card_codes(raw.get("terminal_observation")), native_root)
    template = TEMPLATE.read_text(encoding="utf-8")
    # Escaping '<' prevents replay text from closing an embedded script element.
    replay_json = json.dumps(raw, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    names_json = json.dumps(names, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    html = template.replace("__EMBEDDED_REPLAY__", replay_json).replace(
        "__EMBEDDED_NAMES__", names_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return len(trajectory.decisions), len(names)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    args = parser.parse_args()
    output = args.output or args.trajectory.with_suffix(".html")
    decisions, names = render_replay(args.trajectory, output, args.native_root)
    print(f"wrote {output} ({decisions} decisions, {names} card names); open it in a browser")


if __name__ == "__main__":
    main()
