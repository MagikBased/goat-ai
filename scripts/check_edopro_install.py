"""Read-only preflight for an optional local EDOPro GOAT client bridge.

This checks asset presence and byte parity, not room connectivity or rulings.
"""

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_install(edopro_root: Path, native_root: Path) -> dict:
    """Compare known local assets without reading player data or changing files."""
    edopro_root = edopro_root.resolve()
    native_root = native_root.resolve()
    client_core = edopro_root / "libocgcore.so"
    training_core = native_root / "build/libocgcore.so"
    client_db = (edopro_root / "cards.cdb"
                 if (edopro_root / "cards.cdb").is_file()
                 else edopro_root / "expansions/cards.cdb")
    training_db = native_root / "database/cards.cdb"
    if not training_db.is_file():
        training_db = native_root / "cards.cdb"
    client_goat_list = tuple(sorted(
        path.relative_to(edopro_root).as_posix()
        for directory in (edopro_root / "lflists", edopro_root / "expansions")
        if directory.is_dir()
        for path in directory.rglob("*.conf")
        if "goat" in path.name.lower()))
    core_hashes = (_sha256(client_core), _sha256(training_core))
    database_hashes = (_sha256(client_db), _sha256(training_db))
    return {
        "edopro_root": str(edopro_root),
        "client_binary_present": (edopro_root / "EDOPro").is_file(),
        "windbot_binary_present": (edopro_root / "WindBot/WindBot.exe").is_file(),
        "goat_banlists": client_goat_list,
        "client_goat_scripts_present": (edopro_root / "script/goat").is_dir(),
        "client_core_sha256": core_hashes[0],
        "training_core_sha256": core_hashes[1],
        "core_bytes_match": (None if None in core_hashes else
                             core_hashes[0] == core_hashes[1]),
        "client_main_database_sha256": database_hashes[0],
        "training_main_database_sha256": database_hashes[1],
        "main_database_bytes_match": (None if None in database_hashes else
                                      database_hashes[0] == database_hashes[1]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edopro_root", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    args = parser.parse_args()
    print(json.dumps(inspect_install(args.edopro_root, args.native_root), indent=2))


if __name__ == "__main__":
    main()
