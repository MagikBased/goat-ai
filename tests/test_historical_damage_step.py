"""A real battle checks the GOAT Damage Step's activation boundary."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BOOK_OF_MOON = 14087893
COMPULSORY = 94192409
RING = 511000824
SCAPEGOAT = 504700123
DEKOICHI = 87621407


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("response_code", [BOOK_OF_MOON, COMPULSORY, RING, SCAPEGOAT])
def test_battle_step_response_unavailable_after_defender_flips(tmp_path, response_code):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    response_script = (f"pre-errata/c{RING}.lua" if response_code == RING
                       else f"goat/c{SCAPEGOAT}.lua" if response_code == SCAPEGOAT
                       else f"official/c{response_code}.lua")
    if not (root / f"scripts/official/c{DEKOICHI}.lua").is_file() or not (
            root / "scripts" / response_script).is_file():
        pytest.skip("full card script checkout not installed")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    defender = list(read_ydk(decks / "book_three_probe.ydk").main)
    if response_code == RING:
        defender[:4] = [RING, DEKOICHI, DEKOICHI, DEKOICHI]
    else:
        defender[:3] = [response_code] * 3
        defender[3] = DEKOICHI
    defender_path = tmp_path / "defender.ydk"
    defender_path.write_text("#main\n" + "\n".join(map(str, defender)) + "\n")

    with GoatEnvironment(str(decks / "vanilla_probe.ydk"), str(defender_path),
                         seed=7 if response_code == RING else 48,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = set_monster = set_response = attacked = False
        response_available_on_attack = response_barred_after_flip = False
        defender_deck_before_flip = None
        for _ in range(70):
            choices = env.legal_actions()

            def choice(kind, code=None, actions=choices):
                return next((action for action in actions if action.kind == kind
                             and (code is None or action.parameters.get("code") == code)), None)

            defender_faceup = any(card.controller == 1 and card.code == DEKOICHI
                                  and card.position == "faceup" for card in observation.field)
            if attacked and observation.acting_player == 1:
                response = choice("chain", response_code)
                if not defender_faceup and response is not None:
                    response_available_on_attack = True
                    assert observation.phase == "battle_step"
                if defender_faceup and not response_barred_after_flip:
                    assert response_available_on_attack
                    assert set_response
                    assert observation.phase == "damage_step"
                    assert any(card.controller == 1 and card.zone == "spell_trap"
                               and card.code == response_code for card in observation.field)
                    if response_code == RING:
                        assert any(card.controller == 0 and card.zone == "monster"
                                   and card.position == "faceup" for card in observation.field)
                    assert response is None
                    assert response_script in env.engine.probe.loaded_script_sha256
                    response_barred_after_flip = True
                    defender_deck_before_flip = observation.deck_counts[1]
            if (response_barred_after_flip and defender_deck_before_flip is not None
                    and observation.deck_counts[1] == defender_deck_before_flip - 1):
                assert response_available_on_attack
                assert any(card.code == DEKOICHI for card in observation.field)
                agents = (RandomAgent(480), RandomAgent(481))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    legal = env.legal_actions()
                    observation = env.step(agents[observation.acting_player].select_action(
                        observation, legal))
                assert env.is_terminal()
                path = tmp_path / f"damage_step_{response_code}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return

            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = choice("normal_summon")
                summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not set_monster:
                    action = choice("set_monster", DEKOICHI)
                    set_monster |= action is not None
                if action is None and not set_response:
                    action = choice("set_spell_trap", response_code)
                    set_response |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and (
                summoned and set_monster and set_response
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
