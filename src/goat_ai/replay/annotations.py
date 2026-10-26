"""Validated retrospective action labels tied to a replay-verified duel."""

import json
from dataclasses import dataclass, replace
from pathlib import Path

from .trajectory import DecisionRecord, Trajectory


@dataclass(frozen=True)
class DecisionAnnotations:
    source_trajectory_sha256: str
    reviewer: str
    authorization: str
    choices: tuple[tuple[int, int], ...]  # (zero-based decision, legal-action index)


def read_decision_annotations(path: str | Path, trajectory_sha256: str,
                              trajectory: Trajectory) -> tuple[DecisionAnnotations,
                                                                tuple[DecisionRecord, ...]]:
    """Apply authorized labels only to exact legal decisions in this trajectory.

    The caller must replay-verify ``trajectory`` before using these records to train.
    Synthetic labels must match the scripted action actually played in that replay.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("unsupported decision-annotation schema")
    authorization = raw.get("authorization")
    if authorization not in ("self_recorded", "scripted_scenario"):
        raise ValueError("decision annotations require a supported authorization")
    if (authorization == "scripted_scenario"
            and not trajectory.source.startswith("scripted_")):
        raise ValueError("scripted_scenario labels require a scripted trajectory")
    if raw.get("source_trajectory_sha256") != trajectory_sha256:
        raise ValueError("annotation source trajectory SHA-256 mismatch")
    reviewer = raw.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("decision annotations require a reviewer name")
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("decision annotations require at least one choice")
    seen = set()
    selected = []
    parsed = []
    for choice in choices:
        if not isinstance(choice, dict) or set(choice) != {"decision_index", "action_index"}:
            raise ValueError("annotation choice requires decision_index and action_index")
        decision_index = choice["decision_index"]
        action_index = choice["action_index"]
        if (type(decision_index) is not int or type(action_index) is not int
                or not 0 <= decision_index < len(trajectory.decisions)):
            raise ValueError("annotation decision index is invalid")
        if decision_index in seen:
            raise ValueError("duplicate annotated decision")
        seen.add(decision_index)
        record = trajectory.decisions[decision_index]
        if not 0 <= action_index < len(record.legal_actions):
            raise ValueError("annotation action index is not legal")
        if (authorization == "scripted_scenario"
                and record.legal_actions[action_index] != record.selected_action):
            raise ValueError("scripted_scenario label must match the replayed action")
        selected.append(replace(record, selected_action=record.legal_actions[action_index]))
        parsed.append((decision_index, action_index))
    return (DecisionAnnotations(trajectory_sha256, reviewer.strip(), authorization,
                                tuple(parsed)),
            tuple(selected))
