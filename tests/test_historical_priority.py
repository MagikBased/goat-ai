"""Native GOAT priority fixture; historical source recorded in docs/goat_rules.md."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments import GoatEnvironment

CANNON_SOLDIER = 11384280
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_turn_player_ignition_priority_before_opponents_set_book():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = Path(__file__).resolve().parent.parent / "examples/decks"

    def branch(use_ignition: bool) -> None:
        with GoatEnvironment(str(decks / "cannon_probe.ydk"),
                             str(decks / "book_three_probe.ydk"), seed=18,
                             engine=RestrictedOcgcoreEngine(root)) as env:
            observation = env.reset()
            book_set = False
            cannon_summoned = False
            priority_seen = False
            book_response_seen = False
            cannon_cost_paid = False
            for _ in range(40):
                choices = env.legal_actions()
                action = None
                if observation.turn == 1 and observation.acting_player == 0:
                    action = next((a for a in choices if a.kind == "end_phase"), None)
                elif observation.turn == 2 and observation.acting_player == 1:
                    if not book_set:
                        action = next((a for a in choices if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == BOOK_OF_MOON), None)
                        book_set |= action is not None
                    if action is None:
                        action = next((a for a in choices if a.kind == "end_phase"), None)
                elif observation.turn == 3 and observation.acting_player == 0:
                    if not cannon_summoned:
                        action = next((a for a in choices if a.kind == "normal_summon"
                                       and a.parameters.get("code") == CANNON_SOLDIER), None)
                        cannon_summoned |= action is not None
                    cannon_option = next((a for a in choices if a.kind == "chain"
                                          and a.parameters.get("code") == CANNON_SOLDIER), None)
                    if cannon_option is not None:
                        assert book_set and cannon_summoned
                        priority_seen = True
                        action = cannon_option if use_ignition else next(
                            a for a in choices if a.kind == "pass")
                    if use_ignition and action is None:
                        action = next((a for a in choices if a.kind == "select_card"
                                       and a.parameters.get("code") == CANNON_SOLDIER), None)
                        cannon_cost_paid |= action is not None
                if priority_seen and observation.acting_player == 1:
                    book_option = next((a for a in choices if a.kind == "chain"
                                        and a.parameters.get("code") == BOOK_OF_MOON), None)
                    if use_ignition:
                        assert book_option is None
                    elif book_option is not None:
                        book_response_seen = True
                        action = book_option
                if action is None:
                    action = next((a for a in choices if a.kind == "pass"), choices[0])
                observation = env.step(action)
                if use_ignition and observation.life_points[1] == 7500:
                    assert priority_seen and cannon_cost_paid
                    assert not any(card.code == CANNON_SOLDIER for card in observation.field)
                    return
                if not use_ignition and book_response_seen and any(
                    card.controller == 0 and card.position == "facedown"
                    for card in observation.field
                ):
                    assert observation.life_points == (8000, 8000)
                    return
            pytest.fail("priority branch did not resolve within 40 decisions")

    branch(True)
    branch(False)
