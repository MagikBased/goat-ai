"""Battle negation must prevent Sinister Serpent's futile Standby prompt."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import (
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BALTER = 80071763
SINISTER = 511000818


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_balter_battle_destroyed_serpent_cannot_repeat_standby_return(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"pre-errata/c{SINISTER}.lua", f"official/c{BALTER}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    decks = Path(__file__).resolve().parents[1] / "examples/decks"
    deck_a = decks / "goat_control_matt_peddle_indianapolis_2005.ydk"
    deck_b = decks / "goat_control_michael_fukuyama_indianapolis_2005.ydk"
    agents = [TacticalHeuristicAgent(load_flip_monster_codes(root),
                                    load_card_races(root),
                                    card_facts=load_card_facts(root))
              for _ in range(2)]
    with GoatEnvironment(str(deck_a), str(deck_b), seed=10302,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        checked = False
        for _ in range(1500):
            actions = env.legal_actions()
            if observation.turn == 10 and observation.phase == "main1" and not checked:
                assert SINISTER in {card.code for card in observation.graveyards[1]}
                assert any(card.code == BALTER and card.controller == 0
                           and card.position == "faceup" for card in observation.field)
                assert all(action.parameters.get("code") != SINISTER
                           for action in actions)
                checked = True
            action = agents[observation.acting_player].select_action(observation, actions)
            observation = env.step(action)
            if env.is_terminal():
                assert checked
                trajectory = env.trajectory()
                assert all(not (record.observation.turn == 10
                                and record.observation.phase == "standby"
                                and record.selected_action.parameters.get("code") == SINISTER)
                           for record in trajectory.decisions)
                assert f"pre-errata/c{SINISTER}.lua" \
                    in env.engine.probe.loaded_script_sha256
                path = tmp_path / "balter_serpent.json"
                write_trajectory(path, trajectory)
                saved = read_trajectory(path)
                assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(saved)
                return
    pytest.fail("Balter/Serpent duel did not reach a terminal result")
