"""Historical Snatch Steal / Book of Moon control and field memory."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SNATCH_STEAL = 45986603
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_on_snatch_stolen_monster_keeps_control_and_known_identity(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SNATCH_STEAL, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "snatch_book.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        SNATCH_STEAL, BOOK_OF_MOON, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = snatched = booked = False
        summoned_code = None
        for _ in range(50):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summoned = True
                    summoned_code = action.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0 and not snatched:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH_STEAL), action)
                snatched |= action is not None and action.kind == "activate"
            stolen = next((card for card in observation.field
                           if card.zone == "monster" and card.controller == 0
                           and card.code == summoned_code), None)
            if (observation.turn == 3 and observation.acting_player == 0
                    and snatched and not booked and stolen is not None):
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BOOK_OF_MOON), action)
                booked |= action is not None and action.kind == "activate"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")), actions[0])
            if action.kind == "select_card" and booked:
                assert action.parameters["code"] == summoned_code
                assert action.parameters["controller"] == 0
            observation = env.step(action)
            own = env.engine.probe.observation(0)
            if booked and {SNATCH_STEAL, BOOK_OF_MOON}.issubset(
                    {card.code for card in own.graveyards[0]}):
                facedown = next(card for card in own.field
                                if card.zone == "monster" and card.controller == 0)
                assert facedown.code == summoned_code
                assert facedown.position == "facedown"
                assert not any(card.code == SNATCH_STEAL for card in own.field)
                opponent = env.engine.probe.observation(1)
                hidden = next(card for card in opponent.field
                              if card.zone == "monster" and card.controller == 0)
                assert hidden.code is None and hidden.position == "facedown"
                assert (0, "monster", hidden.sequence, summoned_code) in {
                    (card.controller, card.zone, card.sequence, card.code)
                    for card in opponent.known_opponent_field_cards}
                return
    pytest.fail("Snatch Steal / Book of Moon did not reach the face-down outcome")
