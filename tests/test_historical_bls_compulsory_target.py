"""Returning BLS's target to hand stops its pending banish effect."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL = 79571449
COMPULSORY = 94192409
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("respond", [False, True])
def test_compulsory_removes_bls_banish_target_before_resolution(tmp_path, respond):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
               f"official/c{COMPULSORY}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    bls_deck = tmp_path / "bls.ydk"
    bls_deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
        *(code for code in darks for _ in range(3)), *filler[:26])))
        + "\n#extra\n!side\n")
    compulsory_deck = tmp_path / "compulsory.ydk"
    compulsory_deck.write_text("#main\n" + "\n".join(map(str, (
        *([COMPULSORY] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(bls_deck), str(compulsory_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS} <= {c.code for c in obs.hand}
        assert COMPULSORY in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = monster_summoned = compulsory_set = False
        activated = targeted = response_made = compulsory_targeted = False
        costs = set()
        monster_code = None
        for _ in range(110):
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
            if obs.turn == 2 and obs.acting_player == 1:
                if not monster_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        monster_code = action.parameters["code"]
                        monster_summoned = True
                if monster_summoned and not compulsory_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == COMPULSORY), None)
                    compulsory_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and compulsory_set:
                if not activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BLS), None)
                    activated |= action is not None
                if activated and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == monster_code and a.parameters.get("controller") == 1), None)
                    targeted = action is not None
            if targeted and obs.acting_player == 1 and not response_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == COMPULSORY), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [BLS]
                    action = option if respond else next(a for a in actions
                                                        if a.kind == "pass")
                    response_made = True
            if response_made and respond and not compulsory_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == monster_code and a.parameters.get("controller") == 1), None)
                compulsory_targeted = action is not None
                if compulsory_targeted:
                    assert [link.card_code for link in obs.chain] == [BLS, COMPULSORY]
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                              actions[0])
            obs = env.step(action)
            if response_made and (not respond or compulsory_targeted) and not obs.chain \
                    and obs.turn == 3 and BLS in {c.code for c in obs.field}:
                loaded = env.engine.probe.loaded_script_sha256
                if respond:
                    assert scripts <= loaded.keys()
                else:
                    assert {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua"} <= loaded.keys()
                assert {LIGHT, DARK} <= {c.code for c in obs.banished[0]}
                assert any(c.code == BLS and c.position == "faceup" for c in obs.field)
                assert not any(c.controller == 1 and c.zone == "monster" for c in obs.field)
                owner = env.engine.probe.observation(1)
                attacker = env.engine.probe.observation(0)
                assert (monster_code in {c.code for c in owner.hand}) == respond
                assert (monster_code in {c.code for c in obs.banished[1]}) != respond
                assert attacker.known_opponent_hand_cards == ((monster_code,) if respond
                                                              else ())
                assert (COMPULSORY in {c.code for c in obs.graveyards[1]}) == respond
                assert obs.life_points == (8000, 8000)
                return
    pytest.fail("BLS / Compulsory response did not resolve")
