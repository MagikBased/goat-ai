"""Find legal choices that a policy feature version represents identically.

This is a representation audit, not a duel-strength or rules-correctness test.
The inputs are player-visible recorded decisions; no native hidden state is read.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from goat_ai.replay import read_trajectory
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import encode_decision


def audit(checkpoint: Path, trajectories: list[Path], *,
          feature_version: int | None = None) -> dict:
    agent = load_policy_agent(checkpoint)
    version = agent.model.feature_version if feature_version is None else feature_version
    counts: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    examples = []
    for path in trajectories:
        trajectory = read_trajectory(path)
        counts["trajectories"] += 1
        for decision_index, record in enumerate(trajectory.decisions):
            if len(record.legal_actions) < 2:
                continue
            counts["multi_action_decisions"] += 1
            counts["legal_actions"] += len(record.legal_actions)
            features = encode_decision(record.observation, record.legal_actions,
                                       agent.vocabulary, version)
            action_fields = [value for name, value in vars(features).items()
                             if name.startswith("action_")]
            signatures: dict[tuple, list[int]] = defaultdict(list)
            for index in range(len(record.legal_actions)):
                signature = tuple((str(field.dtype), tuple(field[index].shape),
                                   field[index].numpy().tobytes())
                                  for field in action_fields)
                signatures[signature].append(index)
            for indices in signatures.values():
                if len(indices) < 2:
                    continue
                counts["collision_groups"] += 1
                counts["colliding_actions"] += len(indices)
                actions = [record.legal_actions[index] for index in indices]
                distinct = len({(action.kind, json.dumps(action.parameters,
                                                       sort_keys=True))
                                for action in actions}) > 1
                if distinct:
                    counts["distinct_choice_groups"] += 1
                    by_kind.update({action.kind for action in actions})
                    if len(examples) < 20:
                        examples.append({
                            "trajectory": str(path), "decision_index": decision_index,
                            "actions": [{"kind": action.kind,
                                         "parameters": action.parameters}
                                        for action in actions[:3]],
                        })
    return {"feature_version": version,
            "counts": dict(counts), "distinct_groups_by_kind": dict(by_kind),
            "examples": examples}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("trajectories", nargs="+", type=Path)
    parser.add_argument("--feature-version", type=int,
                        help="audit a different feature encoder using checkpoint vocabulary")
    args = parser.parse_args()
    print(json.dumps(audit(args.checkpoint, args.trajectories,
                           feature_version=args.feature_version), indent=2))


if __name__ == "__main__":
    main()
