"""Synthetic legacy-response playback; no real human replay compatibility claim."""

import os
import struct
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.engine.ocgcore_probe import GOAT_FLAGS, OcgcoreProbe
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.replay.edopro_container import (
    DUEL_FLAG_64BIT,
    EXTENDED_HEADER,
    HEADER,
    NEW_REPLAY,
    YRP1,
    parse_edopro_container,
)
from goat_ai.replay.edopro_reconstruct import (
    ReplayReconstructionError,
    reconstruct_legacy_responses,
)


def _legacy_replay(responses: list[bytes], *, settings=(8000, 5, 1),
                   rule_cards=(), extended=True):
    names = (struct.pack("<I", 1) + b"\x00" * 40) * 2
    payload = names + struct.pack("<IIIQ", *settings, GOAT_FLAGS)
    for _ in range(2):
        payload += struct.pack("<I", len(VANILLA_DECK))
        payload += struct.pack(f"<{len(VANILLA_DECK)}I", *VANILLA_DECK)
        payload += struct.pack("<I", 0)
    payload += struct.pack("<I", len(rule_cards))
    payload += struct.pack(f"<{len(rule_cards)}I", *rule_cards)
    payload += b"".join(bytes((len(response),)) + response for response in responses)
    payload += b"\x00"
    flags = NEW_REPLAY | DUEL_FLAG_64BIT | (EXTENDED_HEADER if extended else 0)
    header = HEADER.pack(YRP1, 1, flags, 12345, len(payload), 0, b"\x00" * 8)
    if extended:
        header += struct.pack("<5Q", 1, 43, 44, 45, 46)
    return parse_edopro_container(header + payload)


@pytest.fixture
def native_legacy_responses():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    responses = []
    views = []
    with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                      root / "scripts") as probe:
        probe.first_replay_decision((43, 44, 45, 46), VANILLA_DECK, VANILLA_DECK)
        for _ in range(1000):
            prompt = probe.decode_pending()
            views.append(probe.observation(prompt.player))
            value = prompt.choices[0].response
            response = (struct.pack("<I", value & 0xffffffff)
                        if isinstance(value, int) else value)
            responses.append(response)
            if probe.respond(value).terminal:
                break
        else:
            pytest.fail("source duel exceeded decision bound")
    return root, responses, views


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reconstructs_complete_native_legacy_response_trace(native_legacy_responses):
    root, responses, views = native_legacy_responses
    replay = _legacy_replay(responses)
    trace = reconstruct_legacy_responses(replay, root)
    assert len(trace.decisions) == len(responses) == len(views)
    # The public adapter adds an attacker-slot hint to the raw native view
    # during attack-target responses; all other visible fields must match.
    assert tuple(replace(record.observation, pending_attack=None)
                 for record in trace.decisions) == tuple(views)
    assert all(record.selected_action in record.legal_actions
               for record in trace.decisions)
    assert all(card.code is None
               for record in trace.decisions
               for card in record.observation.field
               if card.controller != record.observation.viewer
               and card.position == "facedown")
    assert trace.winner in (0, 1)
    assert trace.terminal_observation.life_points[trace.winner] > 0
    assert trace.replay_sha256 == replay.sha256
    assert "build/libocgcore.so" in trace.asset_sha256


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reconstruction_rejects_divergent_and_incomplete_responses(native_legacy_responses):
    root, responses, _ = native_legacy_responses
    changed = responses.copy()
    changed[0] = b"\x7f" * 4
    with pytest.raises(ReplayReconstructionError, match="response 0"):
        reconstruct_legacy_responses(_legacy_replay(changed), root)
    with pytest.raises(ReplayReconstructionError, match="before native terminal"):
        reconstruct_legacy_responses(_legacy_replay(responses[:-1]), root)


def test_reconstruction_rejects_non_goat_or_unreproducible_startup():
    replay = _legacy_replay([b"\xff" * 4])
    bad = [
        _legacy_replay([b"\xff" * 4], settings=(4000, 5, 1)),
        _legacy_replay([b"\xff" * 4], rule_cards=(123,)),
        _legacy_replay([b"\xff" * 4], extended=False),
        replace(replay, duel_flags=0),
    ]
    for item in bad:
        with pytest.raises(ReplayReconstructionError, match="startup"):
            reconstruct_legacy_responses(item, ".cache/goat-ai")
