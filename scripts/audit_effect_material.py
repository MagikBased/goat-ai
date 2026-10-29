"""Measure resolved visible material changes for selected effect activations."""

import argparse
import json
from collections import Counter
from pathlib import Path

from goat_ai.agents.card_metadata import load_card_facts
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.effect_material import (
    LOCATIONS,
    TYPE_MONSTER,
    effect_material_changes,
)
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    facts = load_card_facts(args.native_root)
    games = []
    by_source = Counter()
    by_delta = Counter()
    selected_by_source = Counter()
    for path in args.replays:
        trajectory = read_trajectory(path)
        verified = verify_trajectory(trajectory,
                                     ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        for record in trajectory.decisions:
            action = record.selected_action
            code = action.parameters.get("code")
            if (action.kind in ("activate", "chain") and type(code) is int
                    and (card := facts.get(code)) is not None
                    and action.parameters.get("location") in LOCATIONS):
                selected_by_source["monster_ability" if card[0] & TYPE_MONSTER
                                   else "spell_trap_effect"] += 1
        effects = effect_material_changes(trajectory, facts)
        by_source.update(item["source_type"] for item in effects)
        by_delta.update((item["source_type"], item["material_delta"])
                        for item in effects)
        games.append({"replay": str(path), "sha256": sha256_file(path),
                      "verified_decisions": verified, "effects": effects})
    report = {
        "schema_version": 1,
        "scope": "observed_chain_material_change_not_counterfactual_value",
        "game_count": len(games),
        "selected_activations_by_source": dict(sorted(selected_by_source.items())),
        "effect_count_by_source": dict(sorted(by_source.items())),
        "effect_count_by_source_and_delta": [
            {"source_type": source, "material_delta": delta, "count": count}
            for (source, delta), count in sorted(by_delta.items())],
        "games": games,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"game_count": report["game_count"],
                      "selected_activations_by_source": report["selected_activations_by_source"],
                      "effect_count_by_source": report["effect_count_by_source"],
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
