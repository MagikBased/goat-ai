"""Pre-errata BLS summon cost and its mutually exclusive turn choices."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118  # GOAT variant of Black Luster Soldier - Envoy of the Beginning
GRACEFUL = 79571449
LIGHT = 15025844  # Mystical Elf
DARK = 7359741  # Mechanicalchaser


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("choice", ["double_attack", "banish"])
def test_bls_historical_turn_choices(tmp_path, choice):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")

    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    cards = (GRACEFUL, BLS,
             *(code for code in lights for _ in range(3)),
             *(code for code in darks for _ in range(3)), *filler[:26])
    assert len(cards) == 40
    deck = tmp_path / "bls.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = summoned = opponent_summoned = first_attack = False
        second_attack = trigger_accepted = effect_used = False
        costs = []
        opponent_code = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {c["code"] for c in a.parameters["cards"]}
                               == {LIGHT, DARK}), None)
                discarded |= action is not None
            if discarded and observation.turn == 1 and observation.acting_player == 0 \
                    and not summoned:
                option = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == BLS), None)
                if option is not None:
                    assert {c.code for c in observation.graveyards[0]} == {
                        LIGHT, DARK, GRACEFUL}
                    action = option
                    summoned = True
            if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in ({LIGHT, DARK} - set(costs))), action)
                if action is not None:
                    assert action.parameters["location"] == 16
                    costs.append(action.parameters["code"])
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not opponent_summoned:
                option = next((a for a in actions if a.kind == "normal_summon"), None)
                if option is not None:
                    action = option
                    opponent_summoned = True
                    opponent_code = option.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0:
                if choice == "banish" and not effect_used:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BLS), None)
                    if option is not None:
                        action = option
                        effect_used = True
                if choice == "banish" and effect_used and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") == opponent_code
                                   and a.parameters.get("location") == 4), action)
                if observation.phase == "main1" and (
                        choice == "double_attack" or (
                            effect_used and any(c.code == opponent_code
                                                for c in observation.banished[1]))):
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if choice == "double_attack" and observation.phase == "battle_start" \
                        and not first_attack:
                    assert set(costs) == {LIGHT, DARK}
                    assert {c.code for c in observation.banished[0]} == {LIGHT, DARK}
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == BLS), action)
                    first_attack = action is not None and action.kind == "attack"
                if first_attack and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), action)
                if first_attack and any(a.kind == "yes" and a.parameters.get("code") == BLS
                                        for a in actions):
                    assert observation.phase == "damage_step"
                    assert observation.life_points == (8000, 6800)
                    action = next(a for a in actions if a.kind == "yes"
                                  and a.parameters.get("code") == BLS)
                    trigger_accepted = True
                if trigger_accepted and not second_attack \
                        and observation.phase == "battle_step":
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == BLS), action)
                    second_attack = action is not None and action.kind == "attack"
            if (choice == "banish" and effect_used and observation.turn == 3
                    and observation.phase == "battle_start"
                    and any(c.code == opponent_code for c in observation.banished[1])):
                assert not any(a.kind == "attack" and a.parameters.get("code") == BLS
                               for a in actions)
                assert not any(a.kind == "activate" and a.parameters.get("code") == BLS
                               for a in actions)
                assert observation.life_points == (8000, 8000)
                assert f"goat/c{BLS}.lua" in env.engine.probe.loaded_script_sha256
                return
            if (choice == "double_attack" and second_attack and observation.turn == 3
                    and observation.phase == "battle_step"
                    and observation.life_points == (8000, 3800)):
                assert not any(a.kind == "attack" and a.parameters.get("code") == BLS
                               for a in actions)
                assert f"goat/c{BLS}.lua" in env.engine.probe.loaded_script_sha256
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail(f"BLS did not complete its historical {choice} line")
