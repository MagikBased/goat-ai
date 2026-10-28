"""Nobleman target actions cannot identify shuffled Cyber Jar Set monsters."""

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
NOBLEMAN = 504700116


def run_target(root: Path, own: Path, other: Path, reverse: bool,
               replay_path: Path):
    with GoatEnvironment(str(own), str(other), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {CYBER_JAR, NOBLEMAN} <= {card.code for card in obs.hand}
        jar_set = jar_flipped = placed = nobleman_activated = targeted = checked = False
        before = after = None
        agents = (RandomAgent(3), RandomAgent(4))
        for _ in range(3000):
            if env.is_terminal():
                assert checked and before is not None and after is not None
                write_trajectory(replay_path, env.trajectory())
                replay = read_trajectory(replay_path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return before, after
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0 \
                    and not jar_set:
                action = next((a for a in actions if a.kind == "set_monster" and
                               a.parameters.get("code") == CYBER_JAR), None)
                jar_set = action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and not jar_flipped:
                action = next((a for a in actions if a.kind == "flip_summon" and
                               a.parameters.get("code") == CYBER_JAR), None)
                jar_flipped = action is not None
            if jar_flipped and not placed and actions[0].kind == "place":
                action = sorted(actions, key=lambda a: a.parameters["sequence"],
                                reverse=reverse and obs.acting_player == 1)[0]
            if jar_flipped and not placed and obs.acting_player == 1 \
                    and actions[0].kind == "select_position":
                action = next(a for a in actions if a.parameters.get("position") == 8)
            if placed and not nobleman_activated:
                action = next((a for a in actions if a.kind == "activate" and
                               a.parameters.get("code") == NOBLEMAN), None)
                nobleman_activated = action is not None
            if nobleman_activated and not targeted and actions[0].kind == "select_card":
                private = env.engine.probe.observation(1)
                hidden_slots = tuple((card.sequence, card.code) for card in private.field
                                     if card.controller == 1 and card.zone == "monster")
                assert len(hidden_slots) == 5
                assert obs.viewer == obs.acting_player == 0
                assert all(card.code is None for card in obs.field
                           if card.controller == 1 and card.zone == "monster")
                assert len(actions) == 5
                assert all(action.kind == "select_card" and
                           set(action.parameters) == {"location", "sequence", "controller"}
                           and action.parameters["controller"] == 1
                           for action in actions)
                before = obs, actions, hidden_slots
                action = next(a for a in actions if a.parameters["sequence"] == 1)
                targeted = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "pass", "end_phase", "place", "select_position", "select_card")),
                    actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            placed |= jar_flipped and len([
                card for card in obs.field if card.zone == "monster"]) == 10
            if targeted and not checked and NOBLEMAN in {
                    card.code for card in obs.graveyards[0]} \
                    and len(obs.banished[1]) == 1 and not obs.chain:
                target_code = dict(before[2])[1]
                assert obs.banished[1][0].code == target_code
                assert obs.banished[0] == ()
                assert NOBLEMAN not in {card.code for card in obs.hand}
                after = obs
                checked = True
    pytest.fail("Cyber Jar/Nobleman target duel did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_nobleman_target_after_cyber_jar_reveal_hides_slot_identity(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = (f"goat/c{CYBER_JAR}.lua", f"goat/c{NOBLEMAN}.lua")
    if any(not (root / "scripts" / script).is_file() for script in required):
        pytest.skip("GOAT card script not installed")
    cards = [CYBER_JAR, *VANILLA_DECK[1:]]
    cards[2] = NOBLEMAN
    own = tmp_path / "cyber_jar_nobleman.ydk"
    own.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    other = Path("examples/decks/vanilla_probe.ydk")
    forward, revealed_forward = run_target(
        root, own, other, False, tmp_path / "nobleman_forward.json")
    reverse, revealed_reverse = run_target(
        root, own, other, True, tmp_path / "nobleman_reverse.json")
    assert forward[0] == reverse[0]  # The acting player's full target-choice view.
    assert forward[1] == reverse[1]  # Exactly the same five legal target slots.
    assert forward[2] != reverse[2]  # The defender's private mapping differs.
    assert dict(forward[2])[1] != dict(reverse[2])[1]
    assert revealed_forward.banished[1][0].code != revealed_reverse.banished[1][0].code
