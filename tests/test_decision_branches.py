"""A native branch must reproduce its source and verify an alternate duel."""

import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training.policy import POLICY_INFERENCE_VERSION
from scripts import evaluate_decision_branches as branches


class FirstActionAgent:
    model = SimpleNamespace(feature_version=23)

    def select_action(self, _observation, legal_actions):
        return legal_actions[0]


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("inference", (
    "greedy", "greedy_own_loss_guard_v1", "greedy_own_loss_guard_v2",
    "greedy_own_loss_guard_v3"))
def test_native_branch_reproduces_source_and_alternate(tmp_path, monkeypatch,
                                                       inference):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck_a = "examples/decks/vanilla_probe.ydk"
    deck_b = "examples/decks/vanilla_reverse.ydk"
    checkpoint = tmp_path / "first_action.pt"
    checkpoint.write_bytes(b"deterministic test agent")
    with GoatEnvironment(deck_a, deck_b, 2, ExperimentalOcgcoreEngine(root)) as env:
        env.reset()
        for _ in range(1000):
            if env.is_terminal():
                break
            env.step(env.legal_actions()[0])
        assert env.is_terminal()
        source = replace(env.trajectory(), source="policy_evaluation",
                         skill_metadata={
                             "demonstrator_seat": 0,
                             "policy_checkpoint_sha256": sha256_file(checkpoint),
                             "policy_inference": inference,
                             "policy_inference_version": POLICY_INFERENCE_VERSION,
                             "policy_feature_version": 23,
                             "opponent": "TacticalHeuristicAgent",
                             "opponent_version": 14,
                         })
    index = next(i for i, record in enumerate(source.decisions)
                 if record.observation.acting_player == 0
                 and len(record.legal_actions) > 1)
    source_path = tmp_path / "source.json"
    write_trajectory(source_path, source)
    options = []

    def load_agent(_path, **kwargs):
        options.append(kwargs)
        return FirstActionAgent()

    monkeypatch.setattr(branches, "load_policy_agent", load_agent)
    monkeypatch.setattr(branches, "TacticalHeuristicAgent",
                        lambda *_args, **_kwargs: FirstActionAgent())
    report = branches.evaluate_branches(source_path, checkpoint, root, index,
                                        (0, 1), tmp_path / "branches")
    assert report["verified_source_decisions"] == len(source.decisions)
    assert report["policy_inference"] == inference
    if inference == "greedy":
        assert options == [{}]
    else:
        assert len(options) == 1 and options[0]["own_loss_guard"] is True
        assert options[0]["own_loss_guard_version"] == int(inference[-1])
        assert isinstance(options[0]["card_facts"], dict) == inference.endswith("v2")
    assert len(report["branches"]) == 2
    recorded, alternate = report["branches"]
    assert recorded["recorded_action"] is True
    assert alternate["recorded_action"] is False
    assert recorded["winner"] == source.winner
    assert read_trajectory(recorded["trajectory"]).decisions == source.decisions
    assert read_trajectory(alternate["trajectory"]).decisions[index].selected_action \
        == source.decisions[index].legal_actions[1]
    with pytest.raises(ValueError, match="include the recorded action"):
        branches.evaluate_branches(source_path, checkpoint, root, index,
                                   (1,), tmp_path / "rejected")


def test_branch_rejects_unknown_recorded_inference(tmp_path):
    with pytest.raises(ValueError, match="unsupported source policy inference"):
        branches.recorded_policy_options("greedy_unknown", tmp_path)
