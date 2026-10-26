"""Inspect EDOPro replay containers without exporting private card data."""

import argparse
import json
from pathlib import Path

from goat_ai.engine.decks import read_goat_whitelist
from goat_ai.replay import ReplayContainerError, read_edopro_container


def goat_pool_screen(replay, whitelist: dict[int, int]) -> dict:
    """Report card-pool compatibility without revealing private Deck IDs."""
    deck_replay = replay.embedded_legacy_replay() or replay
    if not deck_replay.decks:
        return {"goat_pool_screen": "unavailable_no_decks"}
    main = [code for deck in deck_replay.decks for code in deck.main]
    extra = [code for deck in deck_replay.decks for code in deck.extra]
    main_outside = sum(whitelist.get(code, 0) == 0 for code in main)
    extra_outside = sum(whitelist.get(code, 0) == 0 for code in extra)
    has_minimum = all(len(deck.main) >= 40 for deck in deck_replay.decks)
    return {
        "goat_pool_screen": ("candidate_only" if not main_outside
                             and not extra_outside and has_minimum
                             else "outside_pool_or_deck_size"),
        "goat_main_cards_outside_whitelist": main_outside,
        "goat_extra_cards_outside_whitelist": extra_outside,
        "goat_all_main_decks_at_least_40": has_minimum,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--goat-whitelist", type=Path,
                        help="screen Deck membership and minimum Main Deck size; "
                             "a passing screen does not validate GOAT rules")
    args = parser.parse_args()
    try:
        whitelist = (read_goat_whitelist(args.goat_whitelist)
                     if args.goat_whitelist else None)
    except (OSError, ValueError) as exc:
        parser.error(f"GOAT whitelist: {exc}")
    summaries = []
    for path in args.replays:
        try:
            replay = read_edopro_container(path)
            report = {"path": str(path), **replay.summary()}
            if whitelist is not None:
                report.update(goat_pool_screen(replay, whitelist))
            summaries.append(report)
        except (OSError, ReplayContainerError) as exc:
            parser.error(f"{path}: {exc}")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
