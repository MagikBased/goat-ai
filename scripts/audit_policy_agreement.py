"""Compare policies with teacher choices in replay-verified held-out duels.

This off-policy diagnostic measures action agreement, not competitive strength.
"""

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import torch

from goat_ai.actions import Action
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.replay import (
    DecisionRecord,
    ReplayMismatch,
    Trajectory,
    demonstrator_records,
    read_trajectory,
    verify_trajectory,
)
from goat_ai.training import load_policy_agent

SCOPES = ("all", "multi_option", "multiple_kinds", "known_hand",
          "known_hand_multi_option", "chain", "chain_multi_option",
          "chain_target", "chain_target_multi_option")
STAPLES = {
    71413901: "Breaker the Magical Warrior",
    44763025: "Delinquent Duo",
    45986603: "Snatch Steal",
    55144522: "Pot of Greed",
    504700116: "Nobleman of Crossout",
    14087893: "Book of Moon",
    504700118: "Black Luster Soldier - Envoy of the Beginning",
    19613556: "Heavy Storm",
    511000824: "Ring of Destruction",
    79571449: "Graceful Charity",
}
SOURCE_KINDS = frozenset((
    "activate", "attack", "chain", "change_position", "flip_summon",
    "normal_summon", "set_monster", "set_spell_trap", "special_summon",
))


def source_code(action: Action) -> int | None:
    """A target-choice code identifies a target, not the played card."""
    if action.kind not in SOURCE_KINDS:
        return None
    code = action.parameters.get("code")
    return code if isinstance(code, int) else None


def staple_context(record, staple_codes: set[int]) -> dict[str, set[int]]:
    offered = {code for action in record.legal_actions
               if (code := source_code(action)) in staple_codes}
    selected = source_code(record.selected_action)
    chain = record.observation.chain
    return {
        "offered": offered,
        "teacher_selected": {selected} if selected in staple_codes else set(),
        "chain_prompt": {chain[-1].card_code}
        if chain and chain[-1].card_code in staple_codes else set(),
    }


def empty_staple_counts() -> dict:
    return {context: {"exact": 0, "kind": 0, "total": 0,
                      "multi_option_total": 0}
            for context in ("offered", "teacher_selected", "chain_prompt")}


def empty_counts() -> dict:
    return {scope: {"exact": 0, "kind": 0, "total": 0} for scope in SCOPES}


def decision_scopes(record) -> tuple[str, ...]:
    scopes = ["all"]
    multiple = len(record.legal_actions) > 1
    if multiple:
        scopes.append("multi_option")
    if len({action.kind for action in record.legal_actions}) > 1:
        scopes.append("multiple_kinds")
    if record.observation.known_opponent_hand_cards:
        scopes.append("known_hand")
        if multiple:
            scopes.append("known_hand_multi_option")
    if record.observation.chain:
        scopes.append("chain")
        if multiple:
            scopes.append("chain_multi_option")
    if any(link.targets for link in record.observation.chain):
        scopes.append("chain_target")
        if multiple:
            scopes.append("chain_target_multi_option")
    return tuple(scopes)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decision_deck(trajectory: Trajectory, record: DecisionRecord) -> str:
    """Attribute each visible decision to the acting player's Main Deck."""
    return trajectory.decks[record.observation.acting_player]


