"""Native counter-allocation prompts expose only visible field choices."""

import struct
from dataclasses import replace
from types import SimpleNamespace

import pytest

from goat_ai.actions import Action
from goat_ai.engine import native_messages
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import VisibilityViolation, audit_decision_visibility
from goat_ai.observations import CardView, Observation
from goat_ai.replay import DecisionRecord, Trajectory, read_trajectory, write_trajectory


def _prompt(*, total=2, available=(2, 1), codes=(100, 200)) -> bytes:
    return (struct.pack("<BBHHI", 22, 0, 1, total, len(available))
            + b"".join(struct.pack("<IBBBH", code, player, 4, index, amount)
                       for index, (code, player, amount) in enumerate(
                           zip(codes, (0, 1), available, strict=True))))


def _observation() -> Observation:
    return Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(),
        field=(CardView(0, "monster", "faceup", 100, 0, counters=((1, 2),)),
               CardView(1, "monster", "faceup", 200, 1, counters=((1, 1),))),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=0,
        deck_counts=(35, 35), extra_deck_counts=(0, 0))


def test_native_counter_prompt_maps_allocations_to_visible_actions(tmp_path):
    prompt = _prompt()
    native = native_messages.decode_decision(prompt)
    assert [choice.response for choice in native.choices] == [
        struct.pack("<2h", 1, 1), struct.pack("<2h", 2, 0)]
    engine = ExperimentalOcgcoreEngine(tmp_path)
    engine.probe = SimpleNamespace(
        _pending_message=prompt,
        decode_pending=lambda: native,
        observation=lambda player: _observation())
    decision = engine._decision()
    assert [action.kind for action in decision.legal_actions] == [
        "select_counters", "select_counters"]
    assert decision.legal_actions[0].parameters == {
        "cards": [
            {"controller": 0, "location": 4, "sequence": 0, "code": 100, "amount": 1},
            {"controller": 1, "location": 4, "sequence": 1, "code": 200, "amount": 1}],
        "counter_type": 1, "counter_total": 2}
    assert decision.legal_actions[1].parameters["cards"] == [
        {"controller": 0, "location": 4, "sequence": 0, "code": 100, "amount": 2}]
    for action in decision.legal_actions:
        assert audit_decision_visibility(DecisionRecord(
            decision.observation, decision.legal_actions, action))["opponent_field_choices"] == 1
    assert engine.action_for_recorded_response(struct.pack("<2h", 2, 0)) \
        == decision.legal_actions[1]
    trajectory = Trajectory("goat", ("one", "two"), 42, (
        DecisionRecord(decision.observation, decision.legal_actions,
                       decision.legal_actions[0]),), 0)
    replay_path = tmp_path / "counter_choices.json"
    write_trajectory(replay_path, trajectory)
    assert read_trajectory(replay_path) == trajectory


def test_counter_prompt_rejects_invalid_and_unbounded_allocations(monkeypatch):
    same_targets = native_messages.decode_decision(
        _prompt(total=3, available=(2, 2)))
    assert [choice.counter_allocations for choice in same_targets.choices] == [
        (1, 2), (2, 1)]
    assert same_targets.choices[0].response != same_targets.choices[1].response
    with pytest.raises(ValueError, match="truncated"):
        native_messages.decode_decision(_prompt()[:-1])
    with pytest.raises(ValueError, match="no valid allocation"):
        native_messages.decode_decision(_prompt(total=4))
    monkeypatch.setattr(native_messages, "MAX_COUNTER_SELECTION_COMBINATIONS", 1)
    with pytest.raises(NotImplementedError, match="too many allocations"):
        native_messages.decode_decision(_prompt())


def test_counter_audit_rejects_hidden_or_excess_allocations():
    observation = _observation()
    action = {"cards": [{"controller": 1, "location": 4, "sequence": 1,
                         "code": 200, "amount": 1}],
              "counter_type": 1, "counter_total": 1}
    def check(parameters, view=observation):
        selected = Action("0", "select_counters", 0, parameters)
        return audit_decision_visibility(DecisionRecord(view, (selected,), selected))

    assert check(action) == {"opponent_field_choices": 1}
    with pytest.raises(VisibilityViolation, match="exceeds visible"):
        check({**action, "cards": [{**action["cards"][0], "amount": 2}],
               "counter_total": 2})
    hidden = replace(observation, field=(observation.field[0],
                                         CardView(1, "monster", "facedown", None, 1)))
    with pytest.raises(VisibilityViolation, match="exceeds visible"):
        check(action, hidden)
