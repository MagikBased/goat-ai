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
        if trajectory.source in ("heuristic", "combat_heuristic", "human_cli", "human_web"):
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


def training_demonstrator_records(trajectory: Trajectory) -> tuple[DecisionRecord, ...]:
    """Admit raw cloning labels only from known local recording paths.

    Replay verification proves native reproducibility, not recording permission.
    Imported or reviewed material must use an explicit, separately validated
    annotation path until its own admission requirements are implemented.
    """
    source = trajectory.source
    if source.startswith("scripted_"):
        raise ValueError("scripted replay requires explicit annotations")
    teachers = {"heuristic", "combat_heuristic", "combat_flip", "tactical"}
    if source in ("human_cli", "human_web"):
        if (trajectory.skill_metadata or {}).get("authorization") != "self_recorded":
            raise ValueError(f"{source} training requires self_recorded authorization")
    elif source not in teachers | {"self_play", "self_play_rl"}:
        raise ValueError(f"{source} is not an admitted raw training source")
    if source in teachers | {"human_cli", "human_web"}:
        seat = (trajectory.skill_metadata or {}).get("demonstrator_seat")
        if type(seat) is not int or seat not in (0, 1):
            raise ValueError(f"{source} training requires demonstrator_seat 0 or 1")
    return demonstrator_records(trajectory)
