"""Measure observed material at review-queue activations, without labeling plays.

Only a completed chain provides a post-effect material snapshot. A target
prompt is not an activation, and a duel ending mid-chain has no measured
post-chain margin. Neither case is silently counted as a zero-card trade.
"""

import argparse
import json
from pathlib import Path

from goat_ai.agents.card_metadata import load_card_facts
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.effect_material import effect_material_changes
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.validate_review_queue_labels import queue_sources, verify_queue_items


def material_review_rows(trajectory, offered: dict[int, dict], facts: dict) -> list[dict]:
    """Join selected review decisions to resolved, observed effect margins."""
    effects = {effect["decision_index"]: effect
               for effect in effect_material_changes(trajectory, facts)}
    rows = []
    for index, item in sorted(offered.items()):
        action = trajectory.decisions[index].selected_action
        measured = effects.get(index)
        status = ("resolved" if measured is not None else
                  "not_activation" if action.kind not in ("activate", "chain") else
                  "no_chain_closure")
        rows.append({
            "decision_index": index,
            "audit_flags": item.get("audit_flags", []),
            "action_kind": action.kind,
            "action_code": action.parameters.get("code"),
            "status": status,
            "material_delta": measured["material_delta"] if measured else None,
            "additional_activations": (measured["additional_activations"]
                                       if measured else None),
            "resolved_before_decision": (measured["resolved_before_decision"]
                                         if measured else None),
        })
    return rows


def audit_review_material(queue_path: Path, native_root: Path) -> dict:
    """Verify queue sources, then measure only the recorded branch."""
    queue_path = queue_path.resolve()
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    sources = queue_sources(queue, queue_path)
    facts = load_card_facts(native_root)
    rows = []
    verified = 0
    for digest, (replay_path, offered) in sorted(sources.items()):
        if sha256_file(replay_path) != digest:
            raise ValueError(f"source replay changed: {replay_path}")
        trajectory = read_trajectory(replay_path)
        verify_queue_items(trajectory, offered, queue["checkpoint_sha256"])
        verified += verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
        audit_trajectory_visibility(trajectory)
        rows.extend({"trajectory_sha256": digest, **row}
                    for row in material_review_rows(trajectory, offered, facts))
        if sha256_file(replay_path) != digest:
            raise ValueError(f"source replay changed during audit: {replay_path}")
    return {
        "schema_version": 1,
        "scope": "observed_chain_visible_material_not_counterfactual_or_value",
        "queue_sha256": sha256_file(queue_path),
        "verified_source_decisions": verified,
        "rows": sorted(rows, key=lambda row: (
            row["trajectory_sha256"], row["decision_index"])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_review_material(args.queue, args.native_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(args.output), "items": len(report["rows"]),
                      "verified_source_decisions": report["verified_source_decisions"]}))


if __name__ == "__main__":
    main()
