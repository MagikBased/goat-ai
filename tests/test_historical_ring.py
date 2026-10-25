"""Pre-errata Ring of Destruction may destroy either player's monster."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

RING_PRE_ERRATA = 511000824
GEMINI_ELF = 49881766
BREAKER = 71413901
BOOK_OF_MOON = 14087893


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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_ring_after_breaker_cost_uses_1600_and_breaker_still_destroys_target(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"pre-errata/c{RING_PRE_ERRATA}.lua",
                     f"official/c{BREAKER}.lua", f"official/c{BOOK_OF_MOON}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "breaker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "ring_book.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        RING_PRE_ERRATA, BOOK_OF_MOON, BOOK_OF_MOON, BOOK_OF_MOON,
        *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_ring = set_book = summoned = breaker_used = ring_chained = False
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1:
                if not set_ring:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING_PRE_ERRATA), None)
                    set_ring |= action is not None
                if action is None and not set_book:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    set_book |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), action)
                summoned |= action is not None and action.kind == "normal_summon"
            if summoned and observation.acting_player == 0 and not breaker_used:
                effect = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BREAKER), None)
                if effect is not None:
                    breaker = next(card for card in observation.field
                                   if card.code == BREAKER)
                    assert (breaker.attack, breaker.defense, breaker.counters) == (
                        1900, 1000, ((1, 1),))
                    action = effect
                    breaker_used = True
            if breaker_used and observation.acting_player == 1 and not ring_chained:
                ring = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == RING_PRE_ERRATA), None)
                if ring is not None:
                    action = ring
                    ring_chained = True
            if (action is None and breaker_used and not ring_chained
                    and observation.acting_player == 0
                    and actions[0].kind == "select_card"):
                breaker = next(card for card in observation.field
                               if card.code == BREAKER)
                assert (breaker.attack, breaker.defense, breaker.counters) == (
                    1600, 1000, ())
                # Player 0 chooses a field slot; the set Book identity is hidden.
                assert {a.parameters.get("sequence") for a in actions} == {0, 1}
                assert all("code" not in a.parameters for a in actions)
                action = next(a for a in actions if a.parameters["sequence"] == 1)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            observation = env.step(action)
            if ring_chained and any(card.code == RING_PRE_ERRATA
                                    for card in observation.graveyards[1]):
                assert set_ring and set_book and summoned and breaker_used
                assert observation.life_points == (6400, 6400)
                assert any(card.code == BREAKER for card in observation.graveyards[0])
                assert ({card.code for card in observation.graveyards[1]}
                        >= {RING_PRE_ERRATA, BOOK_OF_MOON})
                assert not any(card.zone in ("monster", "spell_trap")
                               for card in observation.field)
                assert f"pre-errata/c{RING_PRE_ERRATA}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Breaker / pre-errata Ring chain did not resolve")
