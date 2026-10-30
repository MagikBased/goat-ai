"""A non-Python client can request a legal visible-state policy decision."""

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.actions import Action
from goat_ai.interop import (
    decode_request,
    decode_response,
    encode_request,
    encode_response,
    select_response,
)
from goat_ai.interop.decision_protocol import DecisionRequest
from goat_ai.observations import CardView, Observation


class SecondActionAgent:
    def select_action(self, _observation, legal_actions):
        return legal_actions[1]


def request() -> DecisionRequest:
    view = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1",
        life_points=(8000, 8000),
        hand=(CardView(0, "hand", "faceup", 55144522),),
        field=(CardView(1, "monster", "facedown", None, 0, "defense"),),
        graveyards=((), ()), banished=((), ()),
        opponent_hand_count=5, deck_counts=(34, 35),
        extra_deck_counts=(0, 0), turn_player=0)
    actions = (Action("a", "pass", 0), Action("b", "end_phase", 0))
    return DecisionRequest(7, "goat_pinned_historical", view, actions)


def test_json_decision_round_trip_and_decision_local_action_id():
    original = request()
    restored = decode_request(encode_request(original))
    assert restored == original
    response = select_response(SecondActionAgent(), restored)
    assert decode_response(response, original) == original.legal_actions[1]
    assert json.loads(response) == {"schema_version": 1,
                                    "decision_id": 7, "action_id": "b"}


def test_wire_boundary_rejects_hidden_identity_and_stale_or_illegal_action():
    original = request()
    raw = json.loads(encode_request(original))
    raw["observation"]["field"][0]["code"] = 123
    with pytest.raises(ValueError, match="opponent facedown identity"):
        decode_request(json.dumps(raw))
    raw = json.loads(encode_request(original))
    raw["legal_actions"][1]["id"] = "a"
    with pytest.raises(ValueError, match="unique legal IDs"):
        decode_request(json.dumps(raw))
    with pytest.raises(ValueError, match="does not match"):
        decode_response(encode_response(8, "a"), original)
    with pytest.raises(ValueError, match="unknown action ID"):
        decode_response(encode_response(7, "c"), original)
    with pytest.raises(ValueError, match="visible acting-player view"):
        replace(original, observation=replace(original.observation, acting_player=1))


def test_policy_stdio_uses_same_visible_decision_contract():
    root = Path(__file__).resolve().parents[1]
    checkpoint = root / ".cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt"
    if not checkpoint.is_file():
        pytest.skip("local trained checkpoint is not installed")
    from goat_ai.training import load_policy_agent

    original = request()
    expected = load_policy_agent(checkpoint).select_action(
        original.observation, original.legal_actions)
    second = replace(original, decision_id=8)
    completed = subprocess.run(
        [sys.executable, str(root / "scripts/serve_policy_stdio.py"), str(checkpoint)],
        input=encode_request(original) + "\n" + encode_request(second) + "\n",
        text=True, capture_output=True, check=True,
        env={**os.environ, "PYTHONPATH": str(root / "src")})
    lines = completed.stdout.splitlines()
    assert len(lines) == 2 and not completed.stderr
    assert decode_response(lines[0], original) == expected
    assert decode_response(lines[1], second) == expected
