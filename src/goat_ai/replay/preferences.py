"""Retrospective pairwise preferences between visible legal actions."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .trajectory import Trajectory


@dataclass(frozen=True)
class ReviewedPreference:
    decision_index: int
    preferred_action_indices: tuple[int, ...]
    disfavored_action_indices: tuple[int, ...]


@dataclass(frozen=True)
class DecisionPreferences:
    source_trajectory_sha256: str
    reviewer: str
    authorization: str
    reviewed_seat: int
    preferences: tuple[ReviewedPreference, ...]


def read_decision_preferences(path: str | Path, trajectory_sha256: str,
                              trajectory: Trajectory) -> DecisionPreferences:
    """Validate explicit legal alternatives without changing a replayed action.

    The caller must replay-verify and visibility-audit the source trajectory
    before scoring or training on these retrospective preferences.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("unsupported decision-preference schema")
    if raw.get("source_trajectory_sha256") != trajectory_sha256:
        raise ValueError("preference source trajectory SHA-256 mismatch")
    authorization = raw.get("authorization")
    metadata = trajectory.skill_metadata or {}
    if authorization == "self_play_review":
        seat = metadata.get("learner_seat")
        recorded_seat = metadata.get("demonstrator_seat")
        valid = (trajectory.source == "self_play_rl"
                 and type(seat) is int and seat in (0, 1)
                 and (recorded_seat is None
                      or (type(recorded_seat) is int and recorded_seat == seat)))
    elif authorization == "policy_review":
        seat = metadata.get("demonstrator_seat")
        checkpoint = metadata.get("policy_checkpoint_sha256")
        valid = (trajectory.source == "policy_evaluation"
                 and type(seat) is int and seat in (0, 1)
                 and isinstance(checkpoint, str)
                 and re.fullmatch(r"[0-9a-f]{64}", checkpoint) is not None)
    elif authorization == "baseline_review":
        seat = raw.get("reviewed_seat")
        teacher_seat = metadata.get("demonstrator_seat")
        valid = (trajectory.source == "tactical"
                 and type(seat) is int and seat in (0, 1)
                 and type(teacher_seat) is int and teacher_seat in (0, 1)
                 and metadata.get("teacher") == "TacticalHeuristicAgent"
                 and type(metadata.get("teacher_version")) is int
                 and metadata["teacher_version"] > 0
                 and isinstance(metadata.get("opponent"), str)
                 and type(metadata.get("opponent_version")) is int
                 and metadata["opponent_version"] > 0)
    else:
        raise ValueError("preferences require agent-review authorization")
    if not valid:
        raise ValueError("preference source and agent seat do not match authorization")
    reviewer = raw.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("preferences require a reviewer name")
    items = raw.get("preferences")
    if not isinstance(items, list) or not items:
        raise ValueError("preferences require at least one decision")
    parsed = []
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or set(item) != {
                "decision_index", "preferred_action_indices", "disfavored_action_indices"}):
            raise ValueError("preference requires decision and action-index sets")
        index = item["decision_index"]
        if type(index) is not int or not 0 <= index < len(trajectory.decisions):
            raise ValueError("preference decision index is invalid")
        if index in seen:
            raise ValueError("duplicate preference decision")
        seen.add(index)
        record = trajectory.decisions[index]
        if record.observation.acting_player != seat:
            raise ValueError("preference may label only the reviewed agent seat")
        groups = []
        for key in ("preferred_action_indices", "disfavored_action_indices"):
            values = item[key]
            if (not isinstance(values, list) or not values
                    or any(type(value) is not int
                           or not 0 <= value < len(record.legal_actions)
                           for value in values)
                    or len(values) != len(set(values))):
                raise ValueError(f"{key} must contain unique legal action indices")
            groups.append(tuple(values))
        preferred, disfavored = groups
        if set(preferred) & set(disfavored):
            raise ValueError("preferred and disfavored actions overlap")
        if record.legal_actions.index(record.selected_action) not in disfavored:
            raise ValueError("disfavored actions must include the recorded choice")
        parsed.append(ReviewedPreference(index, preferred, disfavored))
    return DecisionPreferences(trajectory_sha256, reviewer.strip(), authorization,
                               seat, tuple(parsed))
