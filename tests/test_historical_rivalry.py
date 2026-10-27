"""Rivalry must let its controller keep one face-up Type without native recursion."""

import os
from pathlib import Path

import pytest

from scripts.probe_random_decks import generate_deck, write_deck
from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import UPSTREAM_GOAT_RIVALRY_SHA256
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CHAOS_NECROMANCER = 1434352  # Fiend
BIRDFACE_GOAT = 504700073  # Winged Beast
RIVALRY_GOAT = 504700158


@pytest.mark.parametrize(
    ("keep_race", "kept", "sent"),
    [(8, CHAOS_NECROMANCER, BIRDFACE_GOAT),
     (512, BIRDFACE_GOAT, CHAOS_NECROMANCER)],
)
@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_rivalry_type_choice_sends_other_monster_and_duel_completes(
        tmp_path, keep_race, kept, sent):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own = tmp_path / "own.ydk"
    opponent = tmp_path / "opponent.ydk"
    write_deck(own, generate_deck(root, 10227))
    write_deck(opponent, generate_deck(root, 10227 + 1_000_000))

    selected = False
    with GoatEnvironment(str(own), str(opponent), 10227,
                         ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        agent = RandomAgent(10227)
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            choice = agent.select_action(observation, actions)
            if not selected and {8, 512} == {
                    action.parameters.get("race") for action in actions}:
                assert all(action.kind == "announce_race" for action in actions)
                assert {CHAOS_NECROMANCER, BIRDFACE_GOAT} <= {
                    card.code for card in observation.field if card.controller == 0
                    and card.position == "faceup"}
                choice = next(action for action in actions
                              if action.parameters["race"] == keep_race)
                selected = True
                observation = env.step(choice)
                assert kept in {card.code for card in observation.field
                                if card.controller == 0 and card.zone == "monster"
                                and card.position == "faceup"}
                assert sent not in {card.code for card in observation.field}
                assert sent in {card.code for card in observation.graveyards[0]}
                continue
            observation = env.step(choice)
        else:
            pytest.fail("Rivalry fixture exceeded 3000 decisions")
        assert selected
        trajectory = env.trajectory()
        assert trajectory.asset_sha256[
            "scripts/goat/c504700158.lua"] != UPSTREAM_GOAT_RIVALRY_SHA256
        assert any(record.selected_action.parameters.get("code") == RIVALRY_GOAT
                   for record in trajectory.decisions)

    path = tmp_path / "rivalry.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    audit_trajectory_visibility(loaded)
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
