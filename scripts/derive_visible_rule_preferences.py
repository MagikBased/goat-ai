"""Turn a narrow set of verified visible-state audit flags into synthetic preferences.

These labels are automated hypotheses, not human reviews or winning-move
claims. Keep the output separate from human annotations and evaluate a trained
child on held-out decks before using it as a reference policy.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from goat_ai.agents.card_metadata import load_weak_flip_monster_attack
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.replay_review import (
    THUNDER_DRAGON,
    review_candidates,
)
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_decision_preferences, read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file


RULE_SET_ID = "visible_audit_v1"
SUPPORTED_CATEGORIES = frozenset({
    "bls_targets_itself_with_enemy_option",
    "chaos_sorcerer_targets_itself_with_enemy_option",
    "thunder_empty_search_with_copies_available",
    "weak_flip_normal_summon_with_set_available",
    "pot_before_available_thunder_dragon",
    "ring_targets_own_with_safe_enemy_option",
})


def preferred_indices(record, category: str) -> list[int]:
    """Return legal alternatives justified by one player-visible audit flag."""
    seat = record.observation.acting_player
    actions = record.legal_actions
    if category in ("bls_targets_itself_with_enemy_option",
                    "chaos_sorcerer_targets_itself_with_enemy_option"):
        return [i for i, action in enumerate(actions)
                if action.kind == "select_card"
                and action.parameters.get("location") == 4
                and action.parameters.get("controller") == 1 - seat]
    if category == "thunder_empty_search_with_copies_available":
        counts = [sum(card.get("code") == THUNDER_DRAGON
                      for card in action.parameters.get("cards", ()))
                  if action.kind == "select_cards" else 0 for action in actions]
        maximum = max(counts, default=0)
        return [i for i, count in enumerate(counts) if count == maximum] if maximum else []
    if category == "weak_flip_normal_summon_with_set_available":
        code = record.selected_action.parameters.get("code")
        return [i for i, action in enumerate(actions)
                if action.kind == "set_monster" and action.parameters.get("code") == code]
    if category == "pot_before_available_thunder_dragon":
        return [i for i, action in enumerate(actions)
                if action.kind == "activate" and action.parameters.get("code") == THUNDER_DRAGON]
    if category == "ring_targets_own_with_safe_enemy_option":
        enemy = {card.sequence: card for card in record.observation.field
                 if card.controller == 1 - seat and card.zone == "monster"
                 and card.position == "faceup"}
        return [i for i, action in enumerate(actions)
                if action.kind == "select_card"
                and action.parameters.get("controller") == 1 - seat
                and action.parameters.get("location") == 4
                and (card := enemy.get(action.parameters.get("sequence"))) is not None
                and card.attack is not None
                and card.attack < record.observation.life_points[seat]]
    return []


def derive(trajectory, candidates) -> tuple[list[dict], Counter]:
    """Keep one unambiguous automated comparison per recorded decision."""
    result = []
    counts = Counter()
    seen = set()
    for candidate in candidates:
        if candidate.category not in SUPPORTED_CATEGORIES \
                or candidate.decision_index in seen:
            continue
        record = trajectory.decisions[candidate.decision_index]
        disfavored = record.legal_actions.index(record.selected_action)
        preferred = sorted(set(preferred_indices(record, candidate.category)) - {disfavored})
        if not preferred:
            continue
        result.append({"decision_index": candidate.decision_index,
                       "preferred_action_indices": preferred,
                       "disfavored_action_indices": [disfavored]})
        counts[candidate.category] += 1
        seen.add(candidate.decision_index)
    return result, counts


def validate_automated_preferences(trajectory, preferences, weak_flip_attacks) -> None:
    """Reject edits that no longer match the declared visible-rule output."""
    expected, _ = derive(trajectory, review_candidates(
        trajectory, weak_flip_attacks=weak_flip_attacks))
    actual = [{"decision_index": item.decision_index,
               "preferred_action_indices": list(item.preferred_action_indices),
               "disfavored_action_indices": list(item.disfavored_action_indices)}
              for item in preferences.preferences]
    if actual != expected:
        raise ValueError("automated preferences do not match visible_audit_v1")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error("output directory must be empty")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    weak_flip_attacks = load_weak_flip_monster_attack(args.native_root)
    report = []
    for path in args.replays:
        trajectory = read_trajectory(path)
        if trajectory.source not in ("policy_evaluation", "self_play_rl"):
            raise ValueError(f"{path}: expected a policy or self-play replay")
        verified = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        candidates = review_candidates(trajectory, weak_flip_attacks=weak_flip_attacks)
        preferences, categories = derive(trajectory, candidates)
        if not preferences:
            continue
        seat = trajectory.skill_metadata.get("learner_seat" if trajectory.source
                                             == "self_play_rl" else "demonstrator_seat")
        payload = {
            "schema_version": 1,
            "source_trajectory_sha256": sha256_file(path),
            "authorization": "automated_rule",
            "rule_set_id": RULE_SET_ID,
            "reviewer": "GOAT AI automated visible-audit rules",
            "reviewed_seat": seat,
            "preferences": preferences,
        }
        output = args.output_dir / f"{path.stem}.preference.json"
        if output.exists():
            raise ValueError(f"duplicate replay basename would overwrite {output}")
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
        read_decision_preferences(output, sha256_file(path), trajectory)
        report.append({"replay": str(path), "replay_sha256": sha256_file(path),
                       "verified_decisions": verified, "output": str(output),
                       "output_sha256": sha256_file(output),
                       "preferences": len(preferences), "categories": dict(categories)})
    manifest = {"schema_version": 1, "rule_set_id": RULE_SET_ID,
                "labels_are_human_reviewed": False, "replays": report}
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir),
                      "replays_with_preferences": len(report),
                      "preferences": sum(item["preferences"] for item in report),
                      "manifest_sha256": sha256_file(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
