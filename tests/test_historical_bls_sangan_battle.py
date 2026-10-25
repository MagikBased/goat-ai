"""Sangan searches after BLS destroys it and BLS can attack again."""

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
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("take_second", [False, True])
def test_bls_destroys_sangan_search_then_second_attack(tmp_path, take_second):
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
    bls_deck = tmp_path / "bls.ydk"
    bls_deck.write_text("#main\n" + "\n".join(map(str, bls_cards))
                        + "\n#extra\n!side\n")
    sangan_deck = tmp_path / "sangan.ydk"
    sangan_deck.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(bls_deck), str(sangan_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS, LIGHT, DARK}.issubset(c.code for c in obs.hand)
        assert SANGAN in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = bls_summoned = sangan_summoned = False
        battle = attacked = target_selected = bls_triggered = searched = False
        second_attack = False
        costs = set()
        defender_deck_before = None
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                elif not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
                elif discarded and not bls_summoned:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    bls_summoned |= action is not None
                elif bls_summoned and len(costs) < 2 \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - costs)), None)
                    if action is not None:
                        costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1 and not sangan_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SANGAN), None)
                if action is not None:
                    sangan_summoned = True
                    defender_deck_before = obs.deck_counts[1]
            if obs.turn == 3 and obs.acting_player == 0 and sangan_summoned:
                if obs.phase == "main1" and not battle:
                    assert costs == {LIGHT, DARK}
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                elif obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == BLS), None)
                    attacked |= action is not None
                elif attacked and not target_selected and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == SANGAN and a.parameters.get("controller") == 1), None)
                    target_selected |= action is not None
            if target_selected and not bls_triggered:
                option = next((a for a in actions if a.kind == "yes"
                               and a.parameters.get("code") == BLS), None)
                if option is not None:
                    assert obs.phase == "damage_step"
                    assert obs.chain == ()
                    assert SANGAN not in {c.code for c in obs.graveyards[1]}
                    action = (option if take_second else next(a for a in actions
                              if a.kind == "no" and a.parameters.get("code") == BLS))
                    bls_triggered = True
            if target_selected and not searched and actions[0].kind == "select_card" \
                    and any(a.parameters.get("location") == 1 for a in actions):
                assert obs.phase == "damage_step"
                assert SANGAN in {c.code for c in obs.graveyards[1]}
                assert tuple(link.card_code for link in obs.chain) == (SANGAN,)
                attacker_view = env.engine.probe.observation(0)
                assert attacker_view.known_opponent_hand_cards == ()
                assert not attacker_view.private_reveals
                action = next(a for a in actions if a.parameters.get("code") == MYSTICAL_ELF)
                searched = True
            if searched and bls_triggered and take_second and obs.phase == "battle_step" \
                    and obs.acting_player == 0 and not second_attack:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == BLS), action)
                second_attack |= action is not None and action.kind == "attack"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            obs = env.step(action)
            if searched and bls_triggered and not take_second \
                    and obs.phase == "battle_step" and obs.acting_player == 0:
                assert obs.life_points == (8000, 6000)
                assert obs.deck_counts[1] == defender_deck_before - 1
                assert not any(a.kind == "attack" and a.parameters.get("code") == BLS
                               for a in env.legal_actions())
                assert env.engine.probe.observation(0).known_opponent_hand_cards \
                    == (MYSTICAL_ELF,)
                return
            if second_attack and obs.life_points == (8000, 3000) \
                    and obs.phase == "battle_step":
                assert obs.deck_counts[1] == defender_deck_before - 1
                assert MYSTICAL_ELF in {c.code for c in env.engine.probe.observation(1).hand}
                assert env.engine.probe.observation(0).known_opponent_hand_cards \
                    == (MYSTICAL_ELF,)
                assert not any(a.kind == "attack" and a.parameters.get("code") == BLS
                               for a in env.legal_actions())
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("BLS / Sangan battle did not reach the searched second attack")
