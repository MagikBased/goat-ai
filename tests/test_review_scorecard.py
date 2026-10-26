"""Reviewed-choice score margins are distinct from win-rate evaluation."""

import pytest

torch = pytest.importorskip("torch")

from goat_ai.actions import Action
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord
from goat_ai.training.policy import CardVocabulary
from scripts.score_reviewed_decisions import score_decision


class FixedScores(torch.nn.Module):
    feature_version = 1

    def __init__(self, scores):
        super().__init__()
        self.scores = scores

    def forward(self, _features):
        return torch.tensor(self.scores)


def test_scorecard_ranks_reviewed_legal_action_against_recorded_choice():
    observation = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1",
        life_points=(8000, 8000), hand=(), field=(),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    actions = (Action("a", "pass", 0), Action("b", "end_phase", 0),
               Action("c", "battle_phase", 0))
    record = DecisionRecord(observation, actions, actions[0])
    result = score_decision(FixedScores([0.0, 2.0, 1.0]),
                            CardVocabulary(()), record, 2)
    assert result["recorded_index"] == 0
    assert result["annotated_index"] == 2
    assert result["model_best_index"] == 1
    assert result["annotated_rank"] == 2
    assert result["annotated_probability"] == pytest.approx(0.24472847)
    assert result["annotated_minus_recorded_logit"] == 1.0
    assert result["annotated_minus_best_other_logit"] == -1.0
    assert not result["model_matches_annotation"]
    with pytest.raises(ValueError, match="not legal"):
        score_decision(FixedScores([0.0, 2.0, 1.0]), CardVocabulary(()), record, 3)
    with pytest.raises(ValueError, match="invalid legal-action scores"):
        score_decision(FixedScores([float("nan"), 2.0, 1.0]),
                       CardVocabulary(()), record, 2)
