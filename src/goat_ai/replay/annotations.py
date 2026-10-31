"""Validated retrospective action labels tied to a replay-verified duel."""

import json
import re
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
    if authorization not in ("self_recorded", "scripted_scenario",
                             "policy_review", "self_play_review"):
        raise ValueError("decision annotations require a supported authorization")
    if (authorization == "scripted_scenario"
            and not trajectory.source.startswith("scripted_")):
        raise ValueError("scripted_scenario labels require a scripted trajectory")
    metadata = trajectory.skill_metadata or {}
    policy_seat = metadata.get("demonstrator_seat")
    checkpoint_sha256 = metadata.get("policy_checkpoint_sha256")
    if (authorization == "policy_review"
            and (trajectory.source != "policy_evaluation"
                 or type(policy_seat) is not int or policy_seat not in (0, 1)
                 or not isinstance(checkpoint_sha256, str)
                 or re.fullmatch(r"[0-9a-f]{64}", checkpoint_sha256) is None)):
        raise ValueError("policy_review requires a checkpoint-attributed policy replay")
    learner_seat = metadata.get("learner_seat")
    if (authorization == "self_play_review"
            and (trajectory.source != "self_play_rl"
                 or type(learner_seat) is not int or learner_seat not in (0, 1)
                 or (policy_seat is not None
                     and (type(policy_seat) is not int
                          or policy_seat != learner_seat)))):
        raise ValueError("self_play_review requires a learner-seat self-play replay")
    human_seat = None
    explicit_human_indices = None
    if authorization == "self_recorded" and not trajectory.source.startswith("edopro_"):
        if trajectory.source not in ("human_cli", "human_web"):
            raise ValueError("agent replay labels require their review authorization")
        human_seat = metadata.get("demonstrator_seat")
        if (metadata.get("authorization") != "self_recorded"
                or type(human_seat) is not int or human_seat not in (0, 1)):
            raise ValueError("self-recorded labels require an authorized human seat")
        if trajectory.source == "human_web":
            indices = metadata.get("explicit_human_decision_indices")
            if (not isinstance(indices, list) or not indices
                    or any(type(index) is not int or index < 0
                           or index >= len(trajectory.decisions) for index in indices)
                    or indices != sorted(set(indices))):
                raise ValueError("human_web labels require explicit human decision indices")
            explicit_human_indices = set(indices)
    edopro_human_seat = None
    if authorization == "self_recorded" and trajectory.source.startswith("edopro_"):
        edopro_human_seat = metadata.get("human_client_seat")
        if (metadata.get("authorization") != "self_recorded"
                or type(edopro_human_seat) is not int
                or edopro_human_seat not in (0, 1)):
            raise ValueError("EDOPro self-recorded labels require authorized human seat")
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
        if (authorization == "policy_review"
                and record.observation.acting_player != policy_seat):
            raise ValueError("policy_review may label only the policy seat")
        if (authorization == "self_play_review"
                and record.observation.acting_player != learner_seat):
            raise ValueError("self_play_review may label only the learner seat")
        if (edopro_human_seat is not None
                and record.observation.acting_player != edopro_human_seat):
            raise ValueError("EDOPro self-recorded label must belong to the human seat")
        if edopro_human_seat is not None and len(record.legal_actions) < 2:
            raise ValueError("EDOPro self-recorded label needs an optional human choice")
        if human_seat is not None and record.observation.acting_player != human_seat:
            raise ValueError("self-recorded label must belong to the human seat")
        if (explicit_human_indices is not None
                and decision_index not in explicit_human_indices):
            raise ValueError("human_web label was not an explicit human decision")
        if not 0 <= action_index < len(record.legal_actions):
            raise ValueError("annotation action index is not legal")
        if (authorization == "scripted_scenario"
                and record.legal_actions[action_index] != record.selected_action):
            raise ValueError("scripted_scenario label must match the replayed action")
        if (edopro_human_seat is not None
                and record.legal_actions[action_index] != record.selected_action):
            raise ValueError("EDOPro self-recorded label must match the played action")
        if (human_seat is not None
                and record.legal_actions[action_index] != record.selected_action):
            raise ValueError("self-recorded label must match the played action")
        selected.append(replace(record, selected_action=record.legal_actions[action_index]))
        parsed.append((decision_index, action_index))
    return (DecisionAnnotations(trajectory_sha256, reviewer.strip(), authorization,
                                tuple(parsed)),
            tuple(selected))
