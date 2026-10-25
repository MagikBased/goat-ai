"""Scapegoat chained to Heavy Storm protects four Sheep Tokens."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

HEAVY_STORM = 19613556
SCAPEGOAT = 504700123
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_chained_scapegoat_resolves_before_heavy_storm(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{HEAVY_STORM}.lua", f"goat/c{SCAPEGOAT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "storm.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        HEAVY_STORM, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "goat.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        goat_set = storm = goat_chained = False
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not goat_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not storm:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY_STORM), action)
                storm |= action is not None and action.kind == "activate"
            if storm and obs.acting_player == 1 and not goat_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_chained |= action is not None and action.kind == "chain"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if goat_chained and HEAVY_STORM in {c.code for c in obs.graveyards[0]}:
                assert SCAPEGOAT in {c.code for c in obs.graveyards[1]}
                tokens = [c for c in obs.field if c.controller == 1
                          and c.code in SHEEP_CODES]
                assert {c.code for c in tokens} == SHEEP_CODES
                assert all(c.position == "faceup" and c.orientation == "defense"
                           for c in tokens)
                assert not any(c.zone == "spell_trap" for c in obs.field)
                assert obs.chain == ()
                assert obs.life_points == (8000, 8000)
                assert f"official/c{HEAVY_STORM}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                assert f"goat/c{SCAPEGOAT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Scapegoat/Heavy Storm chain did not resolve")
