from types import SimpleNamespace

import pytest

from scripts.compare_value_architectures import selected_records


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
