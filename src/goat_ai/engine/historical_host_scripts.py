"""Apply the native adapter's verified GOAT script corrections to a room host."""

import hashlib
from pathlib import Path

from goat_ai.engine.ocgcore_probe import GOAT_PATCHED_SCRIPT_PATHS, patch_goat_script


class HistoricalHostScripts:
    """Duck-typed wrapper around an external EDOPro host ScriptLoader.

    The external host owns the duel. This wrapper changes only bytes sent to
    the core; the source checkouts and the EDOPro client files remain intact.
    """

    def __init__(self, loader, pinned_root: str | Path) -> None:
        root = Path(pinned_root).resolve()
        self._loader = loader
        self._scripts = root / "scripts"
        self.dirs = loader.dirs
        self.init_scripts = loader.init_scripts
        if not self._scripts.is_dir():
            raise ValueError("pinned GOAT scripts directory is missing")
        for relative in GOAT_PATCHED_SCRIPT_PATHS:
            source = self._scripts / relative
            if not source.is_file():
                raise ValueError(f"pinned GOAT patch source is missing: {relative}")
            located = loader.find(source.name)
            if located is None or not Path(located).samefile(source):
                raise ValueError(f"host does not resolve pinned GOAT script: {relative}")
            patch_goat_script(relative, source.read_bytes())

    def read(self, name: str) -> bytes | None:
        data = self._loader.read(name)
        if data is None:
            return None
        located = self._loader.find(name)
        if located is None:
            raise ValueError(f"host lost script after loading it: {name}")
        try:
            relative = Path(located).resolve().relative_to(self._scripts.resolve())
        except ValueError as exc:
            raise ValueError(f"host script is outside pinned source: {name}") from exc
        return patch_goat_script(relative.as_posix(), data)


def validate_pinned_host_assets(engine, native_root: str | Path) -> dict[str, str]:
    """Fail closed unless the external host reads the same core, DBs and list."""
    root = Path(native_root).resolve()
    core = root / "build/libocgcore.so"
    databases = (
        root / "database/cards-unofficial.cdb",
        root / "database/cards.cdb",
        root / "database/goat-entries.cdb",
    )
    banlist = root / "banlist/GOAT.lflist.conf"
    if not core.is_file() or not banlist.is_file() or any(not db.is_file() for db in databases):
        raise ValueError("pinned native core, databases or GOAT list are missing")
    if not Path(engine.install.core_path).samefile(core):
        raise ValueError("host core differs from pinned GOAT native core")
    if len(engine.install.cdb_paths) != 3 or any(
            not Path(actual).samefile(expected)
            for actual, expected in zip(engine.install.cdb_paths, databases, strict=True)):
        raise ValueError("host card database precedence differs from native GOAT adapter")
    if len(engine.install.lflist_paths) != 1 or not Path(
            engine.install.lflist_paths[0]).samefile(banlist):
        raise ValueError("host GOAT list differs from pinned native list")
    if isinstance(engine.scripts, HistoricalHostScripts):
        if engine.scripts._scripts.resolve() != (root / "scripts").resolve():
            raise ValueError("host already uses a different pinned script source")
    else:
        engine.scripts = HistoricalHostScripts(engine.scripts, root)
    return {
        "core_sha256": hashlib.sha256(core.read_bytes()).hexdigest(),
        "goat_list_sha256": hashlib.sha256(banlist.read_bytes()).hexdigest(),
    }
