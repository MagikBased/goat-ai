"""Find distinct legal actions that a policy feature version cannot tell apart."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.training.policy import CardVocabulary, encode_decision

ACTION_ROWS = (
    "action_kinds", "action_cards", "action_targets", "action_target_context",
    "action_target_mask", "action_numbers", "action_field_slots",
    "action_multi_field_slots",
)


def feature_aliases(features, actions):
    """Return pairs with different public action values but equal action inputs."""
    seen = {}
    aliases = []
    for index, action in enumerate(actions):
        signature = b"".join(getattr(features, name)[index].numpy().tobytes()
                             for name in ACTION_ROWS)
        previous = seen.get(signature)
        if previous is None:
            seen[signature] = index
        elif (action.kind, action.parameters) != (
                actions[previous].kind, actions[previous].parameters):
            aliases.append((previous, index))
    return aliases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectories", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--feature-version", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    vocabulary = CardVocabulary.from_goat_whitelist(
        args.native_root / "banlist/GOAT.lflist.conf", native_root=args.native_root)
    kinds = Counter()
    examples = []
    replays = []
    multi_action = 0
    for path in args.trajectories:
        raw = path.read_bytes()
        trajectory = read_trajectory(path)
        verified = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(raw).digest():
            raise ValueError(f"trajectory changed during audit: {path}")
        replays.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                        "verified_decisions": verified})
        for decision_index, record in enumerate(trajectory.decisions):
            actions = record.legal_actions
            if len(actions) < 2:
                continue
            multi_action += 1
            features = encode_decision(record.observation, actions, vocabulary,
                                       args.feature_version)
            aliases = feature_aliases(features, actions)
            for first, second in aliases:
                kinds[actions[first].kind] += 1
                if len(examples) < 20:
                    examples.append({"replay": str(path), "decision_index": decision_index,
                                     "action_indices": [first, second],
                                     "actions": [
                                         {"kind": actions[i].kind,
                                          "parameters": actions[i].parameters}
                                         for i in (first, second)]})
    report = {"feature_version": args.feature_version, "replays": replays,
              "multi_action_decisions": multi_action,
              "aliased_action_pairs": sum(kinds.values()),
              "aliased_first_kinds": dict(sorted(kinds.items())),
              "examples": examples}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "feature_version", "multi_action_decisions", "aliased_action_pairs",
        "aliased_first_kinds")}, sort_keys=True))


if __name__ == "__main__":
    main()
