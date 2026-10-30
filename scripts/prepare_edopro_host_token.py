"""Check or install a local Sheep Token shim for an optional EDOPro host.

The external ygo-agent host treats a missing token script as an error even
though this token has no scripted effect. This writes only a Lua comment, and
only after confirming the external database still marks it as a normal Token.
It does not change GOAT AI's pinned native assets or certify GOAT rulings.
"""

import argparse
import json
import sqlite3
from pathlib import Path

TOKEN_CODE = 73915052
TOKEN_TYPE = 0x4011  # Monster | Normal | Token
SCRIPT = f"c{TOKEN_CODE}.lua"
SHIM = "-- Local compatibility shim for a vanilla Sheep Token.\n"


def prepare(root: Path, *, apply: bool = False) -> dict:
    root = root.resolve()
    database = root / "expansions/cards.cdb"
    scripts = root / "script/official"
    scapegoat = scripts / "c73915051.lua"
    token = scripts / SCRIPT
    if not (root / "libocgcore.so").is_file() or not database.is_file() \
            or not scripts.is_dir() or not scapegoat.is_file():
        raise ValueError("expected an unpacked EDOPro install with core, cards and Scapegoat script")
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT type FROM datas WHERE id=?",
                                 (TOKEN_CODE,)).fetchone()
    if row is None or row[0] != TOKEN_TYPE:
        raise ValueError("Sheep Token's card type differs from the verified normal Token")
    if token.exists():
        if not token.is_file():
            raise ValueError("Sheep Token script path exists but is not a file")
        status = "present"
    elif apply:
        # Exclusive creation prevents overwriting an upstream or user script.
        with token.open("x", encoding="utf-8") as stream:
            stream.write(SHIM)
        status = "created"
    else:
        status = "missing"
    return {"edopro_root": str(root), "sheep_token_script": status,
            "external_host_workaround_only": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edopro_root", type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="create the empty local script if validation passes; never overwrite")
    args = parser.parse_args()
    try:
        result = prepare(args.edopro_root, apply=args.apply)
    except (OSError, sqlite3.Error, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
