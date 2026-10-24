import os
from pathlib import Path

import pytest

from goat_ai.actions import Action
from goat_ai.agents import RandomAgent
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.engine.vanilla_adapter import VanillaOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, write_trajectory


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_random_agent_completes_native_duel_and_records_visible_trajectory(tmp_path):
    deck = tmp_path / "vanilla.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK)) + "\n")
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])

    def play():
        with GoatEnvironment(str(deck), str(deck), seed=42,
                             engine=VanillaOcgcoreEngine(root)) as env:
            observation = env.reset()
            assert len(observation.hand) == 6
            with pytest.raises(ValueError, match="illegal"):
                env.step(Action("bad", "pass", 0))
            agent = RandomAgent(42)
            for _ in range(5000):
                action = agent.select_action(observation, env.legal_actions())
                observation = env.step(action)
                if env.is_terminal():
                    return env.trajectory()
            pytest.fail("native duel did not reach terminal within 5000 decisions")

    trajectory = play()
    assert trajectory == play()
    assert trajectory.winner == 1
    assert len(trajectory.decisions) > 100
    assert any(
        any(card.controller != record.observation.viewer and card.position == "facedown"
            for card in record.observation.field)
        and any(action.kind == "select_card" and "code" not in action.parameters
                for action in record.legal_actions)
        for record in trajectory.decisions
    )
    path = tmp_path / "duel.json"
    write_trajectory(path, trajectory)
    assert read_trajectory(path) == trajectory
