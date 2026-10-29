"""A native branch must reproduce its source and verify an alternate duel."""

import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.observations import CardView, ChainLinkView, Observation
from goat_ai.replay import DecisionRecord, Trajectory, read_trajectory, write_trajectory
from goat_ai.actions import Action
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
    "greedy_own_loss_guard_v3", "greedy_own_loss_guard_v4",
    "greedy_own_loss_guard_v5", "greedy_own_loss_guard_v6"))
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
        assert isinstance(options[0]["card_facts"], dict) == inference.endswith(("v2", "v5", "v6"))
    assert len(report["branches"]) == 2
    recorded, alternate = report["branches"]
    assert recorded["recorded_action"] is True
    assert alternate["recorded_action"] is False
    assert recorded["winner"] == source.winner
    assert read_trajectory(recorded["trajectory"]).decisions == source.decisions
    assert read_trajectory(alternate["trajectory"]).decisions[index].selected_action \
        == source.decisions[index].legal_actions[1]
    if inference == "greedy":
        child = tmp_path / "other_policy.pt"
        child.write_bytes(b"different policy checkpoint")
        changed = branches.evaluate_branches(
            source_path, checkpoint, root, index, (0, 1),
            tmp_path / "changed_policy_branches", continuation_checkpoint=child)
        assert changed["source_checkpoint_sha256"] == sha256_file(checkpoint)
        assert changed["continuation_checkpoint_sha256"] == sha256_file(child)
        assert read_trajectory(changed["branches"][0]["trajectory"]).skill_metadata[
            "policy_checkpoint_sha256"] == sha256_file(child)
        assert options == [{}, {}]
    if inference == "greedy_own_loss_guard_v1":
        child = tmp_path / "guarded_child.pt"
        child.write_bytes(b"different guarded policy checkpoint")
        changed = branches.evaluate_branches(
            source_path, checkpoint, root, index, (0, 1),
            tmp_path / "guarded_child_branches", continuation_checkpoint=child,
            continuation_use_source_inference=True)
        assert changed["continuation_inference"] == inference
        assert options[-1]["own_loss_guard_version"] == 1
        assert changed["continuation_checkpoint_sha256"] == sha256_file(child)
        v3 = branches.evaluate_branches(
            source_path, checkpoint, root, index, (0, 1),
            tmp_path / "v3_continuation_branches", continuation_guard_version=3)
        assert v3["continuation_inference"] == "greedy_own_loss_guard_v3"
        assert options[-1]["own_loss_guard_version"] == 3
        assert v3["branches"][0]["recorded_action"] is True
    with pytest.raises(ValueError, match="include the recorded action"):
        branches.evaluate_branches(source_path, checkpoint, root, index,
                                   (1,), tmp_path / "rejected")


def test_branch_rejects_unknown_recorded_inference(tmp_path):
    with pytest.raises(ValueError, match="unsupported source policy inference"):
        branches.recorded_policy_options("greedy_unknown", tmp_path)


def test_open_chain_material_change_uses_each_players_visible_hand_count():
    def observation(viewer, hand, opposing_hand, chain):
        return Observation(
            viewer=viewer, acting_player=viewer, turn=1, phase="main1",
            life_points=(8000, 8000),
            hand=tuple(CardView(viewer, "hand", "faceup", 100)
                       for _ in range(hand)),
            field=(), graveyards=((), ()), banished=((), ()),
            opponent_hand_count=opposing_hand, deck_counts=(35, 35),
            extra_deck_counts=(0, 0), chain=chain, turn_player=0)

    pending = (ChainLinkView(1, 200, 0, 8, 0),)
    before = observation(0, 5, 5, pending)
    after = observation(1, 3, 5, ())
    wait = Action("pass", "pass", 0, {})
    opponent_wait = Action("pass", "pass", 1, {})
    trajectory = Trajectory("goat", ("a", "b"), 1, (
        DecisionRecord(before, (wait,), wait),
        DecisionRecord(after, (opponent_wait,), opponent_wait),
    ), winner=None)
    result = branches.open_chain_material_change(trajectory, 0, 0, {})
    assert result == {"before": 0, "after": 2, "delta": 2,
                      "closed_before_decision": 1}
    assert branches.open_chain_material_change(trajectory, 1, 0, {}) is None


def test_later_same_code_activations_stops_at_new_turn_and_ignores_opponent():
    def event(turn, phase, actor, kind, code):
        observation = Observation(
            viewer=actor, acting_player=actor, turn=turn, phase=phase,
            life_points=(8000, 8000), hand=(), field=(), graveyards=((), ()),
            banished=((), ()), opponent_hand_count=0, deck_counts=(35, 35),
            extra_deck_counts=(0, 0), turn_player=0)
        action = Action("choice", kind, actor, {"code": code})
        return DecisionRecord(observation, (action,), action)

    trajectory = Trajectory("goat", ("a", "b"), 1, (
        event(1, "main1", 0, "activate", 200),
        event(1, "battle_start", 1, "chain", 200),
        event(1, "main2", 0, "activate", 200),
        event(1, "main2", 0, "set_spell_trap", 200),
        event(2, "draw", 0, "activate", 200),
    ), winner=None)
    assert branches.later_same_code_activations(trajectory, 0, 0, 200) == [
        {"decision_index": 2, "phase": "main2", "action_kind": "activate"}]
    assert branches.later_same_code_activations(trajectory, 0, 0, None) == []
