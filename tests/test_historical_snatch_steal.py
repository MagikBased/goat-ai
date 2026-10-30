"""Common GOAT control staple: Snatch Steal removed by Heavy Storm."""

import json
import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SNATCH_STEAL = 45986603
HEAVY_STORM = 19613556


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_snatch_steal_upkeep_and_heavy_storm_return_control(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SNATCH_STEAL, HEAVY_STORM):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "control_staples.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        SNATCH_STEAL, HEAVY_STORM, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = snatched = stormed = False
        stolen_code = None
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                summoned |= action is not None
                if action is not None:
                    stolen_code = action.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0 and not snatched:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH_STEAL), action)
                snatched |= action is not None and action.kind == "activate"
            if observation.turn == 5 and observation.acting_player == 0 and not stormed:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY_STORM), action)
                stormed |= action is not None and action.kind == "activate"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            monsters = [card for card in observation.field
                        if card.zone == "monster" and card.code == stolen_code]
            snatch_on_field = any(card.code == SNATCH_STEAL for card in observation.field)
            if (snatched and observation.turn == 3 and monsters and snatch_on_field
                    and monsters[0].controller == 0):
                assert monsters[0].owner == 1
                assert monsters[0].faceup_turns == 1
                assert observation.life_points == (8000, 8000)
                snatch = next(card for card in observation.field
                              if card.code == SNATCH_STEAL)
                assert snatch.equipped_to == (0, monsters[0].sequence)
                opponent = env.engine.probe.observation(1)
                assert next(card for card in opponent.field
                            if card.code == stolen_code).faceup_turns == 1
                assert next(card for card in opponent.field
                            if card.code == SNATCH_STEAL).equipped_to == snatch.equipped_to
            if observation.turn == 4 and observation.phase == "main1":
                assert snatched
                assert monsters and monsters[0].controller == 0
                assert monsters[0].faceup_turns == 2
                assert observation.life_points == (8000, 9000)
            if stormed and any(card.code == HEAVY_STORM
                               for card in observation.graveyards[0]):
                assert monsters and monsters[0].controller == 1
                assert monsters[0].owner == 1
                assert monsters[0].faceup_turns == observation.turn - 2
                assert not snatch_on_field
                assert any(card.code == SNATCH_STEAL
                           for card in observation.graveyards[0])
                assert observation.life_points == (8000, 9000)
                agents = (RandomAgent(18), RandomAgent(19))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    observation = env.step(agents[observation.acting_player].select_action(
                        observation, env.legal_actions()))
                else:
                    pytest.fail("Snatch / Heavy duel exceeded 3000 decisions")
                trajectory = env.trajectory()
                assert trajectory.schema_version == 28
                assert any(card.equipped_to is not None
                           for decision in trajectory.decisions
                           for card in decision.observation.field)
                path = tmp_path / "snatch_heavy.json"
                write_trajectory(path, trajectory)
                loaded = read_trajectory(path)
                assert loaded == trajectory
                assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                previous = json.loads(path.read_text())
                previous["schema_version"] = 20
                previous_path = tmp_path / "snatch_heavy_v20.json"
                previous_path.write_text(json.dumps(previous))
                assert verify_trajectory(read_trajectory(previous_path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                legacy = json.loads(path.read_text())
                legacy["schema_version"] = 18
                for view in [*(row["observation"] for row in legacy["decisions"]),
                             legacy["terminal_observation"]]:
                    for card in view["field"]:
                        card.pop("equipped_to", None)
                old_path = tmp_path / "snatch_heavy_v18.json"
                old_path.write_text(json.dumps(legacy))
                assert verify_trajectory(read_trajectory(old_path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                return
    pytest.fail("Snatch Steal and Heavy Storm did not complete their control sequence")
