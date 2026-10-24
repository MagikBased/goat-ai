"""Fetch pinned external assets and build ocgcore for the M0 probe (Linux)."""

import argparse
import hashlib
import platform
import shutil
import subprocess
from pathlib import Path

SOURCES = (
    ("core", "https://github.com/edo9300/ygopro-core.git",
     "baa3881d0bae48e9994f915f5c931be53c1ba8ef"),
    ("scripts", "https://github.com/ProjectIgnis/CardScripts.git",
     "196eb043514e2cbc23ff891e3cfe31b89765ce49"),
    ("database", "https://github.com/ProjectIgnis/BabelCDB.git",
     "19339149fa5ee509327023f15a81d8ba4164c5a1"),
    ("banlist", "https://github.com/ProjectIgnis/LFLists.git",
     "b95e30d7453bb9e692a08ae3081aeceb70582341"),
)
DATABASE_SHA256 = "d5166c35296a6c65dcc0230c7bc0e9f25721639159b80fa78bf724be61183a6a"
GOAT_DATABASE_SHA256 = "042ffc3de692245d13d144656a79a34cb114d291ddd0c93a21bee9c0e607b4b4"
UNOFFICIAL_DATABASE_SHA256 = "7753f01785fbf174be2ec3833610306b02a8ce2cb45ac09339ea50afe164bb6a"
GOAT_LIST_SHA256 = "2159b6eb0868816860c4913571b514c27fd777755a09c358f250e6cc7cc5db37"


def run(*args: str) -> None:
    print("+", *args, flush=True)
    subprocess.run(args, check=True)


def fetch(root: Path, name: str, url: str, revision: str) -> Path:
    path = root / name
    if not path.exists():
        args = ["git", "clone", "--filter=blob:none"]
        if name != "core":
            args.append("--sparse")
        run(*args, url, str(path))
    current = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    if current != revision:
        run("git", "-C", str(path), "checkout", revision)
    if name == "core":
        run("git", "-C", str(path), "submodule", "update", "--init", "--depth", "1")
    elif name == "scripts":
        run("git", "-C", str(path), "sparse-checkout", "set", "--no-cone",
            "/*.lua", "/unofficial/proc_unofficial.lua",
            "/official/c55144522.lua", "/official/c14087893.lua",
            "/official/c11384280.lua",
            "/goat/c504700116.lua", "/pre-errata/c511001039.lua")
    elif name == "banlist":
        run("git", "-C", str(path), "sparse-checkout", "set", "--no-cone",
            "/GOAT.lflist.conf")
    else:
        run("git", "-C", str(path), "sparse-checkout", "set", "--no-cone",
            "/cards.cdb", "/goat-entries.cdb", "/cards-unofficial.cdb")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    args = parser.parse_args()
    if platform.system() != "Linux":
        raise SystemExit("M0 native setup has only been verified on Linux")
    if not shutil.which("meson"):
        raise SystemExit("meson missing; install with pip install -e '.[native]'")
    root = args.native_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    paths = {name: fetch(root, name, url, revision) for name, url, revision in SOURCES}
    actual_hash = hashlib.sha256((paths["database"] / "cards.cdb").read_bytes()).hexdigest()
    if actual_hash != DATABASE_SHA256:
        raise SystemExit(f"database checksum mismatch: {actual_hash}")
    goat_hash = hashlib.sha256((paths["database"] / "goat-entries.cdb").read_bytes()).hexdigest()
    if goat_hash != GOAT_DATABASE_SHA256:
        raise SystemExit(f"GOAT entries database checksum mismatch: {goat_hash}")
    unofficial_hash = hashlib.sha256((paths["database"] / "cards-unofficial.cdb").read_bytes()).hexdigest()
    if unofficial_hash != UNOFFICIAL_DATABASE_SHA256:
        raise SystemExit(f"unofficial database checksum mismatch: {unofficial_hash}")
    list_hash = hashlib.sha256((paths["banlist"] / "GOAT.lflist.conf").read_bytes()).hexdigest()
    if list_hash != GOAT_LIST_SHA256:
        raise SystemExit(f"GOAT whitelist checksum mismatch: {list_hash}")
    build = root / "build"
    if not (build / "build.ninja").exists():
        run("meson", "setup", str(build), str(paths["core"]), "-Ddefault_library=shared")
    run("meson", "compile", "-C", str(build), "-j", "4")
    print(f"Native probe assets ready at {root}")


if __name__ == "__main__":
    main()
