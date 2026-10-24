"""Inventory pinned GOAT whitelist metadata and upstream card-script paths."""

import argparse
import json
import sqlite3
import subprocess
from pathlib import Path

from goat_ai.engine.decks import read_goat_whitelist

SCRIPT_DIRS = ("goat", "pre-errata", "official", "unofficial")


def audit(root: Path) -> dict:
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    paths = set(subprocess.check_output(
        ["git", "-C", str(root / "scripts"), "ls-tree", "-r", "--name-only", "HEAD"],
        text=True).splitlines())
    connection = sqlite3.connect(f"file:{(root / 'database/cards.cdb').resolve()}?mode=ro",
                                 uri=True)
    try:
        for schema, filename in (("goat", "goat-entries.cdb"),
                                 ("unofficial", "cards-unofficial.cdb")):
            connection.execute(f"ATTACH DATABASE ? AS {schema}",
                               (f"file:{(root / 'database' / filename).resolve()}?mode=ro",))
        metadata_sources = {"goat": 0, "main": 0, "unofficial": 0}
        missing_metadata = []
        missing_script = []
        direct_scripts = 0
        alias_scripts = 0
        normal_monsters = 0
        for code, limit in limits.items():
            if limit == 0:
                continue
            result = None
            for schema in ("goat", "main", "unofficial"):
                row = connection.execute(f"SELECT alias, type FROM {schema}.datas WHERE id=?",
                                         (code,)).fetchone()
                if row is not None:
                    result = row
                    metadata_sources[schema] += 1
                    break
            if result is None:
                missing_metadata.append(code)
                continue
            alias, card_type = result
            if card_type == 17:
                normal_monsters += 1
                continue
            if any(f"{folder}/c{code}.lua" in paths for folder in SCRIPT_DIRS):
                direct_scripts += 1
            elif alias and any(f"{folder}/c{alias}.lua" in paths for folder in SCRIPT_DIRS):
                alias_scripts += 1
            else:
                missing_script.append(code)
        return {
            "allowed_ids": sum(limit > 0 for limit in limits.values()),
            "metadata_sources": metadata_sources,
            "normal_monsters_without_required_scripts": normal_monsters,
            "direct_script_paths": direct_scripts,
            "alias_script_paths": alias_scripts,
            "missing_metadata": missing_metadata,
            "missing_script_path": missing_script,
            "scope": "asset inventory only; scripts and rulings have not been validated",
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    args = parser.parse_args()
    print(json.dumps(audit(args.native_root), indent=2))


if __name__ == "__main__":
    main()
