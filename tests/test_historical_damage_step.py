"""A real battle checks the GOAT Damage Step's activation boundary."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment

BOOK_OF_MOON = 14087893
COMPULSORY = 94192409
RING = 511000824
DEKOICHI = 87621407


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("trap_code", [BOOK_OF_MOON, COMPULSORY, RING])
def test_battle_step_response_unavailable_after_defender_flips(tmp_path, trap_code):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    trap_script = (f"pre-errata/c{RING}.lua" if trap_code == RING
                   else f"official/c{trap_code}.lua")
    if not (root / f"scripts/official/c{DEKOICHI}.lua").is_file() or not (
            root / "scripts" / trap_script).is_file():
        pytest.skip("full card script checkout not installed")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    defender = list(read_ydk(decks / "book_three_probe.ydk").main)
    if trap_code == RING:
        defender[:4] = [RING, DEKOICHI, DEKOICHI, DEKOICHI]
    else:
        defender[:3] = [trap_code] * 3
        defender[3] = DEKOICHI
    defender_path = tmp_path / "defender.ydk"
    defender_path.write_text("#main\n" + "\n".join(map(str, defender)) + "\n")

    with GoatEnvironment(str(decks / "vanilla_probe.ydk"), str(defender_path),
                         seed=7 if trap_code == RING else 48,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = set_monster = set_trap = attacked = False
        trap_available_on_attack = trap_barred_after_flip = False
        defender_deck_before_flip = None
        for _ in range(70):
            choices = env.legal_actions()

            def choice(kind, code=None, actions=choices):
                return next((action for action in actions if action.kind == kind
                             and (code is None or action.parameters.get("code") == code)), None)

            defender_faceup = any(card.controller == 1 and card.code == DEKOICHI
                                  and card.position == "faceup" for card in observation.field)
            if attacked and observation.acting_player == 1:
                trap = choice("chain", trap_code)
                if not defender_faceup and trap is not None:
                    trap_available_on_attack = True
                    assert observation.phase == "battle_step"
                if defender_faceup and not trap_barred_after_flip:
                    assert trap_available_on_attack
                    assert set_trap
                    assert observation.phase == "damage_step"
                    assert any(card.controller == 1 and card.zone == "spell_trap"
                               and card.code == trap_code for card in observation.field)
                    if trap_code == RING:
                        assert any(card.controller == 0 and card.zone == "monster"
                                   and card.position == "faceup" for card in observation.field)
                    assert trap is None
                    assert trap_script in env.engine.probe.loaded_script_sha256
                    trap_barred_after_flip = True
                    defender_deck_before_flip = observation.deck_counts[1]
            if (trap_barred_after_flip and defender_deck_before_flip is not None
                    and observation.deck_counts[1] == defender_deck_before_flip - 1):
                assert trap_available_on_attack
                assert any(card.code == DEKOICHI for card in observation.field)
                return

            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = choice("normal_summon")
                summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not set_monster:
                    action = choice("set_monster", DEKOICHI)
                    set_monster |= action is not None
                if action is None and not set_trap:
                    action = choice("set_spell_trap", trap_code)
                    set_trap |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and (
                summoned and set_monster and set_trap
            ):
                if not attacked:
                    action = choice("battle_phase") or choice("attack")
                    attacked |= action is not None and action.kind == "attack"
                if attacked and action is None:
                    action = choice("select_card") or choice("pass")
            if action is None:
                action = choice("end_phase") or choice("pass") or choices[0]
            observation = env.step(action)
        pytest.fail("Damage Step regression did not complete within 70 decisions")
