"""Build an offline replay viewer, optionally with verified reviewer-only reveals."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from goat_ai.engine.decks import read_goat_whitelist
from goat_ai.replay import read_trajectory
from goat_ai.replay.verify import verify_trajectory

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


def _option_texts(codes: set[int], native_root: Path) -> dict[int, str]:
    """Resolve ocgcore Stringid(card_id, index) from the local CDB str columns."""
    texts = {}
    for filename in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        path = native_root / "database" / filename
        if not path.is_file():
            continue
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as database:
            columns = {row[1] for row in database.execute("PRAGMA table_info(texts)")}
            slots = [index for index in range(1, 17) if f"str{index}" in columns]
            if not slots:
                continue
            selected = ", ".join(f"str{index}" for index in slots)
            for code in codes:
                row = database.execute(
                    f"SELECT {selected} FROM texts WHERE id=?", (code,)).fetchone()
                if row:
                    texts.update({(code << 20) | (slot - 1): value
                                  for slot, value in zip(slots, row) if value})
    return texts


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


def _local_card_images(output: Path, codes: set[int]) -> dict[int | str, str]:
    """Reference only locally cached art beside the generated HTML."""
    folder = output.parent / "card_images"
    images = {}
    for code in codes:
        for suffix in ("jpg", "jpeg", "png", "webp"):
            if (folder / f"{code}.{suffix}").is_file():
                images[code] = f"card_images/{code}.{suffix}"
                break
    for key, filename in (("back", "cover.png"), ("backOpponent", "cover2.png")):
        if (folder / filename).is_file():
            images[key] = f"card_images/{filename}"
    return images


def _embed_viewer(raw: dict | None, source_sha256: str, names: dict[int, str],
                  options: dict[int, str], images: dict[int | str, str],
                  reviewer: dict | None = None) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    # Escaping '<' prevents replay or database text from closing a script element.
    replay_json = json.dumps(raw, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    names_json = json.dumps(names, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    options_json = json.dumps(options, separators=(",", ":"), ensure_ascii=True).replace(
        "<", "\\u003c")
    images_json = json.dumps(images, separators=(",", ":"), ensure_ascii=True)
    reviewer_json = json.dumps(reviewer, separators=(",", ":"), ensure_ascii=True).replace(
        "<", "\\u003c")
    return (template.replace("__SOURCE_SHA256__", source_sha256)
            .replace("__EMBEDDED_NAMES__", names_json)
            .replace("__EMBEDDED_OPTIONS__", options_json)
            .replace("__EMBEDDED_IMAGES__", images_json)
            .replace("__EMBEDDED_REVIEWER__", reviewer_json)
            .replace("__EMBEDDED_REPLAY__", replay_json))


def _reviewer_frame(engine, *, terminal: bool = False) -> dict:
    """Combine two legitimate player views for offline review, outside the agent API."""
    views = (engine.probe.observation(0, terminal=terminal),
             engine.probe.observation(1, terminal=terminal))
    field = {}
    for view in views:
        for card in view.field:
            if card.code is not None:
                field[f"{card.controller}:{card.zone}:{card.sequence}"] = card.code
    return {
        "hands": [[card.code for card in view.hand] for view in views],
        "field": field,
        "banished": [[card.code for card in view.banished[player]]
                     for player, view in enumerate(views)],
        "extra": [[card.code for card in view.own_extra_deck] for view in views],
        "decks": [list(view.own_main_deck) for view in views],
    }


def _reviewer_data(trajectory, native_root: Path, source_sha256: str,
                   deck_paths: tuple[str | Path, str | Path] | None = None) -> dict:
    from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
    from goat_ai.environments import GoatEnvironment

    paths = deck_paths or trajectory.decks
    # Verification checks the complete recorded observations, actions, decks,
    # result and native asset hashes before any hidden information is exported.
    verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root), paths)
    frames = []
    with GoatEnvironment(str(paths[0]), str(paths[1]), trajectory.seed,
                         ExperimentalOcgcoreEngine(native_root)) as env:
        env.reset()
        for index, record in enumerate(trajectory.decisions):
            frame = _reviewer_frame(env.engine)
            visible = record.observation
            opponent = 1 - visible.viewer
            if len(frame["hands"][opponent]) != visible.opponent_hand_count:
                raise ValueError(f"decision {index}: reviewer hand count differs")
            if any(card.code is None and frame["field"].get(
                    f"{card.controller}:{card.zone}:{card.sequence}") is None
                   for card in visible.field):
                raise ValueError(f"decision {index}: reviewer field identity missing")
            frames.append(frame)
            actions = env.legal_actions()
            env.step(actions[record.legal_actions.index(record.selected_action)])
        if trajectory.terminal_observation is not None:
            frames.append(_reviewer_frame(env.engine, terminal=True))
    return {"schema_version": 1, "source_trajectory_sha256": source_sha256,
            "frames": frames}


def render_replay(source: Path, output: Path, native_root: Path, *,
                  reviewer_reveal: bool = False,
                  deck_paths: tuple[str | Path, str | Path] | None = None) -> tuple[int, int]:
    """Validate a trajectory; reveal hidden cards only in an optional review artifact."""
    trajectory = read_trajectory(source)
    source_bytes = source.read_bytes()
    raw = json.loads(source_bytes)
    if not trajectory.decisions:
        raise ValueError("trajectory contains no decisions to view")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    reviewer = (_reviewer_data(trajectory, native_root, source_sha256, deck_paths)
                if reviewer_reveal else None)
    codes = (_card_codes(raw["decisions"]) |
             _card_codes(raw.get("terminal_observation")))
    if reviewer:
        for frame in reviewer["frames"]:
            codes.update(frame["field"].values())
            for zone in ("hands", "banished", "extra", "decks"):
                codes.update(code for player_cards in frame[zone]
                             for code in player_cards if code is not None)
    codes |= _catalog_codes(native_root)
    names = _card_names(codes, native_root)
    options = _option_texts(codes, native_root)
    html = _embed_viewer(raw, source_sha256, names, options,
                         _local_card_images(output, codes), reviewer)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    if reviewer:
        output.with_suffix(".review.json").write_text(
            json.dumps(reviewer, separators=(",", ":")) + "\n", encoding="utf-8")
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
    output.write_text(_embed_viewer(None, "", names,
                                    _option_texts(codes, native_root),
                                    _local_card_images(output, codes)), encoding="utf-8")
    return len(names)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--catalog-viewer", action="store_true",
                        help="make one offline viewer with names for all GOAT cards")
    parser.add_argument("--reviewer-reveal", action="store_true",
                        help="verify native replay and reveal both players' cards in HTML and a .review.json sidecar")
    parser.add_argument("--deck1", type=Path, help="relocated first YDK for reviewer verification")
    parser.add_argument("--deck2", type=Path, help="relocated second YDK for reviewer verification")
    args = parser.parse_args()
    if args.catalog_viewer:
        if args.trajectory or args.reviewer_reveal or args.deck1 or args.deck2:
            parser.error("--catalog-viewer does not take a trajectory or reviewer options")
        output = args.output or Path("replays/goat_viewer.html")
        names = render_catalog_viewer(output, args.native_root)
        print(f"wrote {output} ({names} GOAT card/Token names); "
              "open it and choose a replay JSON")
        return
    if args.trajectory is None:
        parser.error("provide a trajectory or use --catalog-viewer")
    if bool(args.deck1) != bool(args.deck2):
        parser.error("--deck1 and --deck2 must be supplied together")
    output = args.output or args.trajectory.with_suffix(".html")
    decisions, names = render_replay(
        args.trajectory, output, args.native_root, reviewer_reveal=args.reviewer_reveal,
        deck_paths=(args.deck1, args.deck2) if args.deck1 else None)
    print(f"wrote {output} ({decisions} decisions, {names} card names); open it in a browser")


if __name__ == "__main__":
    main()
