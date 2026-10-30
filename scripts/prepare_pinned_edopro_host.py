"""Create an ignored EDOPro-host layout pointing at pinned GOAT native assets."""

import argparse
import json
from pathlib import Path


def prepare(native_root: Path, host_root: Path) -> dict:
    native_root = native_root.resolve()
    host_root = host_root.resolve()
    links = {
        host_root / "libocgcore.so": native_root / "build/libocgcore.so",
        host_root / "script": native_root / "scripts",
        host_root / "expansions/01-unofficial.cdb": native_root / "database/cards-unofficial.cdb",
        host_root / "expansions/02-main.cdb": native_root / "database/cards.cdb",
        host_root / "expansions/03-goat.cdb": native_root / "database/goat-entries.cdb",
        host_root / "lflists/GOAT.lflist.conf": native_root / "banlist/GOAT.lflist.conf",
    }
    for target in links.values():
        if not target.exists():
            raise ValueError(f"native asset is missing: {target}")
    for link, target in links.items():
        if (link.exists() or link.is_symlink()) and (
                not link.is_symlink() or not link.samefile(target)):
            raise ValueError(f"host path already exists and differs: {link}")
    for link, target in links.items():
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.is_symlink():
            link.symlink_to(target)
    return {"host_root": str(host_root), "native_root": str(native_root),
            "linked_assets": len(links)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--host-root", type=Path,
                        default=Path(".cache/goat-ai/edopro_pinned_host"))
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.native_root, args.host_root), indent=2))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
