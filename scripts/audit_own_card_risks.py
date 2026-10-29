"""Count visible own-card risk patterns in verified policy trajectories.

These are diagnostic flags, not automatic training labels. Resolved material
can include responses and triggers; a negative delta alone is not a bad play.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from goat_ai.agents.card_metadata import load_card_facts
from goat_ai.agents.tactical_guard import (
    MYSTICAL_SPACE_TYPHOON,
    RING_OF_DESTRUCTION,
    safe_idle_own_ring_indices,
    safe_own_one_shot_response_indices,
    safe_target_indices,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.effect_material import effect_material_changes
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file


def own_card_risk_rows(trajectory, facts: dict) -> tuple[list[dict], Counter]:
    """Flag selected own-card patterns using only each actor's legal view."""
    seat = (trajectory.skill_metadata or {}).get("demonstrator_seat")
    if trajectory.source != "policy_evaluation" or type(seat) is not int or seat not in (0, 1):
        raise ValueError("expected a policy-evaluation trajectory with a policy seat")
    effects = {entry["decision_index"]: entry
               for entry in effect_material_changes(trajectory, facts)}
    rows = []
    counts = Counter()
    for index, record in enumerate(trajectory.decisions):
        if record.observation.acting_player != seat:
            continue
        counts["policy_decisions"] += 1
        obs, legal = record.observation, record.legal_actions
        chosen = legal.index(record.selected_action)
        if len(legal) < 2:
            continue
        counts["multi_action_policy_decisions"] += 1
        action = record.selected_action
        flags = []
        if (action.kind in ("activate", "chain")
                and action.parameters.get("code") == RING_OF_DESTRUCTION
                and chosen not in safe_idle_own_ring_indices(obs, legal, range(len(legal)))):
            flags.append("idle_own_only_ring")
        if (action.kind == "chain"
                and action.parameters.get("code") == MYSTICAL_SPACE_TYPHOON
                and chosen not in safe_own_one_shot_response_indices(
                    obs, legal, range(len(legal)), facts)):
            flags.append("mst_on_own_resolving_one_shot")
        if (action.kind == "select_card" and obs.chain
                and chosen not in safe_target_indices(
                    obs, legal, range(len(legal)), protect_removal_targets=True)):
            flags.append("own_removal_target_with_enemy_option")
        if not flags:
            continue
        counts["flagged_decisions"] += 1
        counts.update(flags)
        effect = effects.get(index)
        if action.kind in ("activate", "chain"):
            if effect is None:
                counts["flagged_activations_without_chain_closure"] += 1
            elif effect["additional_activations"]:
                counts["flagged_activations_with_additional_activations"] += 1
            else:
                counts["flagged_single_activations_resolved"] += 1
                if effect["material_delta"] < 0:
                    counts["flagged_single_activations_negative_material"] += 1
        rows.append({"decision_index": index, "flags": flags,
                     "action_kind": action.kind,
                     "action_code": action.parameters.get("code"),
                     "material_delta": effect["material_delta"] if effect else None,
                     "additional_activations": (effect["additional_activations"]
                                                if effect else None)})
    return rows, counts


def audit_replays(paths: list[Path], native_root: Path) -> dict:
    if not paths or len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("provide distinct replay paths")
    facts = load_card_facts(native_root)
    total = Counter()
    games = []
    for path in paths:
        path = path.resolve()
        digest = sha256_file(path)
        trajectory = read_trajectory(path)
        verified = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
        audit_trajectory_visibility(trajectory)
        rows, counts = own_card_risk_rows(trajectory, facts)
        if sha256_file(path) != digest:
            raise ValueError(f"replay changed during audit: {path}")
        total.update(counts)
        games.append({"trajectory": str(path), "sha256": digest,
                      "inference": (trajectory.skill_metadata or {}).get("policy_inference"),
                      "verified_decisions": verified, "counts": dict(sorted(counts.items())),
                      "flags": rows})
    return {"schema_version": 1, "scope": "visible_risk_not_action_value_or_training_labels",
            "counts": dict(sorted(total.items())), "games": games}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_replays(args.replays, args.native_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(args.output), "games": len(report["games"]),
                      "counts": report["counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
