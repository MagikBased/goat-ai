"""Select the demonstrated seat after full-duel replay verification."""

from .trajectory import DecisionRecord, Trajectory


def demonstrator_seat(trajectory: Trajectory) -> int | None:
    """Resolve the labeled seat; legacy self-play uses learner_seat metadata."""
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("demonstrator_seat")
    if trajectory.source == "self_play_rl":
        learner = metadata.get("learner_seat")
        if type(learner) is not int or learner not in (0, 1):
            raise ValueError("self_play_rl trajectory requires learner_seat 0 or 1")
        if seat is not None and (type(seat) is not int or seat != learner):
            raise ValueError("demonstrator_seat conflicts with learner_seat")
        seat = learner
    if seat is None:
        if trajectory.source in ("heuristic", "combat_heuristic", "human_cli"):
            raise ValueError(f"{trajectory.source} trajectory lacks demonstrator_seat")
        return None
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("demonstrator_seat must be 0 or 1")
    return seat


def demonstrator_records(trajectory: Trajectory) -> tuple[DecisionRecord, ...]:
    """Return learner labels without treating the other player's moves as demos."""
    seat = demonstrator_seat(trajectory)
    if seat is None:
        return trajectory.decisions
    selected = tuple(record for record in trajectory.decisions
                     if record.observation.acting_player == seat)
    if not selected:
        raise ValueError("trajectory contains no decisions by demonstrator_seat")
    return selected
