"""Compare a recorded flagged activation with a legal phase transition.

This is an offline diagnostic. Each branch replays the same complete-state
prefix; it is not an information-safe online search algorithm.
"""

import argparse
import json
from pathlib import Path

from goat_ai.replay import read_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.evaluate_decision_branches import evaluate_branches


def evaluate_flagged_phase_branches(
    audit_path: Path, checkpoint: Path, native_root: Path, output_dir: Path,
    category: str, phase_action: str = "end_phase",
) -> dict:
    """Evaluate every distinct matching flag with the requested phase action."""
    if phase_action not in ("end_phase", "battle_phase"):
        raise ValueError("phase_action must be end_phase or battle_phase")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    skipped = 0
    seen: set[tuple[str, int]] = set()
    for report in audit["replays"]:
        source = Path(report["trajectory"])
        relevant = [candidate for candidate in report.get("candidates", ())
                    if candidate["category"] == category]
        if not relevant:
            continue
        trajectory = read_trajectory(source)
        for candidate in relevant:
            index = candidate["decision_index"]
            key = (str(source), index)
            if key in seen:
                continue
            seen.add(key)
            decision = trajectory.decisions[index]
            alternatives = [i for i, action in enumerate(decision.legal_actions)
                            if action.kind == phase_action]
            if not alternatives:
                skipped += 1
                continue
            selected = decision.legal_actions.index(decision.selected_action)
            if selected in alternatives:
                raise ValueError(f"flagged selected action is {phase_action}: {source}:{index}")
            branch_dir = output_dir / f"{source.stem}_d{index}"
            branch = evaluate_branches(source, checkpoint, native_root, index,
                                       (selected, alternatives[0]), branch_dir)
            by_index = {item["action_index"]: item for item in branch["branches"]}
            cases.append({
                "source": str(source), "source_sha256": sha256_file(source),
                "decision_index": index, "policy_seat": report["policy_seat"],
                "selected_action_index": selected,
                "phase_action_index": alternatives[0],
                "selected_winner": by_index[selected]["winner"],
                "phase_winner": by_index[alternatives[0]]["winner"],
                "branch_report": str(branch_dir / "report.json"),
                "branch_report_sha256": sha256_file(branch_dir / "report.json"),
            })
    summary = {
        "source_audit": str(audit_path),
        "source_audit_sha256": sha256_file(audit_path),
        "checkpoint_sha256": sha256_file(checkpoint),
        "category": category, "phase_action": phase_action,
        "skipped_without_phase_action": skipped,
        "scope": "offline_exact_state_phase_counterfactual_diagnostic",
        "cases": cases,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--category", required=True)
    parser.add_argument("--phase-action", choices=("end_phase", "battle_phase"),
                        default="end_phase")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_flagged_phase_branches(
        args.audit, args.checkpoint, args.native_root, args.output_dir,
        args.category, args.phase_action)
    print(json.dumps({"cases": len(result["cases"]),
                      "skipped_without_phase_action": result["skipped_without_phase_action"],
                      "summary": str(args.output_dir / "summary.json")}, indent=2))


if __name__ == "__main__":
    main()
