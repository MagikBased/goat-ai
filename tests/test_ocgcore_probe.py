import os
import struct
from pathlib import Path

import pytest

from goat_ai.engine.native_messages import decode_decision
from goat_ai.engine.ocgcore_probe import (
    GOAT_FLAGS,
    MSG_DRAW,
    MSG_SELECT_CHAIN,
    OcgcoreProbe,
    split_messages,
)
from goat_ai.engine.probe_deck import VANILLA_DECK
from scripts.run_native_smoke import run


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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_real_vanilla_duel_to_terminal():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    result = run(root, 42)
    assert result["decisions"] == 350
    assert result["winner"] == 1
    assert result == run(root, 42)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_first_idle_actions_and_illegal_response():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                      root / "scripts") as probe:
        probe.first_decision(42, VANILLA_DECK)
        with pytest.raises(ValueError, match="illegal"):
            probe.respond(100)
        probe.pass_empty_chain()
        probe.pass_empty_chain()
        decision = decode_decision(probe._pending_message)
        assert decision.player == 0
        assert {choice.kind for choice in decision.choices} == {
            "normal_summon", "set_monster", "end_phase", "shuffle_hand",
        }
        assert len(decision.choices) == 14


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_opening_hand_is_seeded_and_shuffled():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])

    def hand(seed):
        with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                          root / "scripts") as probe:
            probe.first_decision(seed, VANILLA_DECK)
            return tuple(card.code for card in probe.observation(0).hand)

    assert hand(42) == hand(42)
    assert hand(42) != hand(43)

