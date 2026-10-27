"""Compare the first player-visible decision across GOAT Main Deck identities.

This is an information-flow audit of the opening decision only. It does not
certify that card effects or later decisions hide all private information.
"""

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from time import perf_counter

from goat_ai.engine.decks import read_goat_whitelist
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.replay.fingerprint import sha256_file


def candidate_deck(code: int) -> tuple[int, ...]:
    """Keep the chosen card in the seeded opening slot without a fourth copy."""
    cards = [code, *VANILLA_DECK[1:]]
    if code != VANILLA_DECK[0] and code in cards[1:]:
        cards[cards.index(code, 1)] = VANILLA_DECK[0]
    return tuple(cards)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--own-deck", type=Path,
                        default=Path("examples/decks/nobleman_probe.ydk"))
    parser.add_argument("--seed", type=int, default=52)
    parser.add_argument("--limit", type=int, help="audit only this many eligible IDs")
    parser.add_argument("--output", type=Path, help="write the complete JSON report")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    whitelist = args.native_root / "banlist/GOAT.lflist.conf"
    database = args.native_root / "database/cards.cdb"
    core = args.native_root / "build/libocgcore.so"
    limits = read_goat_whitelist(whitelist)
    with sqlite3.connect(database) as connection:
        card_types = dict(connection.execute("SELECT id, type FROM datas"))
    # The probe inserts one card into the Main Deck. Fusion cards belong in
    # the Extra Deck and are covered by separate identity tests.
    eligible = sorted(code for code, cap in limits.items()
                      if cap > 0 and code in card_types
                      and not card_types[code] & 0x40)
    codes = eligible[:args.limit] if args.limit is not None else eligible
    started = perf_counter()
    baseline = None
    checked = 0
    mismatches = []
    errors = []
    with tempfile.TemporaryDirectory(prefix="goat-hidden-opening-") as directory:
        opponent = Path(directory) / "candidate.ydk"
        for code in codes:
            opponent.write_text("#main\n" + "\n".join(map(str, candidate_deck(code)))
                                + "\n#extra\n!side\n", encoding="utf-8")
            engine = ExperimentalOcgcoreEngine(args.native_root)
            try:
                decision = engine.reset(str(args.own_deck), str(opponent), args.seed)
                if code not in {card.code for card in engine.probe.observation(1).hand}:
                    raise AssertionError("replacement card absent from opponent opening hand")
                visible = (decision.observation, decision.legal_actions)
                if baseline is None:
                    baseline = visible
                elif visible != baseline:
                    mismatches.append(code)
                checked += 1
            except Exception as exc:  # noqa: BLE001 - report every failed card, then exit nonzero
                errors.append({"code": code, "error": f"{type(exc).__name__}: {exc}"})
            finally:
                engine.close()

    report = {
        "scope": "opening decision only; opponent hand/deck identities changed",
        "seed": args.seed,
        "own_deck": str(args.own_deck),
        "own_deck_sha256": sha256_file(args.own_deck),
        "whitelist_sha256": sha256_file(whitelist),
        "database_sha256": sha256_file(database),
        "core_sha256": sha256_file(core),
        "eligible_main_deck_ids": len(eligible),
        "attempted": len(codes),
        "checked": checked,
        "mismatches": mismatches,
        "errors": errors,
        "elapsed_seconds": perf_counter() - started,
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if mismatches or errors or checked != len(codes):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
