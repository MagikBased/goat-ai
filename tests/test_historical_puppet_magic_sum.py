"""Puppet Magic's Level-sum request is exposed as valid field-card actions."""

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
@pytest.mark.parametrize("seed", (10097, 10102))
def test_puppet_magic_sum_choices_finish_seeded_duel(tmp_path, seed):
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
            if (observation.chain and observation.chain[-1].card_code == 40703393
                    and actions and all(action.kind in ("select_card", "select_cards")
                                        for action in actions)
                    and all(action.parameters.get("location") == 4
                            or action.kind == "select_cards" for action in actions)):
                found = True
                own_field_codes = {card.code for card in observation.field
                                   if card.zone == "monster"
                                   and card.controller == observation.viewer}
                for action in actions:
                    if action.kind == "select_card":
                        assert action.parameters["code"] in own_field_codes
                    else:
                        assert {card["code"] for card in action.parameters["cards"]} \
                            <= own_field_codes
            observation = env.step(agent.select_action(observation, actions))
            if env.is_terminal():
                break
        assert found
        assert env.is_terminal()
        trajectory = env.trajectory()
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
        audit_trajectory_visibility(trajectory)
