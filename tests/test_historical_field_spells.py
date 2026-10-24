"""Historical Field Spell replacement regression; source in docs/goat_rules.md."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

NECROVALLEY_PRE_ERRATA = 511002998
A_LEGENDARY_OCEAN = 295517
MYSTICAL_SPACE_TYPHOON = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_resolved_new_field_spell_destroys_old_faceup_field_spell(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/pre-errata/c511002998.lua").is_file():
        pytest.skip("full card script checkout not installed")
    paths = []
    for name, code in (("necrovalley", NECROVALLEY_PRE_ERRATA),
                       ("ocean", A_LEGENDARY_OCEAN)):
        main = (code,) + VANILLA_DECK[1:]
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, main)) + "\n")
        paths.append(path)

    with GoatEnvironment(*(str(path) for path in paths), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        activated = set()
        for _ in range(40):
            choices = env.legal_actions()
            code = NECROVALLEY_PRE_ERRATA if observation.acting_player == 0 else A_LEGENDARY_OCEAN
            action = None
            if code not in activated:
                action = next((choice for choice in choices if choice.kind == "activate"
                               and choice.parameters.get("code") == code), None)
                if action is not None:
                    activated.add(code)
            if action is None:
                action = next((choice for choice in choices
                               if choice.kind == "end_phase"), None)
            if action is None:
                action = next((choice for choice in choices if choice.kind == "pass"),
                              choices[0])
            observation = env.step(action)
            if activated == {NECROVALLEY_PRE_ERRATA, A_LEGENDARY_OCEAN} and (
                observation.turn == 3 and observation.acting_player == 0
            ):
                field_spells = {(card.controller, card.code) for card in observation.field
                                if card.zone == "spell_trap" and card.sequence == 5}
                assert field_spells == {(1, A_LEGENDARY_OCEAN)}
                assert any(card.code == NECROVALLEY_PRE_ERRATA
                           for card in observation.graveyards[0])
                return
        pytest.fail("field spell replacement did not resolve within 40 decisions")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_destroying_new_field_spell_in_chain_preserves_old_one(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/pre-errata/c511002998.lua").is_file():
        pytest.skip("full card script checkout not installed")
    deck0 = list(VANILLA_DECK)
    deck0[:2] = [NECROVALLEY_PRE_ERRATA, MYSTICAL_SPACE_TYPHOON]
    deck1 = (A_LEGENDARY_OCEAN,) + VANILLA_DECK[1:]
    paths = []
    for name, cards in (("necro_mst", deck0), ("ocean", deck1)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n")
        paths.append(path)

    with GoatEnvironment(*(str(path) for path in paths), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        activated_necro = set_mst = activated_ocean = chained_mst = False
        for _ in range(60):
            choices = env.legal_actions()
            action = None
            if observation.acting_player == 0 and observation.turn == 1:
                if not activated_necro:
                    action = next((choice for choice in choices if choice.kind == "activate"
                                   and choice.parameters.get("code") == NECROVALLEY_PRE_ERRATA),
                                  None)
                    activated_necro |= action is not None
                elif not set_mst:
                    action = next((choice for choice in choices
                                   if choice.kind == "set_spell_trap"
                                   and choice.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                                  None)
                    set_mst |= action is not None
            if observation.acting_player == 1 and observation.turn == 2 and not activated_ocean:
                action = next((choice for choice in choices if choice.kind == "activate"
                               and choice.parameters.get("code") == A_LEGENDARY_OCEAN), None)
                activated_ocean |= action is not None
            if observation.acting_player == 0 and observation.turn == 2 and (
                activated_ocean and not chained_mst
            ):
                action = next((choice for choice in choices if choice.kind == "chain"
                               and choice.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                              None)
                chained_mst |= action is not None
            if action is None and chained_mst:
                action = next((choice for choice in choices if choice.kind == "select_card"
                               and choice.parameters.get("code") == A_LEGENDARY_OCEAN), None)
            if action is None:
                action = next((choice for choice in choices
                               if choice.kind == "end_phase"), None)
            if action is None:
                action = next((choice for choice in choices if choice.kind == "pass"),
                              choices[0])
            observation = env.step(action)
            if chained_mst and any(card.code == A_LEGENDARY_OCEAN
                                   for card in observation.graveyards[1]):
                assert activated_necro and set_mst and activated_ocean
                field_spells = {(card.controller, card.code) for card in observation.field
                                if card.zone == "spell_trap" and card.sequence == 5}
                assert field_spells == {(0, NECROVALLEY_PRE_ERRATA)}
                assert not any(card.code == NECROVALLEY_PRE_ERRATA
                               for card in observation.graveyards[0])
                return
        pytest.fail("chained field spell destruction did not resolve within 60 decisions")
