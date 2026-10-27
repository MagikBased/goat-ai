"""Inspect EDOPro replay containers without exporting private card data."""

import argparse
import json
from pathlib import Path

from goat_ai.engine.decks import read_goat_whitelist
from goat_ai.engine.ocgcore_probe import GOAT_FLAGS
from goat_ai.replay import ReplayContainerError, read_edopro_container


def goat_rules_screen(replay) -> dict:
    """Check replay setup against the one native rules profile we currently run."""
    deck_replay = replay.embedded_legacy_replay() or replay
    settings = deck_replay.settings
    if settings is None:
        return {"goat_rules_screen": "unavailable_no_legacy_settings"}
    mismatches = []
    if deck_replay.player_count != 2:
        mismatches.append("player_count")
    if deck_replay.duel_flags != GOAT_FLAGS:
        mismatches.append("duel_flags")
    if settings.starting_life_points != 8000:
        mismatches.append("starting_life_points")
    if settings.opening_hand_size != 5:
        mismatches.append("opening_hand_size")
    if settings.draw_count != 1:
        mismatches.append("draw_count")
    return {
        "goat_rules_screen": ("setup_candidate_only" if not mismatches
                              else "unsupported_setup"),
        "goat_rules_mismatches": mismatches,
    }


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
            report = {"path": str(path), **replay.summary(),
                      **goat_rules_screen(replay)}
            if whitelist is not None:
                report.update(goat_pool_screen(replay, whitelist))
            summaries.append(report)
        except (OSError, ReplayContainerError) as exc:
            parser.error(f"{path}: {exc}")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
