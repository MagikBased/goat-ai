"""Label policy-visited, player-visible states with a versioned baseline."""

from collections.abc import Collection, Sequence
from dataclasses import replace
from math import isfinite

import torch

from goat_ai.agents import Agent
from goat_ai.evaluation.thunder_search_audit import thunder_search_choice
from goat_ai.replay import DecisionRecord, Trajectory
from goat_ai.training.policy import CardVocabulary, LegalActionPolicy, encode_decision


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


def filter_thunder_search_opportunities(
    trajectory: Trajectory, labeled: Sequence[DecisionRecord],
) -> tuple[tuple[DecisionRecord, ...], int]:
    """Keep only staged Thunder searches with a visible Deck-copy option."""
    seat = (trajectory.skill_metadata or {}).get("demonstrator_seat")
    originals = [record for record in trajectory.decisions
                 if record.observation.acting_player == seat
                 and len(record.legal_actions) > 1]
    if seat not in (0, 1) or len(originals) != len(labeled):
        raise ValueError("Thunder focus needs aligned policy decisions and seat")
    kept = []
    disagreements = 0
    for original, teacher in zip(originals, labeled, strict=True):
        if (original.observation != teacher.observation
                or original.legal_actions != teacher.legal_actions):
            raise ValueError("Thunder labels do not match recorded visible decisions")
        if thunder_search_choice(original, seat) is None:
            continue
        kept.append(teacher)
        disagreements += original.selected_action != teacher.selected_action
    return tuple(kept), disagreements


def teacher_disagreement_flags(
    trajectory: Trajectory, labeled: Sequence[DecisionRecord],
) -> tuple[bool, ...]:
    """Identify corrections using only the recorded policy seat's legal choices."""
    seat = (trajectory.skill_metadata or {}).get("demonstrator_seat")
    originals = [record for record in trajectory.decisions
                 if record.observation.acting_player == seat
                 and len(record.legal_actions) > 1]
    if len(originals) != len(labeled):
        raise ValueError("teacher disagreement flags need aligned policy decisions")
    flags = []
    for original, teacher in zip(originals, labeled, strict=True):
        if (original.observation != teacher.observation
                or original.legal_actions != teacher.legal_actions):
            raise ValueError("teacher labels do not match recorded visible decisions")
        flags.append(original.selected_action != teacher.selected_action)
    return tuple(flags)


def filter_low_parent_margin_opportunities(
    trajectory: Trajectory, labeled: Sequence[DecisionRecord],
    parent: LegalActionPolicy, vocabulary: CardVocabulary, margin: float,
) -> tuple[tuple[DecisionRecord, ...], int]:
    """Keep synthetic labels only where the exact parent scores are close.

    The margin is computed from the acting player's visible observation and
    offered actions. The replay's hidden deal is never passed to the model.
    """
    if not isfinite(margin) or margin < 0:
        raise ValueError("parent margin must be finite and nonnegative")
    seat = (trajectory.skill_metadata or {}).get("demonstrator_seat")
    originals = [record for record in trajectory.decisions
                 if record.observation.acting_player == seat
                 and len(record.legal_actions) > 1]
    if seat not in (0, 1) or len(originals) != len(labeled):
        raise ValueError("margin focus needs aligned policy decisions and seat")
    parent.eval()
    device = next(parent.parameters()).device
    kept = []
    disagreements = 0
    with torch.inference_mode():
        for original, teacher in zip(originals, labeled, strict=True):
            if (original.observation != teacher.observation
                    or original.legal_actions != teacher.legal_actions):
                raise ValueError("teacher labels do not match recorded visible decisions")
            features = encode_decision(original.observation, original.legal_actions,
                                       vocabulary, parent.feature_version)
            scores = parent(features.to(device))
            top_two = torch.topk(scores, 2).values
            if (top_two[0] - top_two[1]).item() < margin:
                kept.append(teacher)
                disagreements += original.selected_action != teacher.selected_action
    return tuple(kept), disagreements
