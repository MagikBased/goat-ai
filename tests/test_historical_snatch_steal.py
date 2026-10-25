"""Common GOAT control staple: Snatch Steal removed by Heavy Storm."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SNATCH_STEAL = 45986603
HEAVY_STORM = 19613556


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_snatch_steal_upkeep_and_heavy_storm_return_control(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SNATCH_STEAL, HEAVY_STORM):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "control_staples.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        SNATCH_STEAL, HEAVY_STORM, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = snatched = stormed = False
        stolen_code = None
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                summoned |= action is not None
                if action is not None:
                    stolen_code = action.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0 and not snatched:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH_STEAL), action)
                snatched |= action is not None and action.kind == "activate"
            if observation.turn == 5 and observation.acting_player == 0 and not stormed:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY_STORM), action)
                stormed |= action is not None and action.kind == "activate"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            monsters = [card for card in observation.field
                        if card.zone == "monster" and card.code == stolen_code]
            snatch_on_field = any(card.code == SNATCH_STEAL for card in observation.field)
            if (snatched and observation.turn == 3 and monsters and snatch_on_field
                    and monsters[0].controller == 0):
                assert observation.life_points == (8000, 8000)
            if observation.turn == 4 and observation.phase == "main1":
                assert snatched
                assert monsters and monsters[0].controller == 0
                assert observation.life_points == (8000, 9000)
            if stormed and any(card.code == HEAVY_STORM
                               for card in observation.graveyards[0]):
                assert monsters and monsters[0].controller == 1
                assert not snatch_on_field
                assert any(card.code == SNATCH_STEAL
                           for card in observation.graveyards[0])
                assert observation.life_points == (8000, 9000)
                return
    pytest.fail("Snatch Steal and Heavy Storm did not complete their control sequence")
