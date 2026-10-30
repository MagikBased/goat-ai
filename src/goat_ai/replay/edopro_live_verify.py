"""Verify a local EDOPro room's review record against its original replay."""

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
    training-admission decision. It detects altered or mismatched local files.
    """
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    if (metadata.get("source") != "edopro_external_unpatched"
            or metadata.get("training_admitted") is not False
            or metadata.get("mirror_complete") is not True):
        raise ValueError("metadata is not a complete, excluded EDOPro room recording")
    replay = read_edopro_container(replay_path)
    embedded = replay.embedded_legacy_replay()
    if embedded is None or embedded.header.seed_words is None:
        raise ValueError("EDOPro replay has no embedded seed and responses")
    if metadata.get("core_seed") != list(embedded.header.seed_words):
        raise ValueError("metadata core seed differs from replay")
    reconstructed = reconstruct_legacy_responses(
        replay, native_root, historical_patches=False)
    trajectory = read_trajectory(review_path)
    if (trajectory.source != "edopro_external_unpatched"
            or trajectory.ruleset != "goat_external_unverified"
            or trajectory.schema_version != 28
            or trajectory.decks != tuple(metadata.get("names", ()))
            or trajectory.seed != metadata.get("seed")
            or trajectory.winner != reconstructed.winner
            or trajectory.winner != metadata.get("winner_team")
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
        "external_unpatched_comparison_only": True,
        "training_admitted": False,
    }
