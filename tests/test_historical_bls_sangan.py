"""BLS banishes Sangan without triggering its field-to-Graveyard search."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
SANGAN = 504700178
GRACEFUL = 79571449
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_bls_banishes_opponents_sangan_without_search(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{BLS}.lua", f"goat/c{SANGAN}.lua",
               f"official/c{GRACEFUL}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    bls_cards = (GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
                 *(code for code in darks for _ in range(3)), *filler[:26])
    assert len(bls_cards) == 40
    bls_deck = tmp_path / "bls.ydk"
    bls_deck.write_text("#main\n" + "\n".join(map(str, bls_cards))
                        + "\n#extra\n!side\n")
    sangan_deck = tmp_path / "sangan.ydk"
    sangan_deck.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(bls_deck), str(sangan_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS}.issubset(c.code for c in obs.hand)
        assert SANGAN in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = sangan_summoned = bls_summoned = False
        bls_used = sangan_targeted = False
        costs = set()
        defender_deck_before = None
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
            if obs.turn == 2 and obs.acting_player == 1 and not sangan_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SANGAN), None)
                if action is not None:
                    sangan_summoned = True
                    defender_deck_before = obs.deck_counts[1]
            if obs.turn == 3 and obs.acting_player == 0 and sangan_summoned:
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
                        action = option
                        bls_used = True
                if bls_used and not sangan_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") == SANGAN), None)
                    sangan_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if sangan_targeted and SANGAN in {c.code for c in obs.banished[1]}:
                assert obs.chain == ()
                assert obs.deck_counts[1] == defender_deck_before
                assert SANGAN not in {c.code for c in obs.graveyards[1]}
                assert not any(a.kind == "select_card" and a.parameters.get(
                    "location") == 1 for a in env.legal_actions())
                assert env.engine.probe.observation(0).known_opponent_hand_cards == ()
                assert not env.engine.probe.observation(0).private_reveals
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("BLS did not banish Sangan without a search")
