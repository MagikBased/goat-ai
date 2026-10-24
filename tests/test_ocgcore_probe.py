import os
import struct
from pathlib import Path

import pytest

from goat_ai.engine.ocgcore_probe import (
    GOAT_FLAGS,
    MSG_DRAW,
    MSG_SELECT_CHAIN,
    OcgcoreProbe,
    split_messages,
)
from goat_ai.engine.probe_deck import VANILLA_DECK


def test_message_frame_parser():
    frame = struct.pack("<I", 2) + b"\x5a\x01"
    assert split_messages(frame + frame) == (b"\x5a\x01", b"\x5a\x01")
    with pytest.raises(ValueError, match="truncated"):
        split_messages(b"\x01")
    with pytest.raises(ValueError, match="invalid"):
        split_messages(struct.pack("<I", 10) + b"\x5a")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_real_goat_mode_first_draw_and_determinism():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])

    def run():
        with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                          root / "scripts") as probe:
            return probe.first_decision(42, VANILLA_DECK)

    first = run()
    assert first == run()
    assert first.flags == GOAT_FLAGS
    assert first.core_version == (11, 0)
    assert first.hand_counts == (6, 5)
    assert first.deck_counts == (34, 35)
    assert MSG_DRAW in first.message_ids
    assert first.draw_events == ((0, 5), (1, 5), (0, 1))
    assert first.decision_message_id == MSG_SELECT_CHAIN
    assert first.decision_player == 0