def decision_fingerprint(record: DecisionRecord) -> str:
    """Identify an exact visible decision, including its legal and chosen actions."""
    decision = (asdict(record.observation),
                tuple(asdict(action) for action in record.legal_actions),
                asdict(record.selected_action))
    payload = json.dumps(decision, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, action="append", required=True)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"),
                        default="restricted")
    parser.add_argument("--staple-code", type=int, action="append",
                        help="Audit this card ID; repeat to replace the default high-play cards")
    parser.add_argument("--output", type=Path)
    parser.add_argument("trajectories", nargs="+", type=Path)
    args = parser.parse_args()
    staple_names = (STAPLES if args.staple_code is None else {
        code: STAPLES.get(code, str(code)) for code in args.staple_code})
    if any(code <= 0 for code in staple_names):
        parser.error("staple card codes must be positive")
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    checkpoints = []
    for path in args.checkpoint:
        metadata = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
            raise ValueError(f"{path}: unsupported checkpoint schema")
        seeds = {game["seed"] for game in metadata.get("training_games", ())}
        checkpoints.append((path, seeds))

    counts = {str(path): defaultdict(empty_counts)
              for path, _ in checkpoints}
    staple_counts = {str(path): defaultdict(empty_staple_counts)
                     for path, _ in checkpoints}
    staple_selected_kinds = {str(path): defaultdict(lambda: defaultdict(
        lambda: {"exact": 0, "total": 0, "chosen_kinds": defaultdict(int),
                 "fingerprints": set(), "mismatch_fingerprints": set()}))
                             for path, _ in checkpoints}
    verified = []
    for path in args.trajectories:
        trajectory = read_trajectory(path)
        if not trajectory.deck_sha256 or not trajectory.asset_sha256:
            raise ValueError(f"{path}: replay fingerprints required")
        for checkpoint, seeds in checkpoints:
            if trajectory.seed in seeds:
                raise ValueError(f"{path}: seed {trajectory.seed} overlaps {checkpoint}")
        try:
            count = verify_trajectory(trajectory, engine_type(args.native_root))
        except ReplayMismatch as exc:
            raise ReplayMismatch(f"{path}: {exc}") from exc
        records = demonstrator_records(trajectory)
        seat = (trajectory.skill_metadata or {}).get("demonstrator_seat")
        deck = trajectory.decks[seat] if seat is not None else "both seats"
        verified.append({"path": str(path), "sha256": sha256(path),
                         "seed": trajectory.seed, "deck": deck,
                         "verified_decisions": count,
                         "teacher_decisions": len(records)})
        for checkpoint, _ in checkpoints:
            agent = load_policy_agent(checkpoint)
            for record in records:
                bucket = counts[str(checkpoint)][decision_deck(trajectory, record)]
                chosen = agent.select_action(record.observation, record.legal_actions)
                contexts = staple_context(record, set(staple_names))
                for context, codes in contexts.items():
                    for code in codes:
                        card_bucket = staple_counts[str(checkpoint)][code][context]
                        card_bucket["total"] += 1
                        card_bucket["multi_option_total"] += len(record.legal_actions) > 1
                        card_bucket["exact"] += chosen == record.selected_action
                        card_bucket["kind"] += chosen.kind == record.selected_action.kind
                        if context == "teacher_selected":
                            kind_bucket = staple_selected_kinds[str(checkpoint)][code][
                                record.selected_action.kind]
                            kind_bucket["total"] += 1
                            kind_bucket["exact"] += chosen == record.selected_action
                            kind_bucket["chosen_kinds"][chosen.kind] += 1
                            fingerprint = decision_fingerprint(record)
                            kind_bucket["fingerprints"].add(fingerprint)
                            if chosen != record.selected_action:
                                kind_bucket["mismatch_fingerprints"].add(fingerprint)
                for scope in decision_scopes(record):
                    bucket[scope]["total"] += 1
                    bucket[scope]["exact"] += chosen == record.selected_action
                    bucket[scope]["kind"] += chosen.kind == record.selected_action.kind

    policies = []
    for path, _ in checkpoints:
        by_deck = dict(counts[str(path)])
        overall = {scope: {key: sum(bucket[scope][key] for bucket in by_deck.values())
                           for key in ("exact", "kind", "total")}
                   for scope in SCOPES}
        policies.append({"checkpoint": str(path), "sha256": sha256(path),
                         "overall": overall, "by_deck": by_deck,
                         "by_staple": {
                             str(code): {
                                 "name": staple_names[code], **card_counts,
                                 "teacher_selected_by_kind": {
                                     kind: {"exact": bucket["exact"],
                                            "total": bucket["total"],
                                            "chosen_kinds": dict(bucket["chosen_kinds"]),
                                            "unique_demonstrations": len(
                                                bucket["fingerprints"]),
                                            "unique_mismatches": len(
                                                bucket["mismatch_fingerprints"])}
                                     for kind, bucket in
                                     staple_selected_kinds[str(path)][code].items()},
                             }
                             for code, card_counts in sorted(
                                 staple_counts[str(path)].items())}})
    result = {"engine": args.engine, "trajectories": verified, "policies": policies,
              "interpretation": "off-policy agreement on verified visible decisions; "
              "staple contexts may overlap and omit choices without a card-source "
              "action or active staple chain; not a playing-strength estimate"}
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
