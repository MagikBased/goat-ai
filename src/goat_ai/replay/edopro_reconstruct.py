"""Conditional legacy-response playback on the pinned GOAT native adapter.

An EDOPro replay does not fingerprint its original core and scripts. A trace
from this module is evidence that its responses replay on *our* assets, not
proof of historical fidelity or permission to train on its decisions.
"""

import struct
from dataclasses import dataclass
from pathlib import Path

from goat_ai.engine.decks import Decklist
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import GOAT_FLAGS
from goat_ai.evaluation.visibility import VisibilityViolation, audit_decision_visibility
from goat_ai.observations import Observation
from goat_ai.replay.edopro_container import (
    HAND_TEST,
    SINGLE_MODE,
    TAG,
    EdoReplayContainer,
    ReplayContainerError,
)
from goat_ai.replay.trajectory import DecisionRecord


class ReplayReconstructionError(ValueError):
    """Replay inputs or a saved response diverged from this native adapter."""

    def __init__(self, message: str, *, code: str = "unknown",
                 response_index: int | None = None):
        super().__init__(message)
        self.code = code
        self.response_index = response_index


@dataclass(frozen=True)
class ReconstructedLegacyDuel:
    replay_sha256: str
    embedded_replay_sha256: str | None
    decisions: tuple[DecisionRecord, ...]
    saved_response_count: int
    winner: int | None
    terminal_observation: Observation
    asset_sha256: dict[str, str]


def reconstruct_legacy_responses(replay: EdoReplayContainer,
                                 native_root: str | Path,
                                 *, max_responses: int = 10_000,
                                 ) -> ReconstructedLegacyDuel:
    """Map each legacy native response to one player-visible legal action.

    Staged selections produce multiple public DecisionRecords for one saved
    native response, following the normal environment's action contract.
    Returned records are not admitted to the training pipeline.
    """
    if max_responses < 1:
        raise ValueError("max_responses must be positive")
    source_sha256 = replay.sha256
    embedded_sha256 = None
    if replay.header.format == "yrpX":
        try:
            embedded = replay.embedded_legacy_replay()
        except ReplayContainerError as exc:
            raise ReplayReconstructionError(f"invalid embedded replay: {exc}",
                                            code="invalid_embedded_replay") from exc
        if embedded is None:
            raise ReplayReconstructionError("yrpX has no embedded legacy responses",
                                            code="missing_legacy_responses")
        if (replay.duel_flags != embedded.duel_flags
                or replay.player_count != embedded.player_count
                or (replay.header.seed_words is not None
                    and replay.header.seed_words != embedded.header.seed_words)):
            raise ReplayReconstructionError("yrpX wrapper disagrees with embedded replay",
                                            code="wrapper_mismatch")
        embedded_sha256 = embedded.sha256
        replay = embedded
    settings = replay.settings
    if (replay.header.format != "yrp" or replay.header.flags & (TAG | SINGLE_MODE | HAND_TEST)
            or replay.player_count != 2 or len(replay.decks) != 2
            or replay.duel_flags != GOAT_FLAGS
            or settings is None
            or (settings.starting_life_points, settings.opening_hand_size,
                settings.draw_count) != (8000, 5, 1)
            or replay.header.seed_words is None or not any(replay.header.seed_words)
            or replay.rule_cards):
        raise ReplayReconstructionError("replay startup is outside supported GOAT profile",
                                        code="unsupported_startup")
    if not replay.responses or len(replay.responses) > max_responses:
        raise ReplayReconstructionError("replay response count outside reconstruction bound",
                                        code="response_count_bound")

    engine = ExperimentalOcgcoreEngine(native_root)
    records: list[DecisionRecord] = []
    try:
        deck1, deck2 = (Decklist(deck.main, deck.extra) for deck in replay.decks)
        try:
            decision = engine.reset_recorded(replay.header.seed_words, deck1, deck2)
        except (ValueError, RuntimeError) as exc:
            raise ReplayReconstructionError(f"native replay startup failed: {exc}",
                                            code="native_startup_failed") from exc
        for index, response in enumerate(replay.responses):
            if decision.terminal:
                raise ReplayReconstructionError(
                    f"response {index}: native duel ended before saved responses",
                    code="extra_saved_response", response_index=index)
            try:
                action = engine.action_for_recorded_response(response)
            except ValueError as exc:
                native = engine.probe.decode_pending()
                selection = (native.card_selection or native.sum_selection
                             or native.zone_selection)
                if selection is None or not selection.accepts(response):
                    raise ReplayReconstructionError(
                        f"response {index}: saved bytes do not map to one legal action",
                        code="illegal_saved_response", response_index=index) from exc
                if native.zone_selection is not None:
                    zones = native.zone_selection.zones
                    indices = tuple(zones.index(tuple(response[start:start + 3]))
                                    for start in range(0, len(response), 3))
                else:
                    size = struct.unpack_from("<I", response, 4)[0]
                    indices = struct.unpack_from(f"<{size}I", response, 8)
                for candidate in indices:
                    try:
                        action = engine.action_for_selection_index(candidate)
                        records.append(DecisionRecord(decision.observation,
                                                      decision.legal_actions, action))
                        decision = engine.step(action)
                    except (ValueError, RuntimeError) as stage_exc:
                        raise ReplayReconstructionError(
                            f"response {index}: staged selection diverged: {stage_exc}",
                            code="staged_selection_diverged",
                            response_index=index) from stage_exc
                if native.zone_selection is None and engine.recorded_selection_in_progress():
                    try:
                        action = engine.action_for_recorded_response(response)
                        if action.kind != "finish_selection":
                            raise ValueError("selection did not reach a finish action")
                        records.append(DecisionRecord(decision.observation,
                                                      decision.legal_actions, action))
                        decision = engine.step(action)
                    except (ValueError, RuntimeError) as stage_exc:
                        raise ReplayReconstructionError(
                            f"response {index}: selection finish diverged: {stage_exc}",
                            code="selection_finish_diverged",
                            response_index=index) from stage_exc
                continue
            records.append(DecisionRecord(decision.observation,
                                          decision.legal_actions, action))
            try:
                decision = engine.step(action)
            except (ValueError, RuntimeError) as exc:
                raise ReplayReconstructionError(
                    f"response {index}: native transition failed: {exc}",
                    code="native_transition_failed", response_index=index) from exc
        if not decision.terminal:
            raise ReplayReconstructionError("saved responses ended before native terminal state",
                                            code="incomplete_saved_responses")
        for index, record in enumerate(records):
            if record.selected_action not in record.legal_actions:
                raise ReplayReconstructionError(
                    f"decision {index}: saved response is not a legal visible action",
                    code="illegal_visible_action")
            try:
                audit_decision_visibility(record)
            except VisibilityViolation as exc:
                raise ReplayReconstructionError(
                    f"decision {index}: player-visible action audit failed: {exc}",
                    code="visibility_audit_failed") from exc
        return ReconstructedLegacyDuel(source_sha256, embedded_sha256,
                                       tuple(records), len(replay.responses),
                                       decision.winner, decision.observation,
                                       engine.replay_manifest())
    finally:
        engine.close()
