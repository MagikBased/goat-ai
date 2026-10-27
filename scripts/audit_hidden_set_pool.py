"""Compare next-turn player views after a GOAT card is Set.

The native engine still owns both Decks. Only its player-visible observation
and legal actions are compared; a private query verifies the Set identity.
"""

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from time import perf_counter

from goat_ai.engine.decks import read_goat_whitelist
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay.fingerprint import sha256_file
from scripts.audit_hidden_opening_pool import candidate_deck

MYSTICAL_SPACE_TYPHOON = 5318639


class CardCannotBeSet(ValueError):
    """The native Main Phase offers no Set action for this card."""


def reach_next_main_phase(own_deck: Path, opponent_deck: Path, root: Path,
                          seed: int, hidden_code: int, zone: str = "spell_trap",
                          target_hidden: bool = False):
    if zone not in ("spell_trap", "monster"):
        raise ValueError("zone must be spell_trap or monster")
    if target_hidden and zone != "spell_trap":
        raise ValueError("MST target audit requires spell_trap zone")
    set_kind = "set_spell_trap" if zone == "spell_trap" else "set_monster"
    location = 8 if zone == "spell_trap" else 4
    with GoatEnvironment(str(own_deck), str(opponent_deck), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        opening = (observation, env.legal_actions())
        if hidden_code not in {card.code for card in env.engine.probe.observation(1).hand}:
            raise AssertionError("replacement card absent from opponent opening hand")
        set_done = False
        for _ in range(60):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not set_done:
                action = next((option for option in actions
                               if option.kind == set_kind
                               and option.parameters.get("code") == hidden_code), None)
                set_done |= action is not None
                if observation.phase == "main1" and action is None:
                    raise CardCannotBeSet(hidden_code)
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1":
                if not set_done:
                    raise AssertionError("opponent card was not Set")
                hidden = [card for card in observation.field
                          if card.controller == 1 and card.zone == zone]
                if len(hidden) != 1 or hidden[0].position != "facedown" \
                        or hidden[0].code is not None:
                    raise AssertionError("opponent Set card was not hidden")
                if env.engine.probe._query_location(1, location)[hidden[0].sequence].code \
                        != hidden_code:
                    raise AssertionError("private Set identity differs from candidate")
                if len(actions) < 2:
                    raise AssertionError("next Main Phase lacks alternative actions")
                if target_hidden:
                    activation = next((option for option in actions
                                       if option.kind == "activate" and
                                       option.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                                      None)
                    if activation is None:
                        raise AssertionError("MST activation absent at next Main Phase")
                    observation = env.step(activation)
                    actions = env.legal_actions()
                    if actions and all(option.kind == "place" for option in actions):
                        observation = env.step(actions[0])
                        actions = env.legal_actions()
                    target = [option for option in actions
                              if option.kind == "select_card"
                              and option.parameters.get("controller") == 1
                              and option.parameters.get("location") == location
                              and option.parameters.get("sequence") == hidden[0].sequence]
                    if len(target) != 1 or target[0].parameters.get("code") is not None:
                        raise AssertionError("hidden MST target unavailable or reveals ID")
                return opening, (hidden[0].zone, hidden[0].sequence), (
                    observation, actions)
            if action is None:
                action = next((option for option in actions if option.kind in (
                    "pass", "end_phase", "no", "place")), None)
            if action is None:
                raise AssertionError("no passive action before next Main Phase")
            observation = env.step(action)
    raise AssertionError("next Main Phase was not reached within 60 decisions")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--own-deck", type=Path,
                        default=Path("examples/decks/nobleman_probe.ydk"))
    parser.add_argument("--seed", type=int, default=52)
    parser.add_argument("--zone", choices=("spell_trap", "monster"),
                        default="spell_trap", help="type of card the opponent Sets")
    parser.add_argument("--target-hidden", action="store_true",
                        help="compare MST target prompts after the opponent Sets backrow")
    parser.add_argument("--limit", type=int, help="audit only this many eligible IDs")
    parser.add_argument("--output", type=Path, help="write the complete JSON report")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.target_hidden and args.zone != "spell_trap":
        parser.error("--target-hidden requires --zone spell_trap")

    whitelist = args.native_root / "banlist/GOAT.lflist.conf"
    database = args.native_root / "database/cards.cdb"
    core = args.native_root / "build/libocgcore.so"
    limits = read_goat_whitelist(whitelist)
    with sqlite3.connect(database) as connection:
        card_types = dict(connection.execute("SELECT id, type FROM datas"))
    type_mask = (0x2 | 0x4) if args.zone == "spell_trap" else 0x1
    eligible = sorted(code for code, cap in limits.items()
                      if cap > 0 and card_types.get(code, 0) & type_mask
                      and not card_types[code] & 0x40)
    codes = eligible[:args.limit] if args.limit is not None else eligible
    started = perf_counter()
    opening_baseline = None
    baselines = {}
    group_counts = {}
    checked = 0
    not_settable = []
    mismatches = []
    errors = []
    with tempfile.TemporaryDirectory(prefix="goat-hidden-set-") as directory:
        opponent = Path(directory) / "candidate.ydk"
        own_deck = args.own_deck
        if args.target_hidden:
            own_deck = Path(directory) / "mst_probe.ydk"
            own_deck.write_text("#main\n" + "\n".join(map(str, candidate_deck(
                MYSTICAL_SPACE_TYPHOON))) + "\n#extra\n!side\n", encoding="utf-8")
        own_deck_sha256 = sha256_file(own_deck)
        for code in codes:
            opponent.write_text("#main\n" + "\n".join(map(str, candidate_deck(code)))
                                + "\n#extra\n!side\n", encoding="utf-8")
            try:
                opening, slot, next_main = reach_next_main_phase(
                    own_deck, opponent, args.native_root, args.seed, code,
                    args.zone, args.target_hidden)
                if opening_baseline is None:
                    opening_baseline = opening
                elif opening != opening_baseline:
                    mismatches.append({"code": code, "stage": "opening"})
                if slot not in baselines:
                    baselines[slot] = next_main
                elif next_main != baselines[slot]:
                    mismatches.append({"code": code, "stage": "after_set",
                                       "public_slot": slot})
                group_counts[slot] = group_counts.get(slot, 0) + 1
                checked += 1
            except CardCannotBeSet:
                not_settable.append(code)
            except Exception as exc:  # noqa: BLE001 - collect failures, then exit nonzero
                errors.append({"code": code, "error": f"{type(exc).__name__}: {exc}"})

    report = {
        "scope": ("opening and MST hidden-target prompt after opponent Sets one card"
                  if args.target_hidden else
                  "opening and next own Main Phase after opponent Sets one card"),
        "zone": args.zone,
        "seed": args.seed,
        "own_deck": ("generated MST plus vanilla probe" if args.target_hidden
                     else str(args.own_deck)),
        "own_deck_sha256": own_deck_sha256,
        "whitelist_sha256": sha256_file(whitelist),
        "database_sha256": sha256_file(database),
        "core_sha256": sha256_file(core),
        "eligible_ids": len(eligible),
        "attempted": len(codes),
        "checked": checked,
        "not_settable": not_settable,
        "public_slot_groups": {f"{zone}:{sequence}": count
                               for (zone, sequence), count in group_counts.items()},
        "mismatches": mismatches,
        "errors": errors,
        "elapsed_seconds": perf_counter() - started,
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if mismatches or errors or checked + len(not_settable) != len(codes):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
