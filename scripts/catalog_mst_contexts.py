"""Catalog selected MST activations in verified, player-visible trajectories.

Board context is descriptive. This script does not label an MST choice as good
or bad; Set cards and future responses can change the value of an activation.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from goat_ai.agents import load_card_facts
from goat_ai.agents.tactical_guard import MYSTICAL_SPACE_TYPHOON
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file


def _policy_seat(trajectory) -> int:
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("learner_seat" if trajectory.source == "self_play_rl"
                        else "demonstrator_seat")
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("catalog requires a recorded policy seat")
    return seat


def _mst_context(record, index: int, seat: int, action, card_facts: dict) -> dict:
    observation = record.observation
    source_slot = (action.parameters.get("sequence")
                   if action.parameters.get("location") == 8 else None)
    backrow = [card for card in observation.field
               if card.zone == "spell_trap"
               and not (card.controller == seat
                        and card.sequence == source_slot
                        and card.code == MYSTICAL_SPACE_TYPHOON)]
    own = [card for card in backrow if card.controller == seat]
    enemy = [card for card in backrow if card.controller != seat]
    distribution = ("mixed" if own and enemy else "own_only" if own
                    else "enemy_only" if enemy else "none")
    return {
        "decision_index": index,
        "viewer_frame": index + 1,
        "turn": observation.turn,
        "phase": observation.phase,
        "action_kind": action.kind,
        "visible_backrow_distribution": distribution,
        "pass_offered": any(choice.kind == "pass"
                            for choice in record.legal_actions),
        "backrow": [{"relative_controller": "own" if card.controller == seat
                     else "opponent",
                     "position": card.position,
                     "code": card.code,
                     "printed_type": (card_facts.get(card.code, (0, 0, 0))[0]
                                      if card.code is not None else None)}
                    for card in backrow],
    }


def catalog_trajectory(trajectory, card_facts: dict) -> list[dict]:
    """Use only the acting player's visible board at selected MST decisions."""
    seat = _policy_seat(trajectory)
    rows = []
    for index, record in enumerate(trajectory.decisions):
        observation, action = record.observation, record.selected_action
        if (observation.acting_player != seat
                or action.kind not in ("activate", "chain")
                or action.parameters.get("code") != MYSTICAL_SPACE_TYPHOON):
            continue
        rows.append(_mst_context(record, index, seat, action, card_facts))
    return rows


def catalog_opportunities(trajectory, card_facts: dict) -> list[dict]:
    """Include offered MST choices, collapsing repeated identical priority windows."""
    seat = _policy_seat(trajectory)
    rows = []
    seen = set()
    for index, record in enumerate(trajectory.decisions):
        if record.observation.acting_player != seat or len(record.legal_actions) < 2:
            continue
        mst_actions = tuple(action for action in record.legal_actions
                            if action.kind in ("activate", "chain")
                            and action.parameters.get("code") == MYSTICAL_SPACE_TYPHOON)
        if not mst_actions:
            continue
        selected_mst = record.selected_action in mst_actions
        action = record.selected_action if selected_mst else mst_actions[0]
        row = _mst_context(record, index, seat, action, card_facts)
        row["selected_mst"] = selected_mst
        row["selected_action_kind"] = record.selected_action.kind
        key = (row["turn"], row["phase"], row["selected_action_kind"],
               row["action_kind"], row["visible_backrow_distribution"],
               action.parameters.get("location"), action.parameters.get("sequence"),
               tuple((card["relative_controller"], card["position"], card["code"])
                     for card in row["backrow"]))
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    facts = load_card_facts(args.native_root)
    reports = []
    counts = Counter()
    for path in args.replays:
        trajectory = read_trajectory(path)
        if trajectory.source not in ("policy_evaluation", "self_play_rl"):
            raise ValueError(f"{path}: expected a policy or self-play replay")
        verified = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        rows = catalog_trajectory(trajectory, facts)
        counts.update(row["visible_backrow_distribution"] for row in rows)
        reports.append({"replay": str(path), "replay_sha256": sha256_file(path),
                        "verified_decisions": verified, "selected_mst": rows})
    output = {"schema_version": 1, "note": "descriptive visible context, not play labels",
              "replays": reports, "selected_mst_counts": dict(sorted(counts.items()))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(args.output), "replays": len(reports),
                      "selected_mst_counts": output["selected_mst_counts"]}))


if __name__ == "__main__":
    main()
