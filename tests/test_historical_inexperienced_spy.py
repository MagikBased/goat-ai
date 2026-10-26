"""The Inexperienced Spy chooses a hidden hand card before its private reveal."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

SPY = 81820689


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_spy_blind_hand_choice_reveals_only_selected_card_to_activator(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = tmp_path / "spy.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (SPY, *VANILLA_DECK[1:])))
                    + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", 3,
                         ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert SPY in {card.code for card in observation.hand}
        chosen = False
        checked_reveal = False
        random_agent = RandomAgent(3)
        for _ in range(3000):
            legal = env.legal_actions()
            if legal[0].kind == "select_card" and not chosen:
                assert observation.acting_player == 0
                assert len(legal) == observation.opponent_hand_count
                assert all(action.parameters == {"controller": 1, "location": 2}
                           for action in legal)
                assert not observation.private_reveals
                action = legal[0]
                chosen = True
            elif not chosen:
                action = next((option for option in legal
                               if option.kind == "activate"
                               and option.parameters.get("code") == SPY), None)
                if action is None:
                    action = next((option for option in legal if option.kind == "place"), None)
                if action is None:
                    action = next((option for option in legal if option.kind == "pass"),
                                  legal[0])
            else:
                action = random_agent.select_action(observation, legal)
            observation = env.step(action)
            if (chosen and not checked_reveal
                    and any(event.recipient == 0 for event in observation.private_reveals)):
                revealed = [card.code for event in observation.private_reveals
                            for card in event.cards if event.recipient == 0]
                assert len(revealed) == 1
                assert revealed[0] in observation.known_opponent_hand_cards
                opponent = env.engine.probe.observation(1)
                assert all(event.recipient == 1 for event in opponent.private_reveals)
                checked_reveal = True
            if env.is_terminal():
                trajectory = env.trajectory()
                assert chosen and checked_reveal
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                return
    pytest.fail("The Inexperienced Spy duel did not terminate")
