"""Airknight Parshath draws only after actual battle damage."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL_CHARITY = 79571449
PREMATURE_BURIAL = 70828912
AIRKNIGHT = 18036057
WABOKU = 12607053
DEKOICHI = 87621407
SEVEN_COLORED_FISH = 23771716  # 800 DEF
SECOND_DISCARD = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("waboku", [False, True])
def test_airknight_piercing_draw_requires_nonzero_battle_damage(tmp_path, waboku):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required_scripts = (GRACEFUL_CHARITY, PREMATURE_BURIAL, AIRKNIGHT)
    if waboku:
        required_scripts += (WABOKU,)
    for code in required_scripts:
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "airknight.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, AIRKNIGHT,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    opponent = "examples/decks/vanilla_probe.ydk"
    if waboku:
        response_deck = tmp_path / "waboku.ydk"
        response_deck.write_text("#main\n" + "\n".join(map(str, (
            WABOKU, WABOKU, WABOKU, *VANILLA_DECK[3:])))
                                 + "\n#extra\n!side\n")
        opponent = str(response_deck)

    with GoatEnvironment(str(deck), opponent, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = premature = fish_set = waboku_set = False
        attacked = waboku_used = entered_damage_step = False
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not graceful:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    if option is not None:
                        action = option
                        graceful = True
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"]
                                   for c in a.parameters["cards"]} == {
                                       AIRKNIGHT, SECOND_DISCARD}), None)
                    discarded = action is not None
                if discarded and not premature:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE_BURIAL), None)
                    if option is not None:
                        action = option
                        premature = True
                if premature and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == AIRKNIGHT
                                   and a.parameters.get("location") == 16), action)
            if observation.turn == 2 and observation.acting_player == 1:
                if not fish_set:
                    option = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == SEVEN_COLORED_FISH), None)
                    if option is not None:
                        action = option
                        fish_set = True
                if waboku and fish_set and not waboku_set and action is None:
                    option = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == WABOKU), None)
                    if option is not None:
                        action = option
                        waboku_set = True
            if observation.turn == 3 and observation.acting_player == 0:
                if observation.phase == "main1":
                    assert any(c.code == AIRKNIGHT and c.attack == 1900
                               for c in observation.field)
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if observation.phase == "battle_start" and not attacked:
                    hidden = next(c for c in observation.field
                                  if c.zone == "monster" and c.controller == 1)
                    assert hidden.code is None and hidden.position == "facedown"
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == AIRKNIGHT), action)
                    attacked = action is not None and action.kind == "attack"
                if attacked and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4
                                   and a.parameters.get("code") is None), action)
            if waboku and attacked and observation.turn == 3 \
                    and observation.phase == "battle_step" \
                    and observation.acting_player == 1 and not waboku_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == WABOKU), None)
                if option is not None:
                    action = option
                    waboku_used = True
            if attacked and observation.turn == 3 and observation.phase == "damage_step":
                entered_damage_step = True
            if entered_damage_step and observation.turn == 3 \
                    and observation.phase == "battle_step" \
                    and observation.acting_player == 0:
                own = env.engine.probe.observation(0)
                if waboku:
                    assert waboku_used
                    assert observation.life_points == (7200, 8000)
                    assert own.deck_counts[0] == 30
                    assert len(own.hand) == 6
                    assert SEVEN_COLORED_FISH not in {
                        c.code for c in observation.graveyards[1]}
                    assert WABOKU in {c.code for c in observation.graveyards[1]}
                else:
                    assert observation.life_points == (7200, 6900)
                    assert own.deck_counts[0] == 29
                    assert len(own.hand) == 7
                    assert SEVEN_COLORED_FISH in {
                        c.code for c in observation.graveyards[1]}
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{AIRKNIGHT}.lua" in loaded
                if waboku:
                    assert f"official/c{WABOKU}.lua" in loaded
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Airknight battle did not reach its draw/no-draw outcome")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_airknight_draw_resolves_before_attacked_dekoichi_flip_draw(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, PREMATURE_BURIAL, AIRKNIGHT, DEKOICHI):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "airknight.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, AIRKNIGHT,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    opponent = tmp_path / "dekoichi.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        DEKOICHI, DEKOICHI, DEKOICHI, *VANILLA_DECK[3:])))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = premature = dekoichi_set = attacked = False
        air_chain_seen = dekoichi_chain_seen = False
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not graceful:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    if option is not None:
                        action = option
                        graceful = True
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"]
                                   for c in a.parameters["cards"]} == {
                                       AIRKNIGHT, SECOND_DISCARD}), None)
                    discarded = action is not None
                if discarded and not premature:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE_BURIAL), None)
                    if option is not None:
                        action = option
                        premature = True
                if premature and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == AIRKNIGHT
                                   and a.parameters.get("location") == 16), action)
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not dekoichi_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), action)
                dekoichi_set |= action is not None and action.kind == "set_monster"
            if observation.turn == 3 and observation.acting_player == 0:
                if observation.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if observation.phase == "battle_start" and not attacked:
                    hidden = next(c for c in observation.field
                                  if c.zone == "monster" and c.controller == 1)
                    assert hidden.code is None and hidden.position == "facedown"
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == AIRKNIGHT), action)
                    attacked = action is not None and action.kind == "attack"
                if attacked and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") is None
                                   and a.parameters.get("location") == 4), action)
            if observation.turn == 3 and observation.phase == "damage_step" \
                    and observation.chain:
                code = observation.chain[0].card_code
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                if code == AIRKNIGHT:
                    assert not dekoichi_chain_seen
                    assert observation.life_points == (7200, 7100)
                    assert own.deck_counts[0] == 30 and len(own.hand) == 6
                    assert other.deck_counts[1] == 34 and len(other.hand) == 5
                    air_chain_seen = True
                elif code == DEKOICHI:
                    assert air_chain_seen
                    assert own.deck_counts[0] == 29 and len(own.hand) == 7
                    assert other.deck_counts[1] == 34 and len(other.hand) == 5
                    dekoichi_chain_seen = True
            if dekoichi_chain_seen and observation.turn == 3 \
                    and observation.phase == "battle_step" \
                    and observation.acting_player == 0:
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                assert observation.life_points == (7200, 7100)
                assert own.deck_counts[0] == 29 and len(own.hand) == 7
                assert other.deck_counts[1] == 33 and len(other.hand) == 6
                assert DEKOICHI in {c.code for c in observation.graveyards[1]}
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{AIRKNIGHT}.lua" in loaded
                assert f"official/c{DEKOICHI}.lua" in loaded
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Airknight and Dekoichi draw ordering was not reached")
