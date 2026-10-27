"""Tournament reports detect changes to executable project code."""

from scripts.evaluate_native import card_scripts_sha256, source_code_sha256
from scripts.evaluate_policy import policy_source_sha256


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


def test_policy_source_fingerprint_changes_with_evaluator_code(tmp_path):
    package = tmp_path / "src/goat_ai/engine"
    package.mkdir(parents=True)
    (package / "ocgcore_probe.py").write_text("GOAT_FLAGS = 1\n")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    policy = scripts / "evaluate_policy.py"
    policy.write_text("# original evaluator\n")
    (scripts / "evaluate_native.py").write_text("# shared hashing code\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'goat-ai'\n")
    before = policy_source_sha256(tmp_path)
    policy.write_text("# corrected evaluator\n")
    assert policy_source_sha256(tmp_path) != before
