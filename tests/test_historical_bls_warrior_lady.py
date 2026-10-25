"""D.D. Warrior Lady's choice controls BLS's second-attack opportunity."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL = 79571449
DD_WARRIOR_LADY = 7572887
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("banish", [False, True])
def test_warrior_lady_choice_controls_bls_second_attack(tmp_path, banish):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
                     f"official/c{DD_WARRIOR_LADY}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    bls_cards = (GRACEFUL, BLS,
                 *(code for code in lights for _ in range(3)),
                 *(code for code in darks for _ in range(3)), *filler[:26])
    bls_deck = tmp_path / "bls.ydk"
    bls_deck.write_text("#main\n" + "\n".join(map(str, bls_cards))
                        + "\n#extra\n!side\n")
    warrior_deck = tmp_path / "warrior.ydk"
    warrior_deck.write_text("#main\n" + "\n".join(map(str, (
        DD_WARRIOR_LADY, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(bls_deck), str(warrior_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BLS, GRACEFUL, LIGHT, DARK}.issubset(c.code for c in obs.hand)
        assert DD_WARRIOR_LADY in {
            c.code for c in env.engine.probe.observation(1).hand}
        graceful_used = discarded = bls_summoned = warrior_summoned = False
        battle = attacked = targeted = warrior_choice_made = False
        both_banished = False
        second_attack_enabled = second_attack = False
        costs = []
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful_used |= action is not None
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
                                   in ({LIGHT, DARK} - set(costs))), None)
                    if action is not None:
                        costs.append(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1 and not warrior_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == DD_WARRIOR_LADY), None)
                warrior_summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and warrior_summoned:
                if obs.phase == "main1" and not battle:
                    assert set(costs) == {LIGHT, DARK}
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                elif obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == BLS), None)
                    attacked |= action is not None
                elif attacked and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == DD_WARRIOR_LADY and a.parameters.get("controller")
                                   == 1), None)
                    targeted |= action is not None
            if targeted and obs.acting_player == 0 and not second_attack_enabled:
                option = next((a for a in actions if a.kind == "yes"
                               and a.parameters.get("code") == BLS), None)
                if option is not None:
                    assert obs.phase == "damage_step"
                    assert not warrior_choice_made
                    action = option
                    second_attack_enabled = True
            if targeted and obs.acting_player == 1 and not warrior_choice_made:
                option = next((a for a in actions if a.kind in ("yes", "chain")
                               and a.parameters.get("code") == DD_WARRIOR_LADY), None)
                if option is not None:
                    assert obs.phase == "damage_step"
                    action = option if banish else next(a for a in actions
                                                       if a.kind in ("no", "pass"))
                    warrior_choice_made = True
            if warrior_choice_made and not banish and obs.acting_player == 0 \
                    and second_attack_enabled and not second_attack \
                    and obs.phase == "battle_step":
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == BLS), action)
                second_attack |= action is not None and action.kind == "attack"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            obs = env.step(action)
            if warrior_choice_made and banish and {BLS, DD_WARRIOR_LADY}.issubset(
                    {c.code for zone in obs.banished for c in zone}):
                both_banished = True
            if not banish and second_attack and obs.life_points == (8000, 3500) \
                    and obs.phase == "battle_step" and obs.acting_player == 0:
                assert DD_WARRIOR_LADY in {c.code for c in obs.graveyards[1]}
                assert BLS in {c.code for c in obs.field}
                assert BLS not in {c.code for c in obs.banished[0]}
                assert not any(a.kind == "attack" and a.parameters.get("code") == BLS
                               for a in env.legal_actions())
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"goat/c{BLS}.lua",
                        f"official/c{DD_WARRIOR_LADY}.lua"}.issubset(loaded)
                return
            if both_banished:
                assert second_attack_enabled
                assert BLS in {c.code for c in obs.banished[0]}
                assert DD_WARRIOR_LADY in {c.code for c in obs.banished[1]}
                assert obs.life_points == (8000, 6500)
                assert not any(a.parameters.get("code") == BLS and a.kind in (
                    "yes", "attack") for a in env.legal_actions())
                assert not any(c.code in {BLS, DD_WARRIOR_LADY}
                               for c in obs.field)
                if obs.phase == "battle_step" and obs.acting_player == 0:
                    loaded = env.engine.probe.loaded_script_sha256
                    assert {f"goat/c{BLS}.lua",
                            f"official/c{DD_WARRIOR_LADY}.lua"}.issubset(loaded)
                    return
    pytest.fail(f"Warrior Lady / BLS choice did not resolve (banish={banish})")
