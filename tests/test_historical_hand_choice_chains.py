"""Nested blind choices and delayed addressed hand reveals stay separate."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory
from scripts.probe_random_decks import generate_deck, write_deck


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("seed,source,visible", (
    (10093, 24096228, False),  # Double Spell copies The Inexperienced Spy.
    (10107, 16435215, True),  # Dragged Down into the Grave reveals both hands.
))
def test_opponent_hand_choice_after_response_window(tmp_path, seed, source, visible):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = (tmp_path / "first.ydk", tmp_path / "second.ydk")
    write_deck(decks[0], generate_deck(root, seed))
    write_deck(decks[1], generate_deck(root, seed + 1_000_000))
    found = False
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        agent = RandomAgent(seed)
        for _ in range(3000):
            actions = env.legal_actions()
            if (observation.chain and observation.chain[-1].card_code == source
                    and actions and all(action.kind == "select_card"
                                        and action.parameters.get("location") == 2
                                        and action.parameters.get("controller") ==
                                        1 - observation.viewer for action in actions)):
                found = True
                assert all("sequence" not in action.parameters for action in actions)
                reveals = [reveal for reveal in observation.private_reveals
                           if reveal.recipient == observation.viewer
                           and reveal.turn == observation.turn]
                if visible:
                    assert reveals
                    codes = {card.code for reveal in reveals for card in reveal.cards
                             if card.controller == 1 - observation.viewer
                             and card.location == 2}
                    assert {action.parameters["code"] for action in actions} <= codes
                else:
                    assert all("code" not in action.parameters for action in actions)
            observation = env.step(agent.select_action(observation, actions))
            if env.is_terminal():
                break
        assert found
        assert env.is_terminal()
        trajectory = env.trajectory()
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
        audit_trajectory_visibility(trajectory)
