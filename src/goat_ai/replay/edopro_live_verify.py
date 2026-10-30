"""Verify a complete or interrupted EDOPro room record against its replay."""

import json
from pathlib import Path

from goat_ai.replay.edopro_container import read_edopro_container
from goat_ai.replay.edopro_reconstruct import reconstruct_legacy_responses
from goat_ai.replay.trajectory import read_trajectory


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
    reconstructed = reconstruct_legacy_responses(
        replay, native_root, historical_patches=historical,
        allow_incomplete=prefix)
    trajectory = read_trajectory(review_path)
    status = (trajectory.skill_metadata or {}).get("recording_status")
    if (trajectory.source != (base_source if complete else base_source + "_partial")
            or trajectory.ruleset != ruleset
            or trajectory.schema_version != 28
            or (status not in (None, "complete") if complete
                else status != "interrupted")
            or trajectory.decks != tuple(metadata.get("names", ()))
            or trajectory.seed != metadata.get("seed")
            or reconstructed.native_terminal is not complete
            or trajectory.winner != reconstructed.winner
            or complete and trajectory.winner != metadata.get("winner_team")
            or trajectory.decisions != reconstructed.decisions
            or trajectory.terminal_observation != reconstructed.terminal_observation
            or metadata.get("host_responses") != reconstructed.saved_response_count
            or metadata.get("mirror_responses") != reconstructed.saved_response_count
            or metadata.get("retries") != 0
            or metadata.get("lua_errors") != []):
        raise ValueError("EDOPro review trajectory or metadata differs from replay")
    return {
        "replay_sha256": replay.sha256,
        "responses": reconstructed.saved_response_count,
        "visible_decisions": len(reconstructed.decisions),
        "winner_team": reconstructed.winner,
        "complete": complete,
        "reviewable_prefix": prefix,
        "historical_patches": historical,
        "historical_goat_certified": False,
        "training_admitted": False,
    }
