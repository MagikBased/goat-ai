"""The preflight must report actual asset mismatches without claiming play works."""

from scripts.check_edopro_install import inspect_install


def test_edopro_preflight_detects_expansion_assets_and_parity(tmp_path) -> None:
    client = tmp_path / "client"
    native = tmp_path / "native"
    for path in (client / "expansions/cards.cdb", client / "libocgcore.so",
                 client / "EDOPro", client / "WindBot/WindBot.exe",
                 client / "script/goat/c1.lua", client / "lflists/GOAT.conf",
                 native / "build/libocgcore.so", native / "database/cards.cdb"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"same")
    report = inspect_install(client, native)
    assert report["client_binary_present"]
    assert report["windbot_binary_present"]
    assert report["goat_banlists"] == ("lflists/GOAT.conf",)
    assert report["client_goat_scripts_present"]
    assert report["core_bytes_match"] is True
    assert report["main_database_bytes_match"] is True
    assert "ready_for_verified_goat_training" not in report
    (client / "libocgcore.so").write_bytes(b"different")
    assert inspect_install(client, native)["core_bytes_match"] is False


def test_edopro_preflight_handles_missing_install(tmp_path) -> None:
    report = inspect_install(tmp_path / "missing", tmp_path / "native")
    assert report["client_binary_present"] is False
    assert report["core_bytes_match"] is None
    assert report["goat_banlists"] == ()
