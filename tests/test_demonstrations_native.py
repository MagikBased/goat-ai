"""The demonstrated seat is selected only after a real duel is replay-verified."""

import os
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.agents import HeuristicAgent, RandomAgent
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import demonstrator_records, verify_trajectory


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_heuristic_demonstration_from_verified_native_duel():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = Path(__file__).resolve().parent.parent / "examples/decks/vanilla_probe.ydk"
    with GoatEnvironment(str(deck), str(deck), seed=1000,
                         engine=RestrictedOcgcoreEngine(root)) as env:
        observation = env.reset()
        agents = (HeuristicAgent(), RandomAgent(1000))
        for _ in range(5000):
            action = agents[observation.acting_player].select_action(
                observation, env.legal_actions())
            observation = env.step(action)
            if env.is_terminal():
                break
        else:
            pytest.fail("native heuristic duel exceeded 5000 decisions")
        trajectory = replace(env.trajectory(), source="heuristic",
                             skill_metadata={"demonstrator_seat": 0})

    assert verify_trajectory(trajectory, RestrictedOcgcoreEngine(root)) == len(
        trajectory.decisions)
    selected = demonstrator_records(trajectory)
    assert 0 < len(selected) < len(trajectory.decisions)
    assert all(record.observation.acting_player == 0 for record in selected)
    assert any(record.observation.acting_player == 1
               for record in trajectory.decisions)
