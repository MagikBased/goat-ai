"""Source-backed Solemn Judgment summon-negation regression."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment

CANNON_SOLDIER = 11384280
SOLEMN_JUDGMENT = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_solemn_negates_normal_summon_before_ignition_priority(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c41420027.lua").is_file():
        pytest.skip("full card script checkout not installed")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    opponent = list(read_ydk(decks / "book_three_probe.ydk").main)
    opponent[0] = SOLEMN_JUDGMENT
    opponent_path = tmp_path / "solemn.ydk"
    opponent_path.write_text("#main\n" + "\n".join(map(str, opponent)) + "\n")
    with GoatEnvironment(str(decks / "cannon_probe.ydk"), str(opponent_path),
                         seed=52, engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        trap_set = summon_attempted = solemn_chained = False
        for _ in range(40):
            choices = env.legal_actions()
            if solemn_chained and observation.turn == 3 and (
                observation.acting_player == 0
                and any(choice.kind == "end_phase" for choice in choices)
            ):
                assert trap_set and summon_attempted
                assert observation.life_points == (8000, 4000)
                assert not any(card.code == CANNON_SOLDIER for card in observation.field)
                assert any(card.code == CANNON_SOLDIER
                           for card in observation.graveyards[0])
                assert any(card.code == SOLEMN_JUDGMENT
                           for card in observation.graveyards[1])
                assert not any(choice.kind == "normal_summon" for choice in choices)
                assert not any(choice.kind == "chain"
                               and choice.parameters.get("code") == CANNON_SOLDIER
                               for choice in choices)
                return
            action = None
            if observation.acting_player == 1 and observation.turn == 2 and not trap_set:
                action = next((choice for choice in choices
                               if choice.kind == "set_spell_trap"
                               and choice.parameters.get("code") == SOLEMN_JUDGMENT), None)
                trap_set |= action is not None
            if observation.acting_player == 0 and observation.turn == 3 and not summon_attempted:
                action = next((choice for choice in choices
                               if choice.kind == "normal_summon"
                               and choice.parameters.get("code") == CANNON_SOLDIER), None)
                summon_attempted |= action is not None
            if observation.acting_player == 1 and observation.turn == 3 and (
                summon_attempted and not solemn_chained
            ):
                action = next((choice for choice in choices if choice.kind == "chain"
                               and choice.parameters.get("code") == SOLEMN_JUDGMENT), None)
                solemn_chained |= action is not None
            if action is None:
                action = next((choice for choice in choices
                               if choice.kind == "end_phase"), None)
            if action is None:
                action = next((choice for choice in choices if choice.kind == "pass"),
                              choices[0])
            observation = env.step(action)
        pytest.fail("Solemn summon-negation branch did not resolve within 40 decisions")
