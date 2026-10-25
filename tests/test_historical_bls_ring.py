"""BLS's activated banish resolves after chained Ring destroys BLS."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
RING = 511000824
GRACEFUL = 79571449
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_ring_destroys_bls_but_pending_banish_still_resolves(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{BLS}.lua", f"pre-errata/c{RING}.lua",
               f"official/c{GRACEFUL}.lua")
    for script in scripts:
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    bls_cards = (GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
                 *(code for code in darks for _ in range(3)), *filler[:26])
    bls_deck = tmp_path / "bls.ydk"
    bls_deck.write_text("#main\n" + "\n".join(map(str, bls_cards))
                        + "\n#extra\n!side\n")
    ring_deck = tmp_path / "ring.ydk"
    ring_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(bls_deck), str(ring_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = ring_set = defender_summoned = bls_summoned = False
        bls_used = defender_targeted = ring_chained = bls_targeted = False
        costs = set()
        defender_code = None
        for _ in range(100):
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
            if obs.turn == 2 and obs.acting_player == 1:
                if not ring_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    ring_set |= action is not None
                if ring_set and not defender_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        defender_code = action.parameters["code"]
                        defender_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and defender_summoned:
                if not bls_summoned:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    bls_summoned |= action is not None
                if bls_summoned and len(costs) < 2 and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - costs)), action)
                    if action is not None and action.kind == "select_card":
                        costs.add(action.parameters["code"])
                if costs == {LIGHT, DARK} and not bls_used:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == BLS), None)
                    if option is not None:
                        assert obs.chain == ()
                        action = option
                        bls_used = True
                if bls_used and not defender_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") == defender_code), action)
                    defender_targeted |= action is not None and action.kind == "select_card"
            if defender_targeted and obs.acting_player == 1 and not ring_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), None)
                if option is not None:
                    assert obs.chain[0].card_code == BLS
                    action = option
                    ring_chained = True
            if ring_chained and not bls_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("code") == BLS), None)
                bls_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if bls_targeted and RING in {c.code for c in obs.graveyards[1]}:
                assert ring_set and defender_summoned and bls_used
                assert obs.chain == ()
                assert obs.life_points == (5000, 5000)
                assert BLS in {c.code for c in obs.graveyards[0]}
                assert defender_code in {c.code for c in obs.banished[1]}
                assert not any(c.zone == "monster" for c in obs.field)
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("BLS/Ring chain did not resolve")
