"""Cache small card images for one GOAT AI trajectory; files stay outside Git."""

import argparse
import json
import sqlite3
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from goat_ai.replay import read_trajectory
from scripts.render_replay import _card_codes

IMAGE_BASE = "https://images.ygoprodeck.com/images/cards_small"


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
        request = Request(f"{IMAGE_BASE}/{aliases.get(code, code)}.jpg",
                          headers={"User-Agent": "goat-ai-local-replay-viewer/0.1"})
        try:
            with urlopen(request, timeout=15) as response:
                data = response.read(2_000_001)
            if not data.startswith(b"\xff\xd8\xff") or len(data) > 2_000_000:
                raise ValueError(f"unexpected image data for card {code}")
            temporary = target.with_suffix(".jpg.tmp")
            temporary.write_bytes(data)
            temporary.replace(target)
            downloaded += 1
        except HTTPError as error:
            if error.code != 404:
                raise
            unavailable += 1
        except URLError:
            raise
        if index < len(codes) - 1:
            time.sleep(delay)
    return downloaded, cached, unavailable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path, nargs="+")
    parser.add_argument("--output-dir", type=Path, default=Path("replays/card_images"))
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    args = parser.parse_args()
    downloaded, cached, unavailable = setup_card_images(
        args.trajectory, args.output_dir, args.native_root)
    print(f"card images: {downloaded} downloaded, {cached} cached, "
          f"{unavailable} unavailable; run render_replay.py --catalog-viewer next")


if __name__ == "__main__":
    main()
