"""Label policy-visited, player-visible states with a versioned baseline."""

from collections.abc import Collection, Sequence
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


def filter_activation_opportunities(
    trajectory: Trajectory, labeled: Sequence[DecisionRecord], codes: Collection[int],
) -> tuple[tuple[DecisionRecord, ...], int]:
    """Keep teacher labels where a named card could be activated from a visible option."""
    selected_codes = set(codes)
    seat = (trajectory.skill_metadata or {}).get("demonstrator_seat")
    originals = [record for record in trajectory.decisions
                 if record.observation.acting_player == seat
                 and len(record.legal_actions) > 1]
    if not selected_codes or len(originals) != len(labeled):
        raise ValueError("activation focus needs card IDs and aligned teacher labels")
    kept = []
    disagreements = 0
    for original, teacher in zip(originals, labeled, strict=True):
        if (original.observation != teacher.observation
                or original.legal_actions != teacher.legal_actions):
            raise ValueError("teacher labels do not match recorded visible decisions")
        if any(action.kind == "activate"
               and action.parameters.get("code") in selected_codes
               for action in original.legal_actions):
            kept.append(teacher)
            disagreements += original.selected_action != teacher.selected_action
    return tuple(kept), disagreements
