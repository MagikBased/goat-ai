"""A stolen BLS exposes its activated effect to its new controller."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL = 79571449
SNATCH = 45986603
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_snatch_stolen_bls_can_banish_original_owners_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
               f"official/c{SNATCH}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    bls_cards = (GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
                 *(code for code in darks for _ in range(3)), *filler[:26])
    attacker = tmp_path / "bls.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, bls_cards))
                        + "\n#extra\n!side\n")
    stealer = tmp_path / "snatch.ydk"
    stealer.write_text("#main\n" + "\n".join(map(str, (
        SNATCH, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(stealer), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = vanilla_summoned = bls_summoned = False
        snatch_used = snatch_targeted = bls_effect = banish_targeted = False
        banish_resolved = False
        costs = set()
        vanilla_code = None
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
                if discarded and not vanilla_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") in filler), None)
                    if action is not None:
                        vanilla_code = action.parameters["code"]
                        vanilla_summoned = True
            if observation.turn == 3 and observation.acting_player == 0:
                if vanilla_summoned and not bls_summoned:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    bls_summoned |= action is not None
                if bls_summoned and len(costs) < 2 and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - costs)), action)
                    if action is not None and action.kind == "select_card":
                        costs.add(action.parameters["code"])
            if observation.turn == 4 and observation.acting_player == 1:
                if banish_resolved and observation.phase == "battle_start":
                    assert not any(a.kind == "attack" and a.parameters.get("code") == BLS
                                   for a in actions)
                    assert any(card.code == BLS and card.controller == 1
                               for card in observation.field)
                    assert any(card.code == SNATCH and card.controller == 1
                               for card in observation.field)
                    assert observation.life_points == (8000, 8000)
                    assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                    return
                if banish_resolved and observation.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                if bls_summoned and not snatch_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH), None)
                    snatch_used |= action is not None
                if snatch_used and not snatch_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == BLS
                                   and a.parameters.get("controller") == 0), None)
                    snatch_targeted |= action is not None
                if snatch_targeted and not bls_effect:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == BLS), action)
                    bls_effect |= action is not None and action.kind == "chain"
                if bls_effect and not banish_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == vanilla_code and a.parameters.get("controller") == 0), None)
                    banish_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if banish_targeted and vanilla_code in {
                    card.code for card in observation.banished[0]}:
                banish_resolved = True
                assert {LIGHT, DARK}.issubset(card.code for card in
                                              observation.banished[0])
                assert any(card.code == BLS and card.controller == 1
                           for card in observation.field)
                assert any(card.code == SNATCH and card.controller == 1
                           for card in observation.field)
    pytest.fail(f"BLS/Snatch line stalled: graceful={graceful} discard={discarded} "
                f"vanilla={vanilla_summoned} BLS={bls_summoned} costs={costs} "
                f"snatch={snatch_used}/{snatch_targeted} "
                f"effect={bls_effect}/{banish_targeted}/{banish_resolved} "
                f"turn={observation.turn} phase={observation.phase}")
