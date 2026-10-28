"""Reproduce the earlier GOAT core binary for fingerprinted review replays.

The Meson binary embeds build paths, so rebuilding in a different directory
does not reproduce its SHA-256. This command briefly builds the first-patch
source in the canonical native root, copies the result to an ignored review
root, then restores and recompiles the current source. Do not run it beside
another process starting native duels from the same root.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.setup_native import (
    CORE_FORCED_BATTLE_PATCH,
    CORE_FORCED_BATTLE_PATCH_SHA256,
    CORE_PROCESSOR_FORCED_BATTLE_SHA256,
    CORE_PROCESSOR_GOAT_SHA256,
    SOURCES,
)

REVIEW_CORE_SHA256 = "df1774ae5d2f23e52ec2290bcd23e20713d908404539dfffc8f34e1c853e9a00"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*command: str) -> None:
    subprocess.run(command, check=True)


def rebuild(native_root: Path, output_root: Path, expected_sha256: str) -> None:
    native_root = native_root.resolve()
    output_root = output_root.resolve()
    core = native_root / "core"
    build = native_root / "build"
    if (output_root in (native_root, core, build)
            or core in output_root.parents or build in output_root.parents):
        raise ValueError("review output must be separate from the active build")
    processor = core / "processor.cpp"
    library = native_root / "build/libocgcore.so"
    if output_root.exists():
        raise FileExistsError(f"review output already exists: {output_root}")
    core_commit = subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip()
    if core_commit != SOURCES[0][2]:
        raise ValueError(f"unexpected native core commit: {core_commit}")
    if sha256(CORE_FORCED_BATTLE_PATCH) != CORE_FORCED_BATTLE_PATCH_SHA256:
        raise ValueError("forced-battle patch checksum changed")
    if sha256(processor) != CORE_PROCESSOR_FORCED_BATTLE_SHA256:
        raise ValueError("active native processor differs from the pinned final patch")
    if not library.is_file():
        raise FileNotFoundError(library)
    original_library_sha256 = sha256(library)
    venv_meson = Path(sys.executable).with_name("meson")
    meson = str(venv_meson) if venv_meson.is_file() else shutil.which("meson")
    if meson is None:
        raise FileNotFoundError("meson is unavailable")
    run("git", "-C", str(core), "apply", "--check", "-R", str(CORE_FORCED_BATTLE_PATCH))
    output_root.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix="goat-native-backup-") as temporary:
            backup = Path(temporary)
            shutil.copy2(processor, backup / "processor.cpp")
            shutil.copy2(library, backup / "libocgcore.so")
            try:
                run("git", "-C", str(core), "apply", "-R", str(CORE_FORCED_BATTLE_PATCH))
                if sha256(processor) != CORE_PROCESSOR_GOAT_SHA256:
                    raise ValueError("first-patch native source hash mismatch")
                run(meson, "compile", "-C", str(native_root / "build"), "-j", "4")
                actual = sha256(library)
                if actual != expected_sha256:
                    raise ValueError(f"first-patch library hash {actual} != {expected_sha256}")
                shutil.copytree(core, output_root / "core")
                (output_root / "build").mkdir()
                shutil.copy2(library, output_root / "build/libocgcore.so")
                for name in ("database", "scripts", "banlist"):
                    (output_root / name).symlink_to(native_root / name, target_is_directory=True)
            finally:
                shutil.copy2(backup / "processor.cpp", processor)
                os.utime(processor, None)
                try:
                    run(meson, "compile", "-C", str(native_root / "build"), "-j", "4")
                    if sha256(library) != original_library_sha256:
                        raise ValueError("restored native library hash differs from its original")
                except BaseException:
                    shutil.copy2(backup / "libocgcore.so", library)
                    raise
    except BaseException:
        shutil.rmtree(output_root)
        raise
    print(f"Reproduced review binary {expected_sha256} at {output_root}")
    print(f"Restored active binary {original_library_sha256} at {library}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output-root", type=Path,
                        default=Path(".cache/goat-ai/first_patch_review_native"))
    parser.add_argument("--expected-sha256", default=REVIEW_CORE_SHA256)
    args = parser.parse_args()
    rebuild(args.native_root, args.output_root, args.expected_sha256)


if __name__ == "__main__":
    main()
