"""Chaos Sorcerer summon cost, banish effect, and attack restriction."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CHAOS_SORCERER = 9596126
GRACEFUL_CHARITY = 79571449
LIGHT = 62651957  # X-Head Cannon
DARK = 7359741  # Mechanicalchaser
SCAPEGOAT = 504700123
SHEEP_TOKENS = {73915052, 73915053, 73915054, 73915055}


def chaos_deck(tmp_path):
    lights = (15025844, LIGHT)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    cards = (GRACEFUL_CHARITY, *(CHAOS_SORCERER,) * 3,
             *(code for code in lights for _ in range(3)),
             *(code for code in darks for _ in range(3)), *filler[:24])
    assert len(cards) == 40
    deck = tmp_path / "chaos_sorcerer.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return deck


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("effect_phase", ["main1", "main2"])
def test_sorcerer_banishes_opponent_monster_in_either_main_phase(tmp_path, effect_phase):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (CHAOS_SORCERER, GRACEFUL_CHARITY):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = chaos_deck(tmp_path)

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = summoned = opponent_summoned = effect_used = False
        costs = []
        opponent_code = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.acting_player == 0 and observation.turn == 1 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {card["code"]
                               for card in a.parameters["cards"]} == {LIGHT, DARK}), None)
                discarded |= action is not None
            if (discarded and observation.acting_player == 0 and observation.turn == 1
                    and not summoned):
                option = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == CHAOS_SORCERER), None)
                if option is not None:
                    assert {card.code for card in observation.graveyards[0]} == {
                        LIGHT, DARK, GRACEFUL_CHARITY}
                    action = option
                    summoned = True
            if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                cost = next((a for a in actions if a.parameters.get("code")
                             in ({LIGHT, DARK} - set(costs))), None)
                if cost is not None:
                    assert cost.parameters["location"] == 16
                    assert cost.parameters["controller"] == 0
                    costs.append(cost.parameters["code"])
                    action = cost
            if observation.acting_player == 1 and observation.turn == 2 and not opponent_summoned:
                option = next((a for a in actions if a.kind == "normal_summon"), None)
                if option is not None:
                    action = option
                    opponent_summoned = True
                    opponent_code = option.parameters["code"]
            if (effect_phase == "main2" and observation.turn == 3
                    and observation.acting_player == 0 and opponent_summoned
                    and not effect_used and action is None):
                action = next((a for a in actions if a.kind in ("battle_phase", "main2")),
                              None)
            if (observation.acting_player == 0 and observation.turn == 3
                    and observation.phase == effect_phase
                    and opponent_summoned and not effect_used and action is None):
                option = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CHAOS_SORCERER), None)
                if option is not None:
                    assert set(costs) == {LIGHT, DARK}
                    assert {card.code for card in observation.banished[0]} == {LIGHT, DARK}
                    action = option
                    effect_used = True
            if effect_used and observation.turn == 3 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == opponent_code
                               and a.parameters.get("location") == 4), action)
            if (effect_used and observation.turn == 3
                    and any(card.code == opponent_code for card in observation.banished[1])):
                assert not any(a.kind == "activate"
                               and a.parameters.get("code") == CHAOS_SORCERER
                               for a in actions)
                assert any(card.code == CHAOS_SORCERER and card.attack == 2300
                           and card.defense == 2000 for card in observation.field)
                if effect_phase == "main2" and observation.phase == "main2" \
                        and any(a.kind == "end_phase" for a in actions):
                    assert observation.life_points == (8000, 8000)
                    return
                if observation.phase == "battle_start" and observation.acting_player == 0:
                    assert not any(a.kind == "attack"
                                   and a.parameters.get("code") == CHAOS_SORCERER
                                   for a in actions)
                    assert observation.life_points == (8000, 8000)
                    return
                if observation.phase == "main1" and observation.acting_player == 0:
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            observation = env.step(action)
    pytest.fail("Chaos Sorcerer line did not reach its attack restriction")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sorcerer_cannot_pay_its_cost_with_light_and_dark_only_on_field(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{CHAOS_SORCERER}.lua").is_file():
        pytest.skip("Chaos Sorcerer script not installed")
    with GoatEnvironment(str(chaos_deck(tmp_path)), "examples/decks/vanilla_probe.ydk",
                         seed=100, engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summons = []
        for _ in range(45):
            actions = env.legal_actions()
            action = None
            if (observation.acting_player == 0 and observation.turn in (1, 3)
                    and len(summons) < (1 if observation.turn == 1 else 2)):
                wanted = LIGHT if not summons else DARK
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == wanted), None)
                if action is not None:
                    summons.append(wanted)
            if (observation.turn == 3 and observation.phase == "main1"
                    and observation.acting_player == 0 and len(summons) == 2
                    and {LIGHT, DARK}.issubset({card.code for card in observation.field})):
                assert not observation.graveyards[0]
                assert not any(a.kind == "special_summon"
                               and a.parameters.get("code") == CHAOS_SORCERER
                               for a in actions)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("did not reach the LIGHT/DARK field-only control state")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sorcerer_cannot_use_banish_effect_in_main2_after_attacking(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{CHAOS_SORCERER}.lua",
                     f"official/c{GRACEFUL_CHARITY}.lua", f"goat/c{SCAPEGOAT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    opponent = tmp_path / "scapegoat.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(chaos_deck(tmp_path)), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = summoned = goat_used = battle = attacked = False
        targeted = False
        costs = set()
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {c["code"] for c in
                               a.parameters["cards"]} == {LIGHT, DARK}), None)
                discarded |= action is not None
            if discarded and obs.turn == 1 and obs.acting_player == 0 \
                    and not summoned and action is None:
                action = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == CHAOS_SORCERER), None)
                summoned |= action is not None
            if summoned and len(costs) < 2 and actions[0].kind == "select_card" \
                    and action is None:
                action = next((a for a in actions if a.parameters.get("code")
                               in {LIGHT, DARK} - costs and a.parameters.get("location")
                               == 16), None)
                if action is not None:
                    costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1 and not goat_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_used |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and goat_used:
                if not battle and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    if action is not None:
                        assert any(a.kind == "activate" and a.parameters.get("code")
                                   == CHAOS_SORCERER for a in actions)
                    battle |= action is not None
                if battle and obs.phase == "battle_start" and not attacked \
                        and action is None:
                    assert {c.code for c in obs.field if c.controller == 1
                            and c.code in SHEEP_TOKENS} == SHEEP_TOKENS
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == CHAOS_SORCERER), None)
                    attacked |= action is not None
                if attacked and targeted and obs.phase == "battle_step" and action is None \
                        and sum(c.controller == 1 and c.code in SHEEP_TOKENS
                                for c in obs.field) == 3:
                    action = next((a for a in actions if a.kind == "main2"), None)
            if attacked and not targeted and actions[0].kind == "select_card" \
                    and action is None:
                action = next((a for a in actions if a.parameters.get("code")
                               in SHEEP_TOKENS), None)
                targeted |= action is not None
            if targeted and obs.acting_player == 0 and obs.phase == "main2":
                assert set(costs) == {LIGHT, DARK}
                assert sum(c.controller == 1 and c.code in SHEEP_TOKENS
                           for c in obs.field) == 3
                assert not any(a.kind == "activate" and a.parameters.get("code")
                               == CHAOS_SORCERER for a in actions)
                assert obs.life_points == (8000, 8000)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Sorcerer attack did not block its Main Phase 2 effect")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sorcerer_declined_replay_still_blocks_main2_banish(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{CHAOS_SORCERER}.lua",
                     f"official/c{GRACEFUL_CHARITY}.lua", f"goat/c{SCAPEGOAT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    opponent = tmp_path / "scapegoat.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(chaos_deck(tmp_path)), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = summoned = goat_set = attacked = chained = checked = False
        costs = set()
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "sorcerer_goat_replay.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {c["code"] for c in a.parameters["cards"]}
                               == {LIGHT, DARK}), None)
                assert action is not None
                discarded = True
            if discarded and obs.turn == 1 and obs.acting_player == 0 \
                    and not summoned and action is None:
                action = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == CHAOS_SORCERER), None)
                summoned |= action is not None
            if summoned and costs != {LIGHT, DARK} and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in {LIGHT, DARK} - costs and a.parameters.get("location") == 16),
                              action)
                if action is not None:
                    costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1 and not goat_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_set |= action is not None
            if goat_set and obs.turn == 3 and obs.acting_player == 0:
                if obs.phase == "main1":
                    assert any(a.kind == "activate"
                               and a.parameters.get("code") == CHAOS_SORCERER
                               for a in actions)
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if obs.phase == "battle_start" and not attacked:
                    assert not any(c.controller == 1 and c.zone == "monster"
                                   for c in obs.field)
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == CHAOS_SORCERER), action)
                    attacked |= action is not None and action.kind == "attack"
            if attacked and obs.acting_player == 1 and not chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                chained |= action is not None and action.kind == "chain"
            tokens = sum(c.code in SHEEP_TOKENS for c in obs.field)
            if chained and tokens == 4 and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "battle_step" and not checked and any(
                        a.kind == "attack" and a.parameters.get("code") == CHAOS_SORCERER
                        for a in actions):
                action = next((a for a in actions if a.kind == "main2"), None)
                assert action is not None
            if chained and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main2" and not checked:
                assert tokens == 4
                assert not any(a.kind == "activate"
                               and a.parameters.get("code") == CHAOS_SORCERER
                               for a in actions)
                assert obs.life_points == (8000, 8000)
                assert {f"official/c{CHAOS_SORCERER}.lua",
                        f"goat/c{SCAPEGOAT}.lua"} <= (
                    env.engine.probe.loaded_script_sha256.keys())
                checked = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
    pytest.fail("Sorcerer / Scapegoat replay duel did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_makes_sorcerer_target_invalid_but_still_spends_effect_and_attack(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (CHAOS_SORCERER, GRACEFUL_CHARITY, 14087893):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    book = 14087893
    opponent = tmp_path / "book_response.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        book, book, book, *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(chaos_deck(tmp_path)), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = summoned = opponent_summoned = book_set = False
        activated = targeted = book_chained = False
        opponent_code = None
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {card["code"]
                               for card in a.parameters["cards"]} == {LIGHT, DARK}), None)
                discarded |= action is not None
            if (discarded and observation.turn == 1 and observation.acting_player == 0
                    and not summoned):
                option = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == CHAOS_SORCERER), None)
                if option is not None:
                    action = option
                    summoned = True
            if observation.turn == 2 and observation.acting_player == 1:
                if not opponent_summoned:
                    option = next((a for a in actions if a.kind == "normal_summon"), None)
                    if option is not None:
                        action = option
                        opponent_summoned = True
                        opponent_code = option.parameters["code"]
                if action is None and opponent_summoned and not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == book), None)
                    book_set |= action is not None
            if (observation.turn == 3 and observation.acting_player == 0
                    and book_set and not activated):
                option = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CHAOS_SORCERER), None)
                if option is not None:
                    action = option
                    activated = True
            if activated and not targeted and actions[0].kind == "select_card":
                option = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == opponent_code
                               and a.parameters.get("location") == 4), None)
                if option is not None:
                    action = option
                    targeted = True
            if targeted and observation.acting_player == 1 and not book_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == book), None)
                if option is not None:
                    action = option
                    book_chained = True
            if book_chained and observation.acting_player == 1 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == opponent_code
                               and a.parameters.get("location") == 4), action)
            if (book_chained and observation.turn == 3 and observation.acting_player == 0
                    and any(card.code == book for card in observation.graveyards[1])):
                set_monster = next(card for card in observation.field
                                   if card.controller == 1 and card.zone == "monster")
                assert set_monster.position == "facedown" and set_monster.code is None
                assert not observation.banished[1]
                assert any(card.controller == 1 and card.zone == "monster"
                           and card.sequence == set_monster.sequence
                           and card.code == opponent_code
                           for card in observation.known_opponent_field_cards)
                assert not any(a.kind == "activate"
                               and a.parameters.get("code") == CHAOS_SORCERER
                               for a in actions)
                if observation.phase == "battle_start":
                    assert not any(a.kind == "attack"
                                   and a.parameters.get("code") == CHAOS_SORCERER
                                   for a in actions)
                    return
                if observation.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            observation = env.step(action)
    pytest.fail("Book of Moon did not invalidate the Sorcerer target")
