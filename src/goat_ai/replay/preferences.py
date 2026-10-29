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
    rule_set_id: str | None = None
    schema_version: int = 1
    preference_kind: str | None = None


def read_decision_preferences(path: str | Path, trajectory_sha256: str,
                              trajectory: Trajectory) -> DecisionPreferences:
    """Validate explicit legal alternatives without changing a replayed action.

    The caller must replay-verify and visibility-audit the source trajectory
    before scoring or training on these retrospective preferences.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(raw, dict) or type(raw.get("schema_version")) is not int
            or raw["schema_version"] not in (1, 2)):
        raise ValueError("unsupported decision-preference schema")
    schema_version = raw["schema_version"]
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
    elif authorization == "automated_rule":
        rule_set_id = raw.get("rule_set_id")
        if ((schema_version == 1 and rule_set_id not in (
                "visible_audit_v1", "visible_audit_v2"))
                or (schema_version == 2 and rule_set_id not in (
                    "visible_resource_v3", "visible_material_choices_v4",
                    "visible_material_avoidance_v5", "visible_optional_own_loss_v6",
                    "visible_guard_distillation_v7",
                    "visible_residual_guard_distillation_v8",
                    "visible_optional_own_loss_v9",
                    "visible_selected_own_loss_v10"))):
            raise ValueError("automated preferences require a supported visible audit rule set")
        seat = metadata.get("learner_seat" if trajectory.source == "self_play_rl"
                            else "demonstrator_seat")
        checkpoint = metadata.get("policy_checkpoint_sha256")
        valid = ((trajectory.source == "self_play_rl"
                  and type(seat) is int and seat in (0, 1)
                  and (metadata.get("demonstrator_seat") is None
                       or (type(metadata["demonstrator_seat"]) is int
                           and metadata["demonstrator_seat"] == seat)))
                 or (trajectory.source == "policy_evaluation"
                     and type(seat) is int and seat in (0, 1)
                     and isinstance(checkpoint, str)
                     and re.fullmatch(r"[0-9a-f]{64}", checkpoint) is not None))
    else:
        raise ValueError("preferences require agent-review authorization")
    if schema_version == 2 and authorization != "automated_rule":
        raise ValueError("counterfactual preference schema requires automated-rule provenance")
    if not valid:
        raise ValueError("preference source and agent seat do not match authorization")
    if "reviewed_seat" in raw and (type(raw["reviewed_seat"]) is not int
                                   or raw["reviewed_seat"] != seat):
        raise ValueError("preference reviewed seat does not match source agent seat")
    reviewer = raw.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("preferences require a reviewer name")
    items = raw.get("preferences")
    preference_kind = raw.get("preference_kind")
    if preference_kind is not None and (preference_kind != "reject_recorded"
                                        or authorization != "policy_review"
                                        or schema_version != 1):
        raise ValueError("unsupported human preference kind")
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
        selected_index = record.legal_actions.index(record.selected_action)
        if schema_version == 1 and selected_index not in disfavored:
            raise ValueError("disfavored actions must include the recorded choice")
        if schema_version == 2 and selected_index not in (*preferred, *disfavored):
            raise ValueError("counterfactual comparison must include the recorded choice")
        if preference_kind == "reject_recorded" and (
                disfavored != (selected_index,)
                or set(preferred) != set(range(len(record.legal_actions))) - {selected_index}):
            raise ValueError("rejection must preserve every other legal action")
        parsed.append(ReviewedPreference(index, preferred, disfavored))
    return DecisionPreferences(trajectory_sha256, reviewer.strip(), authorization,
                               seat, tuple(parsed),
                               raw.get("rule_set_id") if authorization == "automated_rule" else None,
                               schema_version, preference_kind)
