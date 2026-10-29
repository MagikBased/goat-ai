"""Cache small card images for one GOAT AI trajectory; files stay outside Git."""

import argparse
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from goat_ai.replay import read_trajectory
from scripts.render_replay import _card_codes

IMAGE_BASE = "https://images.ygoprodeck.com/images/cards_small"
COVER_COMMIT = "54a6e2395c532648ff762540e9615319fac4f51b"
COVER_BASE = f"https://raw.githubusercontent.com/ProjectIgnis/Distribution/{COVER_COMMIT}/textures"
COVER_FILES = {
    "cover.png": "67479d49ab1abe3b9e0669634db4493aaeaf5e3b22b4ceba5725ec3c9469ca3e",
    "cover2.png": "4aeab387b87507eb79e98d2a6a78b6d37dbfe79804405dbe8b30dfc666ad31f3",
}


def _image_aliases(codes: list[int], native_root: Path) -> dict[int, int]:
    """Historical script variant IDs use the base card's printed artwork."""
    result = {}
    for filename in ("goat-entries.cdb", "cards-unofficial.cdb"):
        path = native_root / "database" / filename
        if not path.is_file():
            continue
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        try:
            for code in codes:
                row = connection.execute("SELECT alias FROM datas WHERE id=?", (code,)).fetchone()
                if row and row[0] > 0:
                    result[code] = row[0]
        finally:
            connection.close()
    return result


def cache_card_image(code: int, output_dir: Path, native_root: Path,
                     alias: int | None = None) -> bool:
    """Cache one printed card face; return False when the source has no image."""
    target = output_dir / f"{code}.jpg"
    if target.is_file():
        return True
    printed_id = alias if alias is not None else _image_aliases([code], native_root).get(code, code)
    request = Request(f"{IMAGE_BASE}/{printed_id}.jpg",
                      headers={"User-Agent": "goat-ai-local-replay-viewer/0.1"})
    try:
        with urlopen(request, timeout=15) as response:
            data = response.read(2_000_001)
    except HTTPError as error:
        if error.code == 404:
            return False
        raise
    if not data.startswith(b"\xff\xd8\xff") or len(data) > 2_000_000:
        raise ValueError(f"unexpected image data for card {code}")
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".jpg.tmp")
    temporary.write_bytes(data)
    temporary.replace(target)
    return True


def setup_card_images(trajectory: Path | list[Path], output_dir: Path, native_root: Path,
                      delay: float = 0.5) -> tuple[int, int, int]:
    """Download once per visible card ID; return downloaded, cached, unavailable."""
    paths = [trajectory] if isinstance(trajectory, Path) else trajectory
    visible_codes = set()
    for path in paths:
        read_trajectory(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        visible_codes.update(_card_codes(raw["decisions"]))
        visible_codes.update(_card_codes(raw.get("terminal_observation")))
    codes = sorted(visible_codes)
    aliases = _image_aliases(codes, native_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = cached = unavailable = 0
    for index, code in enumerate(codes):
        target = output_dir / f"{code}.jpg"
        if target.is_file():
            cached += 1
            continue
        if cache_card_image(code, output_dir, native_root,
                            alias=aliases.get(code, code)):
            downloaded += 1
        else:
            unavailable += 1
        if index < len(codes) - 1:
            time.sleep(delay)
    return downloaded, cached, unavailable


def setup_card_backs(output_dir: Path) -> tuple[int, int]:
    """Cache the two pinned EDOPro cover textures outside the repository."""
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = cached = 0
    for filename, digest in COVER_FILES.items():
        target = output_dir / filename
        if target.is_file():
            cached += 1
            continue
        request = Request(f"{COVER_BASE}/{filename}",
                          headers={"User-Agent": "goat-ai-local-replay-viewer/0.1"})
        with urlopen(request, timeout=15) as response:
            data = response.read(2_000_001)
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"unexpected EDOPro cover data for {filename}")
        temporary = target.with_suffix(".png.tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
        downloaded += 1
    return downloaded, cached


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path, nargs="*")
    parser.add_argument("--output-dir", type=Path, default=Path("replays/card_images"))
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--card-back-only", action="store_true")
    args = parser.parse_args()
    if not args.trajectory and not args.card_back_only:
        parser.error("provide one or more trajectories, or use --card-back-only")
    if args.trajectory and not args.card_back_only:
        downloaded, cached, unavailable = setup_card_images(
            args.trajectory, args.output_dir, args.native_root)
        print(f"card faces: {downloaded} downloaded, {cached} cached, "
              f"{unavailable} unavailable")
    downloaded, cached = setup_card_backs(args.output_dir)
    print(f"card backs: {downloaded} downloaded, {cached} cached; "
          "run render_replay.py --catalog-viewer next")


if __name__ == "__main__":
    main()
