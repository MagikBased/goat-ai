"""Queue scores describe model behavior without converting prompts to labels."""

from types import SimpleNamespace

import pytest
import torch

from goat_ai.actions import Action
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord
from goat_ai.training.policy import CardVocabulary
from scripts.score_review_queue import score_item


class FixedScores:
    feature_version = 10

    def eval(self):
        return self

    def __call__(self, features):
        return torch.tensor([2.0, -1.0][:len(features.action_kinds)])


def test_score_queue_item_reports_rank_without_asserting_preference_is_correct():
    observation = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1",
        life_points=(8000, 8000), hand=(), field=(),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0,
    )
    mst = Action("mst", "chain", 0, {"code": 5318639})
    decline = Action("pass", "pass", 0)
    record = DecisionRecord(observation, (mst, decline), mst)
    item = {"decision_index": 0, "viewer_frame": 1,
            "teacher_action": {"kind": "pass", "parameters": {}}}
    agent = SimpleNamespace(model=FixedScores(), vocabulary=CardVocabulary(()),
                            select_action=lambda _obs, legal: legal[0])
    result = score_item(agent, record, item)
    assert result["scored_choice_is_recorded"] is True
    assert result["scored_choice_is_suggested"] is False
    assert result["recorded_minus_suggested_logit"] == 3.0
    assert result["suggestion_is_not_a_label"] is True
    with pytest.raises(ValueError, match="exactly one"):
        score_item(agent, record, {**item, "teacher_action": {
            "kind": "activate", "parameters": {}}})
