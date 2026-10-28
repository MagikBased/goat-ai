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


def test_counter_prompt_rejects_invalid_and_stages_large_allocations(monkeypatch):
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
    staged = native_messages.decode_decision(_prompt())
    assert staged.choices == ()
    assert staged.counter_selection is not None
    assert list(staged.counter_selection.feasible_amounts(())) == [1, 2]
    assert staged.counter_selection.accepts(struct.pack("<2h", 1, 1))
    assert not staged.counter_selection.accepts(struct.pack("<2h", 0, 2))


def test_large_counter_prompt_stages_public_amounts_and_sends_one_response(tmp_path):
    cards = tuple((100 + index, index // 5, 4, index % 5) for index in range(10))
    prompt = (struct.pack("<BBHHI", 22, 0, 1, 10, len(cards))
              + b"".join(struct.pack("<IBBBH", code, controller, location,
                                      sequence, 5)
                         for code, controller, location, sequence in cards))
    native = native_messages.decode_decision(prompt)
    selection = native.counter_selection
    assert selection is not None and native.choices == ()
    assert selection.accepts(struct.pack("<10h", *([1] * 10)))
    assert not selection.accepts(struct.pack("<10h", *([2] * 10)))
    observation = replace(_observation(), field=tuple(
        CardView(controller, "monster", "faceup", code, sequence, counters=((1, 5),))
        for code, controller, _, sequence in cards))
    responses = []
    engine = ExperimentalOcgcoreEngine(tmp_path)
    engine.probe = SimpleNamespace(
        _pending_message=prompt,
        decode_pending=lambda: native,
        observation=lambda _player, terminal=False: observation,
        respond=lambda response: (responses.append(response)
                                  or SimpleNamespace(terminal=True, winner=0)),
        close=lambda: None)
    decision = engine._decision()
    records = []
    for index in range(10):
        assert not decision.terminal
        assert decision.observation == observation
        assert 1 <= len(decision.legal_actions) <= 6
        assert all(action.kind == "select_counters" and
                   action.parameters["counter_stage"] is True and
                   action.parameters["counter_index"] == index and
                   action.parameters["counter_card_count"] == 10
                   for action in decision.legal_actions)
        selected = next(action for action in decision.legal_actions
                        if action.parameters["cards"][-1]["amount"] == 1)
        record = DecisionRecord(observation, decision.legal_actions, selected)
        audit_decision_visibility(record)
        records.append(record)
        assert engine.action_for_selection_index(1) == selected
        with pytest.raises(ValueError, match="recorded response"):
            engine.action_for_recorded_response(struct.pack("<10h", *([1] * 10)))
        decision = engine.step(selected)
        assert len(responses) == (1 if index == 9 else 0)
    assert decision.terminal and decision.winner == 0
    assert responses == [struct.pack("<10h", *([1] * 10))]
    trajectory = Trajectory("goat", ("one", "two"), 42, tuple(records), 0)
    path = tmp_path / "staged_counter_choices.json"
    write_trajectory(path, trajectory)
    assert read_trajectory(path) == trajectory


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
    staged = {"cards": [{"controller": 1, "location": 4, "sequence": 1,
                          "code": 200, "amount": 0}],
              "counter_type": 1, "counter_total": 2, "counter_stage": True,
              "counter_index": 0, "counter_card_count": 2, "counter_remaining": 2}
    assert check(staged) == {"opponent_field_choices": 1}
    with pytest.raises(VisibilityViolation, match="invalid public progress"):
        check({**staged, "counter_remaining": 1})
