"""The optional external-host workaround must remain narrow and non-destructive."""

import sqlite3

import pytest

from scripts.prepare_edopro_host_token import SHIM, prepare


def _install(tmp_path, *, card_type=0x4011):
    (tmp_path / "expansions").mkdir()
    scripts = tmp_path / "script/official"
    scripts.mkdir(parents=True)
    (tmp_path / "libocgcore.so").write_bytes(b"test")
    (scripts / "c73915051.lua").write_text("-- test", encoding="utf-8")
    with sqlite3.connect(tmp_path / "expansions/cards.cdb") as connection:
        connection.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY, type INTEGER)")
        connection.execute("INSERT INTO datas VALUES (?, ?)", (73915052, card_type))
    return scripts / "c73915052.lua"


def test_optional_token_shim_checks_then_creates_without_overwrite(tmp_path):
    token = _install(tmp_path)
    assert prepare(tmp_path)["sheep_token_script"] == "missing"
    assert not token.exists()
    assert prepare(tmp_path, apply=True)["sheep_token_script"] == "created"
    assert token.read_text(encoding="utf-8") == SHIM
    token.write_text("-- custom upstream script", encoding="utf-8")
    assert prepare(tmp_path, apply=True)["sheep_token_script"] == "present"
    assert token.read_text(encoding="utf-8") == "-- custom upstream script"


def test_token_shim_rejects_changed_card_type_and_incomplete_install(tmp_path):
    _install(tmp_path, card_type=0x4021)
    with pytest.raises(ValueError, match="card type differs"):
        prepare(tmp_path, apply=True)
    assert not (tmp_path / "script/official/c73915052.lua").exists()
    (tmp_path / "script/official/c73915051.lua").unlink()
    with pytest.raises(ValueError, match="expected an unpacked"):
        prepare(tmp_path, apply=True)
