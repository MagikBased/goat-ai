"""Label policy-visited, player-visible states with a versioned baseline."""

from dataclasses import replace

from goat_ai.agents import Agent
from goat_ai.replay import DecisionRecord, Trajectory


def label_policy_trajectory(
    trajectory: Trajectory, teacher: Agent, checkpoint_sha256: str,
) -> tuple[tuple[DecisionRecord, ...], int]:
    """Return teacher choices for the recorded policy seat, never the opponent.

    The source duel must be replay-verified and visibility-audited by the caller.
    Labels may differ from executed actions and have synthetic-teacher provenance.
    """
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("demonstrator_seat")
    if (trajectory.source != "policy_evaluation" or type(seat) is not int
            or seat not in (0, 1)
            or metadata.get("policy_checkpoint_sha256") != checkpoint_sha256):
        raise ValueError("on-policy teacher requires a matching checkpoint-attributed policy replay")
    selected = []
    disagreements = 0
    for record in trajectory.decisions:
        if record.observation.acting_player != seat or len(record.legal_actions) < 2:
            continue
        action = teacher.select_action(record.observation, record.legal_actions)
        if action not in record.legal_actions:
            raise ValueError("automated teacher selected an illegal action")
        selected.append(replace(record, selected_action=action))
        disagreements += action != record.selected_action
    if not selected:
        raise ValueError("policy replay has no multi-option policy decisions")
    return tuple(selected), disagreements
