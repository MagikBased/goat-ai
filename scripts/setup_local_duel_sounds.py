"""Download pinned EDOPro duel effects to the ignored local cache for personal use."""

import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".cache/goat-ai/duel_sounds"
COMMIT = "54a6e2395c532648ff762540e9615319fac4f51b"
BASE = f"https://raw.githubusercontent.com/ProjectIgnis/Distribution/{COMMIT}/sound"
HASHES = {
    "activate.wav": "d7b123b8ebaab6fa3e8026e170ecc485b5ff6134e5a034cdc92b13cee85f71b4",
    "attack.wav": "84f227e9e74b4a855aa2c38b99fe564cdc8ad69e7cc320d960fd0444b1f176e1",
    "damage.wav": "ba757de3220029971c9e46324448051aafd840f2170e105b587eebc63cdacc04",
    "destroyed.wav": "ee4103709fec62f361b69354ddef90ba22ed7d10ee2cc84f40f275f5489adef3",
    "draw.wav": "d7c1707ca42e62f2c7f27a3ef85ac25c9556632aabf6c7a11905f6dbc584bf9f",
    "equip.wav": "bfe32cb2dcf7e59ebe1c0de1a373d03a2a950f157ef4607ac2ce9116a23d233f",
    "flip.wav": "6a9e36aa1b9773c4d133d24f195f841ae77b4358c645e23b2811dbe3416fa21e",
    "gainlp.wav": "0163c7eeb9896a334cffd8d97d71e20d71e6588ef8c2637ef5c9e5bb605fe4eb",
    "phase.wav": "37553f8c585f05ee814b1a5bf320d86a46630688cb628dadb5452d8e48850bca",
    "set.wav": "2ce8aaf419d0b3fdb161b456c0842173bbfecb804d0950f79735909422aec13b",
    "specialsummon.wav": "3d19682ce0344bb564befc96e6b6d13270aff3d2c87c6d9667d0ead398d3e0b9",
    "summon.wav": "71d9535de615988a1eb5054b3cab3a93a99a37553fd78b4390dc05dcd876a30d",
    "CREDITS.md": "abf9d663f5f052257ec3061cc25736ab3580f95a87cbd9fc98b4231415fc3868",
}


def install(output: Path = OUTPUT) -> tuple[int, int]:
    output.mkdir(parents=True, exist_ok=True)
    downloaded = cached = 0
    for name, expected in HASHES.items():
        target = output / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            cached += 1
            continue
        request = Request(f"{BASE}/{name}",
                          headers={"User-Agent": "goat-ai-local-duel-sounds/0.1"})
        with urlopen(request, timeout=20) as response:
            data = response.read(2_000_001)
        if len(data) > 2_000_000 or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"unexpected sound asset: {name}")
        pending = target.with_suffix(target.suffix + ".tmp")
        pending.write_bytes(data)
        pending.replace(target)
        downloaded += 1
    return downloaded, cached


if __name__ == "__main__":
    new, existing = install()
    print(f"Local EDOPro sounds: {new} downloaded, {existing} already cached in {OUTPUT}")
