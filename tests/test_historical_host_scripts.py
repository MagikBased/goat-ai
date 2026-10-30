"""The external host must share the native GOAT script and asset guard."""

import hashlib
import os
from pathlib import Path

import pytest

from goat_ai.engine.ocgcore_probe import GOAT_PATCHED_SCRIPT_PATHS, patch_goat_script
from scripts.prepare_pinned_edopro_host import prepare


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="pinned native assets unavailable")
def test_historical_script_patch_registry_is_checksum_guarded():
    scripts = Path(os.environ["GOAT_AI_NATIVE_ROOT"]) / "scripts"
    for relative in GOAT_PATCHED_SCRIPT_PATHS:
        original = (scripts / relative).read_bytes()
        patched = patch_goat_script(relative, original)
        assert patched != original, relative
        with pytest.raises(ValueError, match="changed"):
            patch_goat_script(relative, original + b"\n-- unexpected edit")
    utility = patch_goat_script("utility.lua", (scripts / "utility.lua").read_bytes())
    assert hashlib.sha256(utility).hexdigest() == (
        "04c4555a7491a6fa958688f270e28a3212255cfbc23e390040cfb18969936b24")


def test_pinned_host_layout_is_idempotent_and_rejects_substitution(tmp_path):
    native = tmp_path / "native"
    for relative in (
            "build/libocgcore.so", "scripts/utility.lua",
            "database/cards-unofficial.cdb", "database/cards.cdb",
            "database/goat-entries.cdb", "banlist/GOAT.lflist.conf"):
        path = native / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    host = tmp_path / "host"
    assert prepare(native, host)["linked_assets"] == 6
    assert prepare(native, host)["linked_assets"] == 6
    (host / "expansions/02-main.cdb").unlink()
    (host / "expansions/02-main.cdb").write_bytes(b"different")
    with pytest.raises(ValueError, match="differs"):
        prepare(native, host)
