"""Inspect EDOPro replay containers without exporting private card data."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from goat_ai.engine.decks import Decklist, read_goat_whitelist, validate_goat_deck
from goat_ai.engine.ocgcore_probe import GOAT_FLAGS
from goat_ai.replay import ReplayContainerError, read_edopro_container
from goat_ai.replay.edopro_container import HAND_TEST, SINGLE_MODE, TAG
from goat_ai.replay.edopro_reconstruct import (
    ReplayReconstructionError,
    reconstruct_legacy_responses,
)


def goat_rules_screen(replay) -> dict:
    """Screen the complete recorded startup against the supported native path."""
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
    if deck_replay.header.flags & (TAG | SINGLE_MODE | HAND_TEST):
        mismatches.append("legacy_replay_mode")
    if deck_replay.header.seed_words is None or not any(deck_replay.header.seed_words):
        mismatches.append("rng_seed")
    if deck_replay.rule_cards:
        mismatches.append("custom_rule_cards")
    if replay is not deck_replay:
        if replay.player_count != deck_replay.player_count:
            mismatches.append("wrapper_player_count")
        if replay.duel_flags != deck_replay.duel_flags:
            mismatches.append("wrapper_duel_flags")
        if (replay.header.seed_words is not None
                and replay.header.seed_words != deck_replay.header.seed_words):
            mismatches.append("wrapper_rng_seed")
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
    exact_id_copy_excess = sum(
        max(0, count - whitelist.get(code, 0))
        for deck in deck_replay.decks
        for code, count in Counter((*deck.main, *deck.extra)).items()
        if whitelist.get(code, 0) > 0
    )
    has_minimum = all(len(deck.main) >= 40 for deck in deck_replay.decks)
    if main_outside or extra_outside or not has_minimum:
        status = "outside_pool_or_deck_size"
    elif exact_id_copy_excess:
        status = "exact_id_copy_limit_exceeded"
    else:
        status = "candidate_only"
    return {
        "goat_pool_screen": status,
        "goat_main_cards_outside_whitelist": main_outside,
        "goat_extra_cards_outside_whitelist": extra_outside,
        "goat_exact_id_copy_excess": exact_id_copy_excess,
        "goat_all_main_decks_at_least_40": has_minimum,
    }


def goat_native_deck_screen(replay, native_root: Path,
                            whitelist: dict[int, int]) -> dict:
    """Use pinned metadata/aliases without publishing replay Deck contents."""
    deck_replay = replay.embedded_legacy_replay() or replay
    if not deck_replay.decks:
        return {"goat_native_deck_screen": "unavailable_no_decks"}
    rejected = 0
    for deck in deck_replay.decks:
        try:
            validate_goat_deck(
                Decklist(deck.main, deck.extra), whitelist,
                native_root / "database/cards.cdb",
                native_root / "database/goat-entries.cdb",
                native_root / "database/cards-unofficial.cdb",
            )
        except ValueError:
            rejected += 1
    return {
        "goat_native_deck_screen": ("candidate_only" if not rejected else "rejected"),
        "goat_native_decks_rejected": rejected,
        "goat_native_side_decks_checked": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--goat-whitelist", type=Path,
                        help="screen Deck membership and minimum Main Deck size; "
                             "a passing screen does not validate GOAT rules")
    parser.add_argument("--native-deck-screen", type=Path,
                        help="screen Decks against pinned GOAT metadata and aliases; "
                             "Side Decks are unavailable in the replay container")
    parser.add_argument("--reconstruct-native", type=Path,
                        help="conditionally replay saved responses on these pinned native assets; "
                             "never admits replay data to training")
    parser.add_argument("--compare-external-unpatched", action="store_true",
                        help="with --reconstruct-native, load external scripts unchanged for "
                             "compatibility comparison only; never a GOAT correctness or "
                             "training-intake result")
    parser.add_argument("--require-goat-candidate", action="store_true",
                        help="exit nonzero unless setup, native Decks, and complete native "
                             "reconstruction all pass; still not training authorization")
    parser.add_argument("--report", type=Path,
                        help="write the same privacy-preserving JSON report to a local file")
    args = parser.parse_args()
    if args.compare_external_unpatched and args.reconstruct_native is None:
        parser.error("external comparison requires --reconstruct-native")
    if args.compare_external_unpatched and args.require_goat_candidate:
        parser.error("unpatched external comparison cannot pass strict GOAT intake")
    if args.native_deck_screen is not None and args.goat_whitelist is not None:
        parser.error("choose either native deck screening or an explicit GOAT whitelist")
    if args.require_goat_candidate and (
            args.native_deck_screen is None or args.reconstruct_native is None
            or args.native_deck_screen.resolve() != args.reconstruct_native.resolve()):
        parser.error("strict GOAT intake requires native Deck screening and "
                     "reconstruction using the same native root")
    try:
        whitelist_path = (args.native_deck_screen / "banlist/GOAT.lflist.conf"
                          if args.native_deck_screen is not None
                          else args.goat_whitelist)
        whitelist = read_goat_whitelist(whitelist_path) if whitelist_path else None
    except (OSError, ValueError) as exc:
        parser.error(f"GOAT whitelist: {exc}")
    if args.native_deck_screen is not None:
        required = ("database/cards.cdb", "database/goat-entries.cdb",
                    "database/cards-unofficial.cdb")
        if any(not (args.native_deck_screen / name).is_file() for name in required):
            parser.error("native deck screen needs all pinned card databases")
    summaries = []
    reconstruction_failed = False
    for path in args.replays:
        try:
            replay = read_edopro_container(path)
            report = {"path": str(path), **replay.summary(),
                      **goat_rules_screen(replay)}
            if whitelist is not None:
                report.update(goat_pool_screen(replay, whitelist))
            if args.native_deck_screen is not None:
                try:
                    report.update(goat_native_deck_screen(
                        replay, args.native_deck_screen, whitelist))
                except (OSError, sqlite3.Error):
                    parser.error("native deck screen could not read pinned card databases")
            if args.reconstruct_native is not None:
                try:
                    trace = reconstruct_legacy_responses(
                        replay, args.reconstruct_native,
                        historical_patches=not args.compare_external_unpatched)
                    manifest = json.dumps(trace.asset_sha256, sort_keys=True,
                                          separators=(",", ":")).encode("ascii")
                    report.update({
                        "conditional_native_reconstruction": "matched",
                        "reconstruction_asset_mode": (
                            "external_unpatched_comparison" if args.compare_external_unpatched
                            else "historical_patched"),
                        "reconstructed_decisions": len(trace.decisions),
                        "saved_response_count": trace.saved_response_count,
                        "embedded_yrp_sha256": trace.embedded_replay_sha256,
                        "native_asset_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                        "training_ready": False,
                    })
                except (ReplayReconstructionError, OSError, RuntimeError) as exc:
                    reconstruction_failed = True
                    if isinstance(exc, ReplayReconstructionError):
                        reason = exc.code
                    elif isinstance(exc, OSError):
                        reason = "native_asset_io_error"
                    else:
                        reason = "native_runtime_error"
                    report.update({"conditional_native_reconstruction": "failed",
                                   "reconstruction_asset_mode": (
                                       "external_unpatched_comparison" if args.compare_external_unpatched
                                       else "historical_patched"),
                                   "reconstruction_failure_code": reason,
                                   "training_ready": False})
                    if (isinstance(exc, ReplayReconstructionError)
                            and exc.response_index is not None):
                        report["reconstruction_response_index"] = exc.response_index
            report["native_goat_compatibility_candidate"] = (
                not args.compare_external_unpatched
                and report["goat_rules_screen"] == "setup_candidate_only"
                and report.get("goat_native_deck_screen") == "candidate_only"
                and report.get("conditional_native_reconstruction") == "matched")
            report["training_ready"] = False
            summaries.append(report)
        except (OSError, ReplayContainerError) as exc:
            parser.error(f"{path}: {exc}")
    output = json.dumps(summaries, indent=2) + "\n"
    if args.report is not None:
        if args.report.resolve() in {path.resolve() for path in args.replays}:
            parser.error("inspection report cannot overwrite an input replay")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")
    if reconstruction_failed:
        raise SystemExit(1)
    if args.require_goat_candidate and not all(
            item["native_goat_compatibility_candidate"] for item in summaries):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
