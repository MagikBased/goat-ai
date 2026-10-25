"""A negated BLS attack still bars its banish effect in Main Phase 2."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL = 79571449
MAGIC_CYLINDER = 62279055
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_cylinder", [False, True])
def test_bls_cannot_banish_after_attack_was_negated(tmp_path, use_cylinder):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
               f"official/c{MAGIC_CYLINDER}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    attacker = tmp_path / "attacker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
        *(code for code in darks for _ in range(3)), *filler[:26])))
        + "\n#extra\n!side\n")
    defender = tmp_path / "defender.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        MAGIC_CYLINDER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS} <= {c.code for c in obs.hand}
        assert MAGIC_CYLINDER in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = cylinder_set = attacked = responded = False
        costs = set()
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
                if discarded and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    summoned |= action is not None
            if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in ({LIGHT, DARK} - costs)), action)
                if action is not None and action.kind == "select_card":
                    costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1 and not cylinder_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MAGIC_CYLINDER), action)
                cylinder_set |= action is not None and action.kind == "set_spell_trap"
            if obs.turn == 3 and obs.acting_player == 0 and cylinder_set and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or
                                    a.parameters.get("code") == BLS)), action)
                attacked |= action is not None and action.kind == "attack"
            if attacked and obs.acting_player == 1 and not responded:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MAGIC_CYLINDER), None)
                if option is not None:
                    action = option if use_cylinder else next(a for a in actions
                                                               if a.kind == "pass")
                    responded = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")),
                              actions[0])
            obs = env.step(action)
            if responded and obs.turn == 3 and obs.phase == "main2":
                assert costs == {LIGHT, DARK}
                assert any(c.code == BLS and c.position == "faceup" for c in obs.field)
                assert obs.life_points == ((5000, 8000) if use_cylinder
                                           else (8000, 5000))
                assert not any(a.kind == "activate" and a.parameters.get("code") == BLS
                               for a in env.legal_actions())
                assert (MAGIC_CYLINDER in {c.code for c in obs.graveyards[1]}) \
                    == use_cylinder
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua"} <= loaded.keys()
                if use_cylinder:
                    assert f"official/c{MAGIC_CYLINDER}.lua" in loaded
                return
    pytest.fail("BLS / Magic Cylinder line did not reach Main Phase 2")
