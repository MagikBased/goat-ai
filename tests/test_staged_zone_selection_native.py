"""Large field-zone choices stay bounded and submit one native response."""

import os
import struct
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine import native_messages
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.native_messages import decode_decision
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GROUND_COLLAPSE = 90502999
TARGET_ZONES = (
    {"controller": 0, "location": 4, "sequence": 0},
    {"controller": 0, "location": 4, "sequence": 1},
)


def test_large_zone_prompt_exposes_linear_staged_choices():
    prompt = bytes((24, 0, 5)) + struct.pack("<I", 0)
    native = decode_decision(prompt)
    assert native.zone_selection is not None
    assert len(native.choices) == 30
    assert {choice.kind for choice in native.choices} == {"disable_zones"}
    assert [choice.response for choice in native.choices] == list(range(30))
    selection = native.zone_selection
    valid = bytes((0, 4, 0, 0, 4, 1, 0, 4, 2, 0, 4, 3, 0, 4, 4))
    assert selection.accepts(valid)
    assert selection.accepts(b"".join(reversed(
        [valid[start:start + 3] for start in range(0, len(valid), 3)])))
    assert not selection.accepts(valid[:-3])
    assert not selection.accepts(valid[:12] + valid[:3])
    assert not selection.accepts(valid[:12] + bytes((0, 4, 7)))


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_staged_ground_collapse_matches_flat_native_choice(tmp_path, monkeypatch):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{GROUND_COLLAPSE}.lua").is_file():
        pytest.skip("Ground Collapse script not installed")
    decks = ("examples/decks/ground_collapse_probe.ydk",
             "examples/decks/vanilla_probe.ydk")

    def run(staged):
        monkeypatch.setattr(native_messages, "MAX_ZONE_SELECTION_COMBINATIONS",
                            1 if staged else 2048)
        with GoatEnvironment(*decks, seed=3,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            activated = selected = False
            post_selection = None
            agent = RandomAgent(3)
            for _ in range(3000):
                if env.is_terminal():
                    assert activated and selected and post_selection is not None
                    trajectory = env.trajectory()
                    path = tmp_path / f"ground_collapse_staged_{staged}.json"
                    write_trajectory(path, trajectory)
                    loaded = read_trajectory(path)
                    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
                        trajectory.decisions)
                    audit_trajectory_visibility(loaded)
                    return post_selection, env.result()
                actions = env.legal_actions()
                action = None
                if not activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GROUND_COLLAPSE), None)
                    activated |= action is not None
                elif not selected and actions[0].kind == "disable_zones":
                    if staged:
                        native_prompt = env.engine.probe._pending_message
                        first = next(a for a in actions
                                     if a.parameters["zones"] == [TARGET_ZONES[0]])
                        before = obs
                        obs = env.step(first)
                        assert obs is before
                        assert env.engine.probe._pending_message == native_prompt
                        action = next(a for a in env.legal_actions()
                                      if a.parameters["zones"] == list(TARGET_ZONES))
                    else:
                        action = next(a for a in actions
                                      if a.parameters["zones"] == list(TARGET_ZONES))
                    selected = True
                if action is None:
                    action = (agent.select_action(obs, actions) if selected else
                              next((a for a in actions if a.kind in (
                                  "place", "pass", "end_phase")), actions[0]))
                obs = env.step(action)
                if selected and post_selection is None:
                    post_selection = (obs, env.legal_actions())
        pytest.fail("Ground Collapse duel exceeded the decision bound")

    flat, flat_winner = run(False)
    staged, staged_winner = run(True)
    assert staged == flat
    assert staged_winner == flat_winner
