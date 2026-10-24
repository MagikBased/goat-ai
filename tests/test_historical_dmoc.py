"""Pre-errata Dark Magician of Chaos retrieves a Spell on Normal Summon."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DMOC = 511001039
POT_OF_GREED = 55144522


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_pre_errata_dmoc_retrieves_pot_after_tribute_summon(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/pre-errata/c{DMOC}.lua").is_file():
        pytest.skip("full pre-errata card script checkout not installed")
    deck = tmp_path / "dmoc.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (POT_OF_GREED, DMOC,
                                                   *VANILLA_DECK[2:]))) + "\n")
    opponent = Path(__file__).resolve().parent.parent / "examples/decks/vanilla_probe.ydk"

    with GoatEnvironment(str(deck), str(opponent), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        pot_activated = dmoc_summoned = dmoc_effect_accepted = spell_target_selected = False
        normal_monsters_summoned = 0
        for _ in range(80):
            choices = env.legal_actions()
            if dmoc_effect_accepted and any(card.code == POT_OF_GREED
                                            for card in observation.hand):
                assert dmoc_summoned and spell_target_selected
                assert normal_monsters_summoned == 2
                assert any(card.code == DMOC and card.position == "faceup"
                           for card in observation.field)
                assert not any(card.code == POT_OF_GREED
                               for card in observation.graveyards[0])
                assert "pre-errata/c511001039.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return

            action = None
            if observation.acting_player == 0:
                if not pot_activated:
                    action = next((choice for choice in choices
                                   if choice.kind == "activate"
                                   and choice.parameters.get("code") == POT_OF_GREED), None)
                    pot_activated |= action is not None
                if (action is None and normal_monsters_summoned < 2
                        and observation.turn in (1, 3)):
                    action = next((choice for choice in choices
                                   if choice.kind == "normal_summon"), None)
                    normal_monsters_summoned += action is not None
                if action is None and observation.turn >= 5 and not dmoc_summoned:
                    action = next((choice for choice in choices
                                   if choice.kind == "normal_summon"
                                   and choice.parameters.get("code") == DMOC), None)
                    dmoc_summoned |= action is not None
                if action is None and dmoc_summoned:
                    action = next((choice for choice in choices
                                   if choice.kind == "tribute_cards"), None)
                    if action is None:
                        action = next((choice for choice in choices
                                       if choice.kind == "yes"
                                       and choice.parameters.get("code") == DMOC), None)
                        dmoc_effect_accepted |= action is not None
                    if action is None:
                        action = next((choice for choice in choices
                                       if choice.kind == "select_card"
                                       and choice.parameters.get("code") == POT_OF_GREED), None)
                        spell_target_selected |= action is not None
            if action is None:
                action = next((choice for choice in choices
                               if choice.kind == "end_phase"), None)
            if action is None:
                action = next((choice for choice in choices
                               if choice.kind == "pass"), choices[0])
            observation = env.step(action)
        pytest.fail("Dark Magician of Chaos did not retrieve Pot within 80 decisions")
