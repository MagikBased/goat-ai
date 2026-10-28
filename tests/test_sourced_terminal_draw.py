"""A sourced-deck Ring double knockout exposes the native terminal state."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ROOT = Path(__file__).resolve().parent.parent
WARRIOR = ROOT / "examples/decks/warrior_montague_clash.ydk"
CHAOS_RETURN = ROOT / "examples/decks/chaos_return_dingosig_worlds_2022.ydk"
FLIP_CONTROL = ROOT / "examples/decks/flip_control_goatformat_guide.ydk"
RING = 511000824
BLS = 504700118
DEKOICHI = 87621407


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("opponent,seed,pre_lp,target,target_atk,decisions", [
    (CHAOS_RETURN, 9501, (225, 575), BLS, 3000, 429),
    (FLIP_CONTROL, 9600, (25, 275), DEKOICHI, 1400, 1024),
])
def test_ring_double_knockout_returns_current_terminal_observation(
        tmp_path, opponent, seed, pre_lp, target, target_atk, decisions):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    with GoatEnvironment(str(WARRIOR), str(opponent), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        agents = (RandomAgent(seed), RandomAgent(seed))
        for _ in range(3000):
            action = agents[observation.acting_player].select_action(
                observation, env.legal_actions())
            observation = env.step(action)
            if env.is_terminal():
                break
        else:
            pytest.fail("sourced duel exceeded 3000 decisions")
        assert env.result() is None
        loaded = env.engine.probe.loaded_script_sha256
        assert f"pre-errata/c{RING}.lua" in loaded
        if target == BLS:
            assert f"goat/c{BLS}.lua" in loaded
        else:
            assert f"official/c{DEKOICHI}.lua" in loaded
        assert observation.life_points == (0, 0)
        assert env.legal_actions() == ()
        trajectory = env.trajectory()
        assert trajectory.schema_version == 26
        assert trajectory.terminal_observation == observation
        assert len(trajectory.decisions) == decisions
        assert trajectory.decisions[-1].observation.life_points == pre_lp
        assert any(record.selected_action.kind == "chain"
                   and record.selected_action.parameters.get("code") == RING
                   for record in trajectory.decisions[-5:])
        assert any(card.code == target and card.attack == target_atk
                   for card in trajectory.decisions[-3].observation.field)
        path = tmp_path / "draw.json"
        write_trajectory(path, trajectory)
        restored = read_trajectory(path)
        assert restored == trajectory
        assert verify_trajectory(restored, ExperimentalOcgcoreEngine(root)) == decisions
