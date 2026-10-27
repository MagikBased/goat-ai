from types import SimpleNamespace

import pytest
import torch

from scripts import compare_value_architectures as critic_comparison
from scripts.compare_value_architectures import (
    VisibleResourceValue,
    fit_resource_ridge,
    selected_records,
)


def _record(seat: int, options: int = 2):
    return SimpleNamespace(
        observation=SimpleNamespace(acting_player=seat),
        legal_actions=tuple(range(options)),
    )


def test_fixed_policy_critic_uses_only_policy_seat_decisions() -> None:
    policy_records = [_record(1) for _ in range(5)]
    trajectory = SimpleNamespace(
        source="policy_evaluation",
        skill_metadata={"demonstrator_seat": 1},
        decisions=[_record(0), _record(1, 1), *policy_records],
        winner=1,
    )
    records, target = selected_records(trajectory, 3, "policy_evaluation")
    assert records == (policy_records[0], policy_records[2], policy_records[4])
    assert target == 1.0


def test_fixed_policy_critic_rejects_wrong_source_or_missing_seat() -> None:
    trajectory = SimpleNamespace(
        source="policy_evaluation", skill_metadata={"learner_seat": 0},
        decisions=[_record(0)], winner=0,
    )
    with pytest.raises(ValueError, match="demonstrator_seat"):
        selected_records(trajectory, 1, "policy_evaluation")
    with pytest.raises(ValueError, match="self_play_rl"):
        selected_records(trajectory, 1)


def test_self_play_critic_keeps_learner_seat_and_draw_target() -> None:
    learner_record = _record(0)
    trajectory = SimpleNamespace(
        source="self_play_rl", skill_metadata={"learner_seat": 0},
        decisions=[_record(1), learner_record], winner=None,
    )
    assert selected_records(trajectory, 1) == ((learner_record,), 0.0)


def test_resource_value_uses_visible_counts_without_hidden_card_identity() -> None:
    numbers = torch.tensor([0.8, 0.6, 0.5, 0.4, 0, 0, 0.1, 0.075, 0.04, 0])
    cards = torch.tensor([[10, 1, 1, 1], [0, 2, 2, 2],
                          [20, 2, 1, 3], [0, 3, 2, 2]])
    features = SimpleNamespace(state_numbers=numbers, state_cards=cards)
    concealed = SimpleNamespace(state_numbers=numbers,
                                state_cards=cards.clone())
    concealed.state_cards[1, 0] = 9999
    concealed.state_cards[3, 0] = 8888
    model = VisibleResourceValue()
    assert torch.equal(model.forward_batch([features]),
                       model.forward_batch([concealed]))


def test_resource_ridge_weights_complete_games_equally(monkeypatch) -> None:
    monkeypatch.setattr(critic_comparison, "encode_decision",
                        lambda observation, *_: observation)
    features = SimpleNamespace(
        state_numbers=torch.tensor([0.5, 0.5, 0, 0, 0, 0, 0, 0, 0, 0]),
        state_cards=torch.tensor([[0, 0, 0, 0]]),
    )
    record = SimpleNamespace(observation=features, legal_actions=(1, 2))
    games = (((record,) * 4, 1.0), ((record,), -1.0))
    mse, coefficients = fit_resource_ridge(games, None, 23)
    assert abs(coefficients[-1]) < 1e-12
    assert mse(games) == (1.0, 1.0)
