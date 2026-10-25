"""Tournament reports detect changes to executable project code."""

from scripts.evaluate_native import card_scripts_sha256, source_code_sha256


def test_source_code_fingerprint_changes_with_adapter_code(tmp_path):
    package = tmp_path / "src/goat_ai/engine"
    package.mkdir(parents=True)
    module = package / "ocgcore_probe.py"
    module.write_text("GOAT_FLAGS = 1\n")
    script = tmp_path / "scripts/evaluate_native.py"
    script.parent.mkdir()
    script.write_text("# tournament evaluator\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'goat-ai'\n")

    original = source_code_sha256(tmp_path)
    assert original == source_code_sha256(tmp_path)
    module.write_text("GOAT_FLAGS = 2\n")
    assert source_code_sha256(tmp_path) != original


def test_card_script_fingerprint_changes_with_lua_bytes(tmp_path):
    scripts = tmp_path / "scripts/official"
    scripts.mkdir(parents=True)
    card = scripts / "c123.lua"
    card.write_text("-- old\n")
    original = card_scripts_sha256(tmp_path)
    card.write_text("-- corrected\n")
    assert card_scripts_sha256(tmp_path) != original
