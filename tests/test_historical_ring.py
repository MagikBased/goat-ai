"""Pre-errata Ring of Destruction may destroy either player's monster."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

RING_PRE_ERRATA = 511000824
GEMINI_ELF = 49881766


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_pre_errata_ring_targets_own_monster_and_damages_both_players(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/pre-errata/c{RING_PRE_ERRATA}.lua").is_file():
        pytest.skip("pre-errata Ring script not installed")
    deck = tmp_path / "ring_pre_errata.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        RING_PRE_ERRATA, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = set_ring = activated = selected = False
        for _ in range(45):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                summoned |= action is not None
            if (action is None and observation.turn == 1
                    and observation.acting_player == 0 and summoned and not set_ring):
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == RING_PRE_ERRATA), None)
                set_ring |= action is not None
            if (observation.turn == 2 and observation.acting_player == 0
                    and set_ring and not activated):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING_PRE_ERRATA), action)
                activated |= action is not None and action.kind == "chain"
            if activated and not selected:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == GEMINI_ELF
                               and a.parameters.get("controller") == 0), action)
                selected |= action is not None and action.kind == "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if (set_ring and not activated and any(
                    card.code == RING_PRE_ERRATA for card in observation.field)):
                opponent = env.engine.probe.observation(1)
                assert any(card.controller == 0 and card.zone == "spell_trap"
                           and card.position == "facedown" and card.code is None
                           for card in opponent.field)
            if selected and any(card.code == RING_PRE_ERRATA
                                for card in observation.graveyards[0]):
                assert summoned and set_ring and activated
                assert observation.life_points == (6100, 6100)
                assert any(card.code == GEMINI_ELF for card in observation.graveyards[0])
                assert not any(card.zone == "monster" for card in observation.field)
                assert f"pre-errata/c{RING_PRE_ERRATA}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("pre-errata Ring did not resolve against its controller's monster")
