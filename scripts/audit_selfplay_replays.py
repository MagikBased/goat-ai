"""Replay-verify sampled self-play duels and shortlist visible-state mistakes."""

import argparse
import json
from pathlib import Path

from goat_ai.agents import load_card_races
from goat_ai.agents.card_metadata import load_weak_flip_monster_attack
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.replay_review import category_counts, review_candidates
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    card_races = load_card_races(args.native_root)
    weak_flip_attacks = load_weak_flip_monster_attack(args.native_root)
    reports = []
    for path in args.replays:
        trajectory = read_trajectory(path)
        if trajectory.source != "self_play_rl":
            raise ValueError(f"{path}: expected self_play_rl source")
        verified = verify_trajectory(
            trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        candidates = review_candidates(trajectory, card_races, weak_flip_attacks)
        reports.append({
            "trajectory": str(path),
            "trajectory_sha256": sha256_file(path),
            "learner_seat": trajectory.skill_metadata["learner_seat"],
            "seed": trajectory.seed,
            "winner": trajectory.winner,
            "verified_decisions": verified,
            "category_counts": category_counts(candidates),
            "candidates": [candidate.to_dict() for candidate in candidates],
        })
    result = {"schema_version": 1, "source": "self_play_rl",
              "policy_choices": "sampled; candidates are not greedy-checkpoint errors",
              "replays": reports}
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(json.dumps({"output": str(args.output), "replays": len(reports),
                          "candidates": sum(len(r["candidates"]) for r in reports)}))
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
