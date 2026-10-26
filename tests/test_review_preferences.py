"""Reviewed alternatives may contain several equally acceptable legal actions."""

import json
from dataclasses import replace

import pytest

from goat_ai.actions import Action
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord, Trajectory, read_decision_preferences


def trajectory():
    view = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1",
        life_points=(8000, 8000), hand=(), field=(),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    actions = (Action("own", "select_card", 0, {"controller": 0}),
               Action("enemy-a", "select_card", 0, {"controller": 1}),
               Action("enemy-b", "select_card", 0, {"controller": 1}))
    return Trajectory(
        "goat", ("a.ydk", "b.ydk"), 42,
        (DecisionRecord(view, actions, actions[0]),), 1,
        source="self_play_rl",
        skill_metadata={"learner_seat": 0, "demonstrator_seat": 0},
    )


def preference_file(tmp_path, **changes):
    payload = {
        "schema_version": 1,
        "source_trajectory_sha256": "a" * 64,
        "authorization": "self_play_review",
        "reviewer": "Replay audit",
        "preferences": [{
            "decision_index": 0,
            "preferred_action_indices": [1, 2],
            "disfavored_action_indices": [0],
        }],
    }
    payload.update(changes)
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps(payload))
    return path


def test_preference_accepts_two_enemy_targets_without_picking_one(tmp_path):
    reviewed = read_decision_preferences(preference_file(tmp_path), "a" * 64,
                                         trajectory())
    assert reviewed.authorization == "self_play_review"
    assert reviewed.preferences[0].preferred_action_indices == (1, 2)
    assert reviewed.preferences[0].disfavored_action_indices == (0,)


@pytest.mark.parametrize("changes,message", [
    ({"source_trajectory_sha256": "b" * 64}, "SHA-256"),
    ({"authorization": "self_recorded"}, "agent-review"),
    ({"reviewer": " "}, "reviewer"),
    ({"preferences": []}, "at least one"),
    ({"preferences": [{"decision_index": 0,
                       "preferred_action_indices": [1, 1],
                       "disfavored_action_indices": [0]}]}, "unique legal"),
    ({"preferences": [{"decision_index": 0,
                       "preferred_action_indices": [1, 3],
                       "disfavored_action_indices": [0]}]}, "unique legal"),
    ({"preferences": [{"decision_index": 0,
                       "preferred_action_indices": [0, 1],
                       "disfavored_action_indices": [0]}]}, "overlap"),
    ({"preferences": [{"decision_index": 0,
                       "preferred_action_indices": [1],
                       "disfavored_action_indices": [2]}]}, "recorded choice"),
])
def test_preference_rejects_invalid_or_misattributed_sets(tmp_path, changes, message):
    with pytest.raises(ValueError, match=message):
        read_decision_preferences(preference_file(tmp_path, **changes), "a" * 64,
                                  trajectory())


def test_preference_restricts_source_and_learner_seat(tmp_path):
    base = trajectory()
    with pytest.raises(ValueError, match="agent seat"):
        read_decision_preferences(preference_file(tmp_path), "a" * 64,
                                  replace(base, source="policy_evaluation"))
    with pytest.raises(ValueError, match="agent seat"):
        read_decision_preferences(preference_file(tmp_path), "a" * 64,
                                  replace(base, skill_metadata={"learner_seat": True}))
    opponent = replace(base.decisions[0].observation, viewer=1, acting_player=1)
    enemy_actions = (Action("pass", "pass", 1),)
    wrong_seat = replace(base, decisions=(DecisionRecord(
        opponent, enemy_actions, enemy_actions[0]),))
    with pytest.raises(ValueError, match="reviewed agent seat"):
        read_decision_preferences(preference_file(tmp_path), "a" * 64, wrong_seat)


def test_score_prefers_either_good_target_without_set_size_bonus():
    torch = pytest.importorskip("torch")
    from goat_ai.training.policy import CardVocabulary
    from scripts.score_reviewed_preferences import score_preference

    class FixedScores(torch.nn.Module):
        feature_version = 1

        def __init__(self, scores):
            super().__init__()
            self.scores = scores

        def forward(self, _features):
            return torch.tensor(self.scores)

    record = trajectory().decisions[0]
    tied = score_preference(FixedScores([0.0, 0.0, 0.0]),
                            CardVocabulary(()), record, (1, 2), (0,))
    assert tied["preferred_minus_disfavored_log_mean_exp"] == pytest.approx(0.0)
    better = score_preference(FixedScores([0.0, 2.0, 1.0]),
                              CardVocabulary(()), record, (1, 2), (0,))
    assert better["model_best_is_preferred"]
    assert better["best_preferred_rank"] == 1
    assert better["preferred_minus_disfavored_log_mean_exp"] > 0
