"""Compare opt-in guard masks on identical, previously verified replay decisions.

This is a fixed-state coverage diagnostic, not a competitive evaluation.
Input must be a report produced by audit_policy_replays.py, whose replay
verification and policy-choice reproduction precede this comparison.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from goat_ai.agents import load_card_facts
from goat_ai.agents.tactical_guard import (
    safe_idle_own_ring_indices,
    safe_one_shot_response_indices,
    safe_optional_own_loss_indices,
    safe_target_indices,
)
from goat_ai.replay import read_trajectory
from goat_ai.replay.fingerprint import sha256_file


def count_mask_delta(trajectory, card_facts) -> Counter:
    """Count v5's extra removals at the recorded v1 policy's visited states."""
    seat = (trajectory.skill_metadata or {}).get("demonstrator_seat")
    if trajectory.source != "policy_evaluation" or seat not in (0, 1):
        raise ValueError("expected a recorded policy-evaluation seat")
    if trajectory.skill_metadata.get("policy_inference") != "greedy_own_loss_guard_v1":
        raise ValueError("expected a v1-guarded source replay")
    counts = Counter()
    for record in trajectory.decisions:
        if record.observation.acting_player != seat or len(record.legal_actions) < 2:
            continue
        counts["multi_action_policy_decisions"] += 1
        obs, legal = record.observation, record.legal_actions
        chosen = legal.index(record.selected_action)
        base = safe_optional_own_loss_indices(obs, legal, range(len(legal)))
        v1 = safe_target_indices(obs, legal, base, protect_removal_targets=True)
        if chosen not in v1:
            raise ValueError("recorded choice is inconsistent with the v1 mask")
        one_shot = safe_one_shot_response_indices(obs, legal, base, card_facts)
        ring = safe_idle_own_ring_indices(obs, legal, one_shot)
        v5 = safe_target_indices(obs, legal, ring, protect_removal_targets=True)
        if not set(v5) <= set(v1):
            raise ValueError("v5 unexpectedly expanded the v1 action set")
        if len(v5) < len(v1):
            counts["narrowed_decisions"] += 1
            counts["additional_removed_actions"] += len(set(v1) - set(v5))
        if chosen not in v5:
            counts["recorded_choices_removed_by_v5"] += 1
            if chosen not in one_shot:
                counts["recorded_one_shot_mst_responses_removed"] += 1
            elif chosen not in ring:
                counts["recorded_idle_own_ring_activations_removed"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_report", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    args = parser.parse_args()
    audit = json.loads(args.audit_report.read_text(encoding="utf-8"))
    facts = load_card_facts(args.native_root)
    total = Counter()
    rows = audit.get("replays")
    if not isinstance(rows, list) or not rows:
        raise ValueError("audit report has no verified replays")
    for row in rows:
        if (row.get("choice_verification") != "reproduced_greedy"
                or not isinstance(row.get("verified_policy_choices"), int)):
            raise ValueError("audit report lacks reproduced policy choices")
        path = Path(row["trajectory"])
        if sha256_file(path) != row.get("trajectory_sha256"):
            raise ValueError(f"replay fingerprint changed: {path}")
        total.update(count_mask_delta(read_trajectory(path), facts))
    print(json.dumps({"source_audit_sha256": sha256_file(args.audit_report),
                      "replays": len(rows), "counts": dict(sorted(total.items()))},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
