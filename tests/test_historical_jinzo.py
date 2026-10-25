"""Jinzo suppresses Trap activation only while face-up."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL_CHARITY = 79571449
PREMATURE_BURIAL = 70828912
JINZO = 77585513
MIRROR_FORCE = 44095762
BOOK_OF_MOON = 14087893
X_HEAD_CANNON = 62651957
SECOND_DISCARD = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_response", [False, True])
def test_jinzo_suppresses_mirror_until_book_turns_jinzo_facedown(tmp_path, book_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required_scripts = (GRACEFUL_CHARITY, PREMATURE_BURIAL, JINZO, MIRROR_FORCE)
    if book_response:
        required_scripts += (BOOK_OF_MOON,)
    for code in required_scripts:
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "jinzo.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, JINZO,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    opponent = tmp_path / "mirror.ydk"
    opponent_cards = [MIRROR_FORCE, *VANILLA_DECK[1:]]
    if book_response:
        opponent_cards[4] = BOOK_OF_MOON
    opponent.write_text("#main\n" + "\n".join(map(str, opponent_cards))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = premature = mirror_set = book_set = False
        book_used = other_attacker_summoned = attacked = mirror_used = False
        entered_damage_step = mirror_response_checked = False
        attacker = X_HEAD_CANNON if book_response else JINZO
        for _ in range(80):
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
                                       JINZO, SECOND_DISCARD}), None)
                    discarded = action is not None
                if discarded and not premature:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE_BURIAL), None)
                    if option is not None:
                        action = option
                        premature = True
                if premature and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == JINZO
                                   and a.parameters.get("location") == 16), action)
            if observation.turn == 2 and observation.acting_player == 1:
                if not mirror_set:
                    option = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MIRROR_FORCE), None)
                    if option is not None:
                        action = option
                        mirror_set = True
                if book_response and mirror_set and not book_set and action is None:
                    option = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    if option is not None:
                        action = option
                        book_set = True
            if book_response and book_set and observation.turn == 3 \
                    and observation.acting_player == 1:
                if not book_used:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    if option is not None:
                        action = option
                        book_used = True
                if book_used and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == JINZO
                                   and a.parameters.get("controller") == 0), action)
            if observation.turn == 3 and observation.acting_player == 0:
                if observation.phase == "main1":
                    if book_response and book_used and not other_attacker_summoned:
                        jinzo = next(c for c in observation.field
                                     if c.zone == "monster" and c.controller == 0)
                        assert jinzo.code == JINZO and jinzo.position == "facedown"
                        option = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == X_HEAD_CANNON), None)
                        if option is not None:
                            action = option
                            other_attacker_summoned = True
                    elif not book_response or other_attacker_summoned:
                        action = next((a for a in actions if a.kind == "battle_phase"), action)
                if observation.phase == "battle_start" and not attacked:
                    assert any(c.code == attacker and c.position == "faceup"
                               for c in observation.field)
                    assert any(c.zone == "spell_trap" and c.controller == 1
                               and c.code is None for c in observation.field)
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == attacker), action)
                    attacked = action is not None and action.kind == "attack"
            if attacked and observation.turn == 3 and observation.phase == "battle_step" \
                    and observation.acting_player == 1:
                if book_response and not mirror_used:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == MIRROR_FORCE), None)
                    if option is not None:
                        action = option
                        mirror_used = True
                elif not book_response:
                    assert not any(a.kind == "chain" and a.parameters.get("code")
                                   == MIRROR_FORCE for a in actions)
                    assert any(c.code == MIRROR_FORCE and c.position == "facedown"
                               for c in observation.field)
                    mirror_response_checked = True
            if attacked and observation.turn == 3 and observation.phase == "damage_step":
                entered_damage_step = True
            if book_response and mirror_used and observation.turn == 3 \
                    and MIRROR_FORCE in {c.code for c in observation.graveyards[1]} \
                    and any(a.kind == "main2" for a in actions):
                assert observation.life_points == (7200, 8000)
                assert X_HEAD_CANNON in {c.code for c in observation.graveyards[0]}
                assert any(c.code == JINZO and c.position == "facedown"
                           for c in observation.field)
                assert MIRROR_FORCE not in {c.code for c in observation.field}
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{JINZO}.lua" in loaded
                assert f"official/c{MIRROR_FORCE}.lua" in loaded
                assert f"official/c{BOOK_OF_MOON}.lua" in loaded
                return
            if not book_response and entered_damage_step and mirror_response_checked \
                    and observation.turn == 3 and observation.phase == "battle_step" \
                    and observation.acting_player == 0:
                assert observation.life_points == (7200, 5600)
                assert any(c.code == JINZO and c.position == "faceup"
                           for c in observation.field)
                other = env.engine.probe.observation(1)
                assert any(c.code == MIRROR_FORCE and c.position == "facedown"
                           for c in other.field)
                assert f"official/c{JINZO}.lua" in env.engine.probe.loaded_script_sha256
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Jinzo / Mirror Force line did not reach its expected outcome")
