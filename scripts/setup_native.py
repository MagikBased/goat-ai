"""Fetch pinned external assets and build ocgcore for the M0 probe (Linux)."""

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
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
CORE_PROCESSOR_UPSTREAM_SHA256 = "083b4da8e33f22890d186c7d19ebbcf0113aa4c89d59e30f73cef0d2dd8cda90"
CORE_PROCESSOR_GOAT_SHA256 = "544f99bb3e8f3148c6abe17a01b0d8cde27466ccaba062b6a9c815edff9bf3b5"
CORE_SEGOC_PATCH = Path(__file__).resolve().parent / "native_patches/0001-goat-cross-controller-segoc.patch"
CORE_SEGOC_PATCH_SHA256 = "fb2bc9fde96863af230085c1b03aa444fa75145b81eb20479620d18fd2126aef"
CORE_PROCESSOR_FORCED_BATTLE_SHA256 = "eae85af2da638d227b2f992f3d200d2ecc0ff16110e66e2e7faf3da47a148f01"
CORE_FORCED_BATTLE_PATCH = (Path(__file__).resolve().parent
                            / "native_patches/0002-goat-forced-battle-interrupted-attack.patch")
CORE_FORCED_BATTLE_PATCH_SHA256 = "6fea71d5a9af520738aa6cac5d33623a8c9c9c04607bdcf8d75221c9f4e698cf"


def run(*args: str) -> None:
    print("+", *args, flush=True)
    subprocess.run(args, check=True)


def apply_goat_core_patch(core: Path) -> None:
    """Apply checksum-verified GOAT native corrections, or verify them."""
    patch_hash = hashlib.sha256(CORE_SEGOC_PATCH.read_bytes()).hexdigest()
    if patch_hash != CORE_SEGOC_PATCH_SHA256:
        raise SystemExit(f"GOAT core patch checksum mismatch: {patch_hash}")
    forced_patch_hash = hashlib.sha256(CORE_FORCED_BATTLE_PATCH.read_bytes()).hexdigest()
    if forced_patch_hash != CORE_FORCED_BATTLE_PATCH_SHA256:
        raise SystemExit(f"GOAT forced-battle patch checksum mismatch: {forced_patch_hash}")
    processor = core / "processor.cpp"
    current_hash = hashlib.sha256(processor.read_bytes()).hexdigest()
    if current_hash == CORE_PROCESSOR_FORCED_BATTLE_SHA256:
        return
    if current_hash == CORE_PROCESSOR_UPSTREAM_SHA256:
        run("git", "-C", str(core), "apply", str(CORE_SEGOC_PATCH))
        current_hash = hashlib.sha256(processor.read_bytes()).hexdigest()
    if current_hash != CORE_PROCESSOR_GOAT_SHA256:
        raise SystemExit(f"unexpected native processor.cpp checksum: {current_hash}")
    run("git", "-C", str(core), "apply", str(CORE_FORCED_BATTLE_PATCH))
    patched_hash = hashlib.sha256(processor.read_bytes()).hexdigest()
    if patched_hash != CORE_PROCESSOR_FORCED_BATTLE_SHA256:
        raise SystemExit(f"GOAT core patch produced unexpected checksum: {patched_hash}")


def fetch(root: Path, name: str, url: str, revision: str,
          full_card_scripts: bool = False) -> Path:
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
        if full_card_scripts:
            run("git", "-C", str(path), "sparse-checkout", "set", "--no-cone",
                "/*.lua", "/official/*", "/unofficial/*", "/goat/*",
                "/pre-errata/*")
        else:
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
    parser.add_argument("--full-card-scripts", action="store_true",
                        help="fetch all pinned card scripts for experimental deck probes")
    args = parser.parse_args()
    if platform.system() != "Linux":
        raise SystemExit("M0 native setup has only been verified on Linux")
    venv_meson = Path(sys.executable).with_name("meson")
    meson = str(venv_meson) if venv_meson.is_file() else shutil.which("meson")
    if meson is None:
        raise SystemExit("meson missing; install with pip install -e '.[native]'")
    root = args.native_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    paths = {name: fetch(root, name, url, revision, args.full_card_scripts)
             for name, url, revision in SOURCES}
    apply_goat_core_patch(paths["core"])
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
        run(meson, "setup", str(build), str(paths["core"]), "-Ddefault_library=shared")
    run(meson, "compile", "-C", str(build), "-j", "4")
    print(f"Native probe assets ready at {root}")


if __name__ == "__main__":
    main()
