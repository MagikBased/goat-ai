"""Cyber Jar's public reveal must not map shuffled face-down cards to zones."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CYBER_JAR = 504700188


def run_permutation(root: Path, own: Path, other: Path, reverse: bool,
                    replay_path: Path):
    with GoatEnvironment(str(own), str(other), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        jar_set = jar_flipped = captured = False
        snapshot = None
        agents = (RandomAgent(3), RandomAgent(4))
        for _ in range(3000):
            if env.is_terminal():
                assert captured and snapshot is not None
                write_trajectory(replay_path, env.trajectory())
                replay = read_trajectory(replay_path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return snapshot
            actions = env.legal_actions()
            action = None
            if not captured and obs.turn == 1 and obs.acting_player == 0 \
                    and not jar_set:
                action = next((a for a in actions if a.kind == "set_monster" and
                               a.parameters.get("code") == CYBER_JAR), None)
                jar_set = action is not None
            if not captured and obs.turn == 3 and obs.acting_player == 0 \
                    and not jar_flipped:
                action = next((a for a in actions if a.kind == "flip_summon" and
                               a.parameters.get("code") == CYBER_JAR), None)
                jar_flipped = action is not None
            if jar_flipped and not captured and actions[0].kind == "place":
                action = sorted(actions, key=lambda a: a.parameters["sequence"],
                                reverse=reverse and obs.acting_player == 1)[0]
            if jar_flipped and not captured and obs.acting_player == 1 \
                    and actions[0].kind == "select_position":
                action = next(a for a in actions if a.parameters.get("position") == 8)
            if action is None and not captured:
                action = next((a for a in actions if a.kind == "end_phase"), None)
            if action is None and not captured:
                action = next((a for a in actions if a.kind == "pass"), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if jar_flipped and not captured and len([
                    card for card in obs.field if card.zone == "monster"]) == 10:
                opponent = env.engine.probe.observation(0)
                placer = env.engine.probe.observation(1)
                assert [(reveal.player, len(reveal.codes)) for reveal in
                        opponent.public_reveals] == [(0, 5), (1, 5)]
                assert all(card.code is None for card in opponent.field
                           if card.controller == 1 and card.zone == "monster")
                assert not opponent.known_opponent_field_cards
                own_slots = tuple((card.sequence, card.code) for card in placer.field
                                  if card.controller == 1 and card.zone == "monster")
                assert len(own_slots) == 5
                snapshot = opponent, placer, env.legal_actions(), own_slots
                captured = True
    pytest.fail("Cyber Jar hidden placement duel did not reach terminal state")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_cyber_jar_face_down_placement_permutation_is_hidden(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{CYBER_JAR}.lua").is_file():
        pytest.skip("GOAT Cyber Jar script not installed")
    own = tmp_path / "cyber_jar.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        CYBER_JAR, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other = Path("examples/decks/vanilla_probe.ydk")
    forward = run_permutation(root, own, other, False,
                              tmp_path / "cyber_jar_forward.json")
    reversed_order = run_permutation(root, own, other, True,
                                     tmp_path / "cyber_jar_reverse.json")
    assert forward[3] != reversed_order[3]  # Controller knows which slot holds each card.
    assert sorted(code for _, code in forward[3]) == sorted(
        code for _, code in reversed_order[3])
    assert forward[0] == reversed_order[0]  # Opponent's complete view is identical.
    assert forward[2] == reversed_order[2]  # Available actions reveal no hidden mapping.
