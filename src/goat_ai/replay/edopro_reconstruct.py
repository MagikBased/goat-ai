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
from goat_ai.observations import Observation
from goat_ai.replay.edopro_container import (
    HAND_TEST,
    SINGLE_MODE,
    TAG,
    EdoReplayContainer,
)
from goat_ai.replay.trajectory import DecisionRecord


class ReplayReconstructionError(ValueError):
    """Replay inputs or a saved response diverged from this native adapter."""


@dataclass(frozen=True)
class ReconstructedLegacyDuel:
    replay_sha256: str
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
    settings = replay.settings
    if (replay.header.format != "yrp" or replay.header.flags & (TAG | SINGLE_MODE | HAND_TEST)
            or replay.player_count != 2 or len(replay.decks) != 2
            or replay.duel_flags != GOAT_FLAGS
            or settings is None
            or (settings.starting_life_points, settings.opening_hand_size,
                settings.draw_count) != (8000, 5, 1)
            or replay.header.seed_words is None or not any(replay.header.seed_words)
            or replay.rule_cards):
        raise ReplayReconstructionError("replay startup is outside supported GOAT profile")
    if not replay.responses or len(replay.responses) > max_responses:
        raise ReplayReconstructionError("replay response count outside reconstruction bound")

    engine = ExperimentalOcgcoreEngine(native_root)
    records: list[DecisionRecord] = []
    try:
        deck1, deck2 = (Decklist(deck.main, deck.extra) for deck in replay.decks)
        try:
            decision = engine.reset_recorded(replay.header.seed_words, deck1, deck2)
        except (ValueError, RuntimeError) as exc:
            raise ReplayReconstructionError(f"native replay startup failed: {exc}") from exc
        for index, response in enumerate(replay.responses):
            if decision.terminal:
                raise ReplayReconstructionError(
                    f"response {index}: native duel ended before saved responses")
            try:
                action = engine.action_for_recorded_response(response)
            except ValueError as exc:
                native = engine.probe.decode_pending()
                selection = native.card_selection or native.sum_selection
                if selection is None or not selection.accepts(response):
                    raise ReplayReconstructionError(
                        f"response {index}: saved bytes do not map to one legal action") from exc
                if len(response) < 8:
                    raise ReplayReconstructionError(f"response {index}: truncated selection")
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
                            f"response {index}: staged selection diverged: {stage_exc}") from stage_exc
                if engine.recorded_selection_in_progress():
                    try:
                        action = engine.action_for_recorded_response(response)
                        if action.kind != "finish_selection":
                            raise ValueError("selection did not reach a finish action")
                        records.append(DecisionRecord(decision.observation,
                                                      decision.legal_actions, action))
                        decision = engine.step(action)
                    except (ValueError, RuntimeError) as stage_exc:
                        raise ReplayReconstructionError(
                            f"response {index}: selection finish diverged: {stage_exc}") from stage_exc
                continue
            records.append(DecisionRecord(decision.observation,
                                          decision.legal_actions, action))
            try:
                decision = engine.step(action)
            except (ValueError, RuntimeError) as exc:
                raise ReplayReconstructionError(
                    f"response {index}: native transition failed: {exc}") from exc
        if not decision.terminal:
            raise ReplayReconstructionError("saved responses ended before native terminal state")
        return ReconstructedLegacyDuel(replay.sha256, tuple(records), len(replay.responses),
                                       decision.winner, decision.observation,
                                       engine.replay_manifest())
    finally:
        engine.close()
