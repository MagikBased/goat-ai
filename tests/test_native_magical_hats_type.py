"""A Magical Hats Spell/Trap in a Monster Zone has no monster Type."""

import os
from pathlib import Path

import pytest

from scripts.probe_random_decks import generate_deck, write_deck
from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory


ENERGY_DRAIN_GOAT = 504700090


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_magical_hats_spell_trap_flipped_in_monster_zone(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own = tmp_path / "own.ydk"
    opponent = tmp_path / "opponent.ydk"
    write_deck(own, generate_deck(root, 10247))
    write_deck(opponent, generate_deck(root, 10247 + 1_000_000))

    saw_typeless_hats_card = False
    with GoatEnvironment(str(own), str(opponent), 10247,
                         ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        agent = RandomAgent(10247)
        for _ in range(3000):
            for card in observation.field:
                if (card.code == ENERGY_DRAIN_GOAT and card.zone == "monster"
                        and card.position == "faceup"):
                    assert card.race is None
                    assert (card.attack, card.defense) == (0, 0)
                    saw_typeless_hats_card = True
            if env.is_terminal():
                break
            observation = env.step(agent.select_action(observation, env.legal_actions()))
        else:
            pytest.fail("Magical Hats fixture exceeded 3000 decisions")
        assert saw_typeless_hats_card
        trajectory = env.trajectory()

    path = tmp_path / "magical_hats.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    audit_trajectory_visibility(loaded)
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
