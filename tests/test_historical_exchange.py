"""Exchange reveals each hand only to the player choosing from it."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

EXCHANGE = 5556668


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_exchange_choices_use_recipient_scoped_hand_reveals(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{EXCHANGE}.lua").is_file():
        pytest.skip("Exchange script not installed")
    deck = tmp_path / "exchange.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (EXCHANGE, *VANILLA_DECK[1:])))
                    + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        picked = {}
        for _ in range(15):
            actions = env.legal_actions()
            if actions[0].kind == "select_card":
                player = observation.acting_player
                assert player not in picked
                assert all(action.parameters["controller"] == 1 - player
                           and action.parameters["location"] == 2
                           and "sequence" not in action.parameters for action in actions)
                revealed = [card.code for event in observation.private_reveals
                            if event.recipient == player
                            for card in event.cards
                            if card.controller == 1 - player and card.location == 2]
                assert Counter(action.parameters["code"] for action in actions) == Counter(
                    revealed)
                other_view = env.engine.probe.observation(1 - player)
                assert all(event.recipient == 1 - player
                           for event in other_view.private_reveals)
                picked[player] = actions[0].parameters["code"]
                action = actions[0]
            else:
                action = next((choice for choice in actions
                               if choice.kind == "activate"
                               and choice.parameters.get("code") == EXCHANGE), None)
                if action is None:
                    action = next((choice for choice in actions if choice.kind == "place"), None)
                if action is None:
                    action = next((choice for choice in actions if choice.kind == "pass"),
                                  actions[0])
            observation = env.step(action)
            if len(picked) == 2:
                assert picked[0] in {card.code for card in observation.hand}
                second_view = env.engine.probe.observation(1)
                assert picked[1] in {card.code for card in second_view.hand}
                return
    pytest.fail("Exchange did not complete both hand selections")
