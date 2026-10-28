"""A Dark Elf attack can require ordering its cost alongside Toll's."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from scripts.probe_random_decks import generate_deck, write_deck

DARK_ELF = 21417692
TOLL_GOAT = 504700141


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("sort_choice", (0, 1))
def test_random_whitelist_duel_orders_dark_elf_and_toll_chain(tmp_path, sort_choice):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    seed = 10527
    own = tmp_path / "sort_chain_own.ydk"
    opponent = tmp_path / "sort_chain_opponent.ydk"
    write_deck(own, generate_deck(root, seed))
    write_deck(opponent, generate_deck(root, seed + 1_000_000))

    with GoatEnvironment(str(own), str(opponent), seed,
                         ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        agent = RandomAgent(seed)
        sort_decisions = 0
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            if actions[0].kind == "sort_cards":
                sort_decisions += 1
                assert obs.turn == 39 and obs.phase == "battle_step"
                assert obs.acting_player == 0
                assert obs.life_points == (3300, 7500)
                assert not obs.chain
                assert len(actions) == 2
                assert {tuple(card["code"] for card in a.parameters["cards"])
                        for a in actions} == {
                    (DARK_ELF, TOLL_GOAT), (TOLL_GOAT, DARK_ELF)}
                assert all(card["location"] in (4, 8)
                           for action in actions for card in action.parameters["cards"])
                action = actions[sort_choice]
            else:
                action = agent.select_action(obs, actions)
            obs = env.step(action)
            if action.kind == "sort_cards":
                assert obs.life_points == (1800, 7500)
                assert not obs.chain
        assert sort_decisions == 1
        assert env.is_terminal()
        trajectory = env.trajectory()
        path = tmp_path / "sort_chain.json"
        write_trajectory(path, trajectory)
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
