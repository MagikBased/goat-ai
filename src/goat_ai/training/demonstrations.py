"""Select the demonstrated seat after full-duel replay verification."""

from goat_ai.replay import DecisionRecord, Trajectory


def demonstrator_records(trajectory: Trajectory) -> tuple[DecisionRecord, ...]:
    """Return learner labels without treating the other player's moves as demos."""
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("demonstrator_seat")
    if seat is None:
        if trajectory.source in ("heuristic", "human_cli"):
            raise ValueError(f"{trajectory.source} trajectory lacks demonstrator_seat")
        return trajectory.decisions
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("demonstrator_seat must be 0 or 1")
    selected = tuple(record for record in trajectory.decisions
                     if record.observation.acting_player == seat)
    if not selected:
        raise ValueError("trajectory contains no decisions by demonstrator_seat")
    return selected
