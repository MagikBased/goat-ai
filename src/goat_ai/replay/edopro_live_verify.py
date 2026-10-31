"""Verify a complete or interrupted EDOPro room record against its replay."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from goat_ai.engine.decks import Decklist, read_goat_whitelist, validate_goat_deck
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay.annotations import read_decision_annotations
from goat_ai.replay.edopro_container import read_edopro_container
from goat_ai.replay.edopro_reconstruct import reconstruct_legacy_responses
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.replay.trajectory import read_trajectory


def _without_attributes(view):
    """Compare a schema-v28 room replay with the newer public view."""
    def cards(items):
        return tuple(replace(card, attribute=None) for card in items)

    return replace(view, hand=cards(view.hand), field=cards(view.field),
                   graveyards=tuple(cards(zone) for zone in view.graveyards),
                   banished=tuple(cards(zone) for zone in view.banished),
                   own_extra_deck=cards(view.own_extra_deck))


def _without_levels(view):
    """Compare a pre-v30 room replay with the newer public view."""
    def cards(items):
        return tuple(replace(card, level=None) for card in items)

    return replace(view, hand=cards(view.hand), field=cards(view.field),
                   graveyards=tuple(cards(zone) for zone in view.graveyards),
                   banished=tuple(cards(zone) for zone in view.banished),
                   own_extra_deck=cards(view.own_extra_deck))


def _without_hand_levels(view):
    """Compare a schema-v30 room replay before own-hand Level was recorded."""
    return replace(view, hand=tuple(replace(card, level=None) for card in view.hand))


def deck_composition_sha256(main, extra) -> str:
    """Identify a deck by its cards, independent of shuffled draw order."""
    composition = {"main": sorted(main), "extra": sorted(extra)}
    encoded = json.dumps(composition, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def goat_replay_deck_legality(decks, native_root: str | Path) -> tuple[bool, str | None]:
    """Check the recorded Main/Extra Decks against the pinned GOAT card pool.

    Replay containers do not retain the Side Deck. This gate checks only cards
    that could enter the recorded duel; broader historical rulings are separate.
    """
    root = Path(native_root)
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    if len(decks) != 2:
        return False, "EDOPro replay must contain exactly two player Decks"
    for seat, deck in enumerate(decks):
        try:
            validate_goat_deck(
                Decklist(tuple(deck.main), tuple(deck.extra)), limits,
                root / "database/cards.cdb", root / "database/goat-entries.cdb",
                root / "database/cards-unofficial.cdb")
        except ValueError as error:
            return False, f"player {seat + 1} Deck: {error}"
    return True, None


def verify_edopro_live_recording(replay_path: str | Path, review_path: str | Path,
                                 metadata_path: str | Path,
                                 native_root: str | Path) -> dict:
    """Re-simulate the replay and compare every visible decision and result.

    The external-install comparison is deliberately not a GOAT correctness or
    training-admission decision. Interrupted games verify only their saved
    prefix and have no native terminal winner.
    """
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    historical = metadata.get("historical_patches", False)
    if type(historical) is not bool:
        raise ValueError("metadata historical patch mode is invalid")
    base_source = "edopro_pinned_historical" if historical else "edopro_external_unpatched"
    ruleset = "goat_pinned_historical" if historical else "goat_external_unverified"
    complete = metadata.get("mirror_complete") is True
    prefix = metadata.get("mirror_prefix_valid") is True
    if (metadata.get("source") != base_source
            or metadata.get("training_admitted") is not False
            or complete == prefix):
        raise ValueError("metadata is not a synchronized, excluded EDOPro room recording")
    replay = read_edopro_container(replay_path)
    embedded = replay.embedded_legacy_replay()
    if embedded is None or embedded.header.seed_words is None:
        raise ValueError("EDOPro replay has no embedded seed and responses")
    if metadata.get("core_seed") != list(embedded.header.seed_words):
        raise ValueError("metadata core seed differs from replay")
    deck_hashes = tuple(deck_composition_sha256(deck.main, deck.extra)
                        for deck in embedded.decks)
    goat_decks_legal, goat_deck_error = goat_replay_deck_legality(
        embedded.decks, native_root)
    reconstructed = reconstruct_legacy_responses(
        replay, native_root, historical_patches=historical,
        allow_incomplete=prefix)
    trajectory = read_trajectory(review_path)
    reconstructed_decisions = reconstructed.decisions
    reconstructed_terminal = reconstructed.terminal_observation
    if trajectory.schema_version < 30:
        reconstructed_decisions = tuple(replace(
            decision, observation=_without_levels(decision.observation))
            for decision in reconstructed_decisions)
        reconstructed_terminal = _without_levels(reconstructed_terminal)
    elif trajectory.schema_version < 31:
        reconstructed_decisions = tuple(replace(
            decision, observation=_without_hand_levels(decision.observation))
            for decision in reconstructed_decisions)
        reconstructed_terminal = _without_hand_levels(reconstructed_terminal)
    if trajectory.schema_version == 28:
        reconstructed_decisions = tuple(replace(
            decision, observation=_without_attributes(decision.observation))
            for decision in reconstructed_decisions)
        reconstructed_terminal = _without_attributes(reconstructed_terminal)
    provenance = trajectory.skill_metadata or {}
    authorization = metadata.get("human_authorization")
    if authorization not in (None, "self_recorded"):
        raise ValueError("unsupported human recording authorization")
    human_seat = metadata.get("human_client_seat")
    if human_seat is not None and (type(human_seat) is not int or human_seat != 1):
        raise ValueError("unexpected human client seat")
    has_deck_hashes = ("deck_sha256" in metadata
                       or trajectory.deck_sha256 is not None)
    has_asset_hashes = (metadata.get("asset_sha256") is not None
                        or trajectory.asset_sha256 is not None)
    status = provenance.get("recording_status")
    ai_inference = metadata.get("ai_inference")
    if ai_inference is not None and (
            not isinstance(ai_inference, str)
            or not (ai_inference == "policy_own_loss_guard_v1"
                    or ai_inference == "policy_tactical_fallback_margin_1")):
        raise ValueError("unknown EDOPro AI inference mode")
    if (trajectory.source != (base_source if complete else base_source + "_partial")
            or trajectory.ruleset != ruleset
            or trajectory.schema_version not in (28, 29, 30, 31)
            or (status not in (None, "complete") if complete
                else status != "interrupted")
            or trajectory.decks != tuple(metadata.get("names", ()))
            or provenance.get("authorization") != authorization
            or provenance.get("human_client_seat") != human_seat
            or provenance.get("ai_inference") != ai_inference
            or has_deck_hashes and (trajectory.deck_sha256 != deck_hashes
                                    or metadata.get("deck_sha256") != list(deck_hashes))
            or has_asset_hashes and (
                trajectory.asset_sha256 != reconstructed.asset_sha256
                or metadata.get("asset_sha256") != reconstructed.asset_sha256)
            or trajectory.seed != metadata.get("seed")
            or reconstructed.native_terminal is not complete
            or trajectory.winner != reconstructed.winner
            or complete and trajectory.winner != metadata.get("winner_team")
            or trajectory.decisions != reconstructed_decisions
            or trajectory.terminal_observation != reconstructed_terminal
            or metadata.get("host_responses") != reconstructed.saved_response_count
            or metadata.get("mirror_responses") != reconstructed.saved_response_count
            or metadata.get("retries") != 0
            or metadata.get("lua_errors") != []):
        raise ValueError("EDOPro review trajectory or metadata differs from replay")
    audit_trajectory_visibility(trajectory)
    return {
        "replay_sha256": replay.sha256,
        "responses": reconstructed.saved_response_count,
        "visible_decisions": len(reconstructed.decisions),
        "winner_team": reconstructed.winner,
        "complete": complete,
        "reviewable_prefix": prefix,
        "historical_patches": historical,
        "historical_goat_certified": False,
        "deck_identity_verified": has_deck_hashes,
        "goat_decks_legal": goat_decks_legal,
        "goat_deck_error": goat_deck_error,
        "asset_identity_verified": has_asset_hashes,
        "visibility_audited_decisions": len(trajectory.decisions),
        "training_admitted": False,
    }


def verify_edopro_human_annotations(replay_path: str | Path,
                                    review_path: str | Path,
                                    metadata_path: str | Path,
                                    annotation_path: str | Path,
                                    native_root: str | Path) -> dict:
    """Validate explicit human confirmations against a replay-checked room game."""
    report = verify_edopro_live_recording(replay_path, review_path,
                                          metadata_path, native_root)
    trajectory = read_trajectory(review_path)
    annotations, records = read_decision_annotations(
        annotation_path, sha256_file(review_path), trajectory)
    if annotations.authorization != "self_recorded":
        raise ValueError("EDOPro human confirmations require self_recorded labels")
    return {**report, "confirmed_human_choices": len(records),
            "reviewer": annotations.reviewer,
            "annotation_sha256": sha256_file(annotation_path)}
