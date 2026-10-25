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
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("choice", [
    "double_attack", "banish", "banish_book", "attack_then_main2", "attack_book",
    "self_banish", "banish_set"])
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
    opponent_deck = "examples/decks/vanilla_probe.ydk"
    if choice in ("banish_book", "attack_book"):
        if not (root / f"scripts/official/c{BOOK_OF_MOON}.lua").is_file():
            pytest.skip("Book of Moon script not installed")
        opponent = tmp_path / "book_response.ydk"
        opponent.write_text("#main\n" + "\n".join(map(str, (
            BOOK_OF_MOON, BOOK_OF_MOON, BOOK_OF_MOON,
            *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
        opponent_deck = str(opponent)

    with GoatEnvironment(str(deck), opponent_deck, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = summoned = opponent_summoned = first_attack = False
        second_attack = trigger_accepted = effect_used = False
        book_set = effect_targeted = book_chained = book_targeted = False
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
            if action is None and discarded and observation.turn == 1 \
                    and observation.acting_player == 0 \
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
            if (choice == "self_banish" and observation.turn == 1
                    and observation.acting_player == 0 and set(costs) == {LIGHT, DARK}):
                if not effect_used:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == BLS), action)
                    effect_used |= action is not None and action.parameters.get("code") == BLS
                if effect_used and not effect_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == BLS
                                   and a.parameters.get("controller") == 0
                                   and a.parameters.get("location") == 4), action)
                    effect_targeted |= action is not None and action.kind == "select_card"
            if choice != "attack_book" and observation.turn == 2 \
                    and observation.acting_player == 1 \
                    and not opponent_summoned:
                summon_kind = "set_monster" if choice == "banish_set" else "normal_summon"
                option = next((a for a in actions if a.kind == summon_kind), None)
                if option is not None:
                    action = option
                    opponent_summoned = True
                    opponent_code = option.parameters["code"]
            if (choice in ("banish_book", "attack_book") and observation.turn == 2
                    and observation.acting_player == 1
                    and (opponent_summoned or choice == "attack_book")
                    and not book_set and action is None):
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                book_set |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if choice in ("banish", "banish_book", "banish_set") and not effect_used:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BLS), None)
                    if option is not None:
                        action = option
                        effect_used = True
                if (choice in ("banish", "banish_book", "banish_set") and effect_used
                        and not effect_targeted and actions[0].kind == "select_card"):
                    if choice == "banish_set":
                        assert any(c.controller == 1 and c.zone == "monster"
                                   and c.position == "facedown" and c.code is None
                                   for c in observation.field)
                        action = next((a for a in actions if a.parameters.get("controller")
                                       == 1 and a.parameters.get("location") == 4
                                       and "code" not in a.parameters), action)
                    else:
                        action = next((a for a in actions if a.parameters.get("controller")
                                       == 1 and a.parameters.get("code") == opponent_code
                                       and a.parameters.get("location") == 4), action)
                    effect_targeted |= action is not None and action.kind == "select_card"
                if observation.phase == "main1" and (
                        choice in ("double_attack", "attack_then_main2", "attack_book") or (
                            effect_used and any(c.code == opponent_code
                                                for c in observation.banished[1]))):
                    if choice == "attack_then_main2":
                        assert any(a.kind == "activate" and a.parameters.get("code") == BLS
                                   for a in actions)
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if choice in ("double_attack", "attack_then_main2", "attack_book") \
                        and observation.phase == "battle_start" \
                        and not first_attack:
                    assert set(costs) == {LIGHT, DARK}
                    assert {c.code for c in observation.banished[0]} == {LIGHT, DARK}
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == BLS), action)
                    first_attack = action is not None and action.kind == "attack"
                if choice != "attack_book" and first_attack \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), action)
                if first_attack and any(a.kind == "yes" and a.parameters.get("code") == BLS
                                        for a in actions):
                    assert observation.phase == "damage_step"
                    assert observation.life_points == (8000, 6800)
                    response = "yes" if choice == "double_attack" else "no"
                    action = next(a for a in actions if a.kind == response
                                  and a.parameters.get("code") == BLS)
                    trigger_accepted = response == "yes"
                if trigger_accepted and not second_attack \
                        and observation.phase == "battle_step":
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == BLS), action)
                    second_attack = action is not None and action.kind == "attack"
                if choice == "attack_then_main2" and first_attack \
                        and observation.phase == "battle_step" \
                        and observation.life_points == (8000, 6800):
                    action = next((a for a in actions if a.kind == "main2"), action)
            if (choice == "banish_book" and effect_targeted
                    and observation.acting_player == 1 and not book_chained):
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                if option is not None:
                    assert observation.chain[0].card_code == BLS
                    action = option
                    book_chained = True
            if (choice == "banish_book" and book_chained
                    and observation.acting_player == 1
                    and actions[0].kind == "select_card"):
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == opponent_code), action)
                book_targeted |= action is not None and action.kind == "select_card"
            if choice == "attack_book" and first_attack \
                    and observation.acting_player == 1:
                if not book_chained:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    if option is not None:
                        action = option
                        book_chained = True
                elif not book_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.kind == "select_card"
                                   and a.parameters.get("controller") == 0
                                   and a.parameters.get("code") == BLS), None)
                    book_targeted |= action is not None
            if choice == "attack_book" and book_targeted \
                    and BOOK_OF_MOON in {c.code for c in observation.graveyards[1]}:
                assert observation.life_points == (8000, 8000)
                assert any(c.code == BLS and c.position == "facedown"
                           for c in env.engine.probe.observation(0).field)
                if observation.phase == "battle_step" and observation.acting_player == 0:
                    assert not any(a.kind == "attack" and a.parameters.get("code") == BLS
                                   for a in actions)
                    action = next((a for a in actions if a.kind == "main2"), action)
                if observation.phase == "main2" and observation.acting_player == 0:
                    assert not any(a.kind in ("flip_summon", "change_position", "activate")
                                   and a.parameters.get("code") == BLS for a in actions)
                    assert f"official/c{BOOK_OF_MOON}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                    return
            if (choice == "banish_book" and book_chained
                    and BOOK_OF_MOON in {c.code for c in observation.graveyards[1]}):
                assert book_targeted
                assert not any(c.controller == 1 and c.zone == "monster"
                               for c in observation.field)
                assert any(c.code == opponent_code and c.position == "faceup"
                           for c in observation.banished[1])
                assert not any(a.kind == "activate" and a.parameters.get("code") == BLS
                               for a in actions)
                if observation.phase == "battle_start":
                    assert not any(a.kind == "attack" and a.parameters.get("code") == BLS
                                   for a in actions)
                    assert f"official/c{BOOK_OF_MOON}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                    assert f"goat/c{BLS}.lua" in env.engine.probe.loaded_script_sha256
                    return
                if observation.phase == "main1" and observation.acting_player == 0:
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
            if choice == "attack_then_main2" and observation.turn == 3 \
                    and observation.phase == "main2" and observation.acting_player == 0:
                assert any(c.code == BLS for c in observation.field)
                assert not any(a.kind == "activate" and a.parameters.get("code") == BLS
                               for a in actions)
                assert f"goat/c{BLS}.lua" in env.engine.probe.loaded_script_sha256
                return
            if choice == "self_banish" and effect_targeted \
                    and any(c.code == BLS for c in observation.banished[0]):
                assert observation.turn == 1
                assert not any(c.code == BLS for c in observation.field)
                assert {c.code for c in observation.banished[0]} == {LIGHT, DARK, BLS}
                assert observation.life_points == (8000, 8000)
                assert f"goat/c{BLS}.lua" in env.engine.probe.loaded_script_sha256
                return
            if (choice in ("banish", "banish_set") and effect_used and observation.turn == 3
                    and observation.phase == "battle_start"
                    and any(c.code == opponent_code for c in observation.banished[1])):
                assert any(c.code == opponent_code and c.position == "faceup"
                           for c in observation.banished[1])
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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_bls_set_target_choice_is_invariant_to_private_identity(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    cards = (GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
             *(code for code in darks for _ in range(3)), *filler[:26])
    own_deck = tmp_path / "bls.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, cards))
                        + "\n#extra\n!side\n")

    def run(hidden_code):
        opponent_cards = list(VANILLA_DECK)
        opponent_cards[4] = hidden_code
        opponent_deck = tmp_path / f"set_{hidden_code}.ydk"
        opponent_deck.write_text("#main\n" + "\n".join(map(str, opponent_cards))
                                 + "\n#extra\n!side\n")
        with GoatEnvironment(str(own_deck), str(opponent_deck), seed=100,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            graceful = discarded = summoned = set_monster = effect_used = False
            costs = set()
            for _ in range(85):
                actions = env.legal_actions()
                if effect_used and obs.acting_player == 0 \
                        and actions[0].kind == "select_card":
                    assert obs.viewer == 0
                    assert any(c.controller == 1 and c.zone == "monster"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
                    targets = [a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4]
                    assert len(targets) == 1
                    assert "code" not in targets[0].parameters
                    return obs, actions, env.engine.probe.observation(1)
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
                if obs.turn == 2 and obs.acting_player == 1 and not set_monster:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == hidden_code), None)
                    set_monster |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 and set_monster \
                        and not effect_used:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == BLS), action)
                    effect_used |= action is not None and action.parameters.get("code") == BLS
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "pass", "end_phase")), actions[0])
                obs = env.step(action)
        pytest.fail("BLS did not reach its set-monster target decision")

    first = run(23771716)
    second = run(97923414)
    assert first[0] == second[0]
    assert first[1] == second[1]
    assert {c.code for c in first[2].field if c.controller == 1} != {
        c.code for c in second[2].field if c.controller == 1}
