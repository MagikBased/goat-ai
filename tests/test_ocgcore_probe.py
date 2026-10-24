import os
import struct
from pathlib import Path

import pytest

from goat_ai.engine.native_messages import decode_decision
from goat_ai.engine.ocgcore_probe import (
    GOAT_FLAGS,
    MSG_ATTACK,
    MSG_CONFIRM_CARDS,
    MSG_DAMAGE_STEP_END,
    MSG_DAMAGE_STEP_START,
    MSG_DRAW,
    MSG_FIELD_DISABLED,
    MSG_MOVE,
    MSG_POS_CHANGE,
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


def test_public_battle_events_update_observed_phase():
    probe = object.__new__(OcgcoreProbe)
    probe._turn = 0
    probe._phase = "unknown"
    probe._chain = []
    probe._public_history = []
    probe._known_facedown = {}
    probe._update_public_clock([b"\x29\x08\x00"])
    assert probe._phase == "battle_start"
    probe._update_public_clock([bytes((MSG_ATTACK,))])
    assert probe._phase == "battle_step"
    probe._update_public_clock([bytes((MSG_DAMAGE_STEP_START,))])
    assert probe._phase == "damage_step"
    probe._update_public_clock([bytes((MSG_DAMAGE_STEP_END,))])
    assert probe._phase == "battle_step"
    assert probe._public_history == ["phase:battle_start", "attack",
                                     "damage_step:start", "damage_step:end"]
    with pytest.raises(ValueError, match="MSG_DAMAGE_STEP_START"):
        probe._update_public_clock([bytes((MSG_DAMAGE_STEP_START, 0))])


def test_public_field_disabled_mask_replaces_previous_zones():
    probe = object.__new__(OcgcoreProbe)
    probe._turn = 1
    probe._phase = "main1"
    probe._chain = []
    probe._public_history = []
    probe._known_facedown = {}
    probe._disabled_zones = ()
    mask = (1 << 0) | (1 << 1) | (1 << (16 + 8 + 2))
    probe._update_public_clock([bytes((MSG_FIELD_DISABLED,)) + struct.pack("<I", mask)])
    assert {(slot.player, slot.zone, slot.sequence) for slot in probe._disabled_zones} == {
        (0, "monster", 0), (0, "monster", 1), (1, "spell_trap", 2)}
    probe._update_public_clock([bytes((MSG_FIELD_DISABLED,)) + struct.pack("<I", 0)])
    assert probe._disabled_zones == ()
    with pytest.raises(ValueError, match="MSG_FIELD_DISABLED"):
        probe._update_public_clock([bytes((MSG_FIELD_DISABLED, 1))])


def test_confirm_cards_preserves_recipient_and_discards_native_card_order():
    probe = object.__new__(OcgcoreProbe)
    probe._turn = 3
    probe._phase = "main1"
    probe._chain = []
    probe._public_history = []
    probe._known_facedown = {}
    probe._private_reveals = []
    message = (bytes((MSG_CONFIRM_CARDS, 0)) + struct.pack("<I", 2)
               + struct.pack("<IBBI", 200, 1, 1, 7)
               + struct.pack("<IBBI", 100, 1, 1, 2))
    probe._update_public_clock([message])
    reveal = probe._private_reveals[0]
    assert reveal.recipient == 0 and reveal.turn == 3
    assert [(card.code, card.controller, card.location) for card in reveal.cards] == [
        (100, 1, 1), (200, 1, 1)]
    with pytest.raises(ValueError, match="MSG_CONFIRM_CARDS"):
        probe._update_public_clock([message[:-1]])


def test_known_facedown_memory_requires_public_flip_and_clears_on_move():
    probe = object.__new__(OcgcoreProbe)
    probe._turn = 0
    probe._phase = "unknown"
    probe._chain = []
    probe._public_history = []
    probe._known_facedown = {}
    code = 12345678
    key = (1, 4, 2)
    probe._update_public_clock([bytes((MSG_POS_CHANGE,))
                                + struct.pack("<IBBBBB", code, 1, 4, 2, 8, 4)])
    assert probe._known_facedown == {}
    probe._update_public_clock([bytes((MSG_POS_CHANGE,))
                                + struct.pack("<IBBBBB", code, 1, 4, 2, 4, 8)])
    assert probe._known_facedown == {key: code}
    # MSG_MOVE contains the raw identity even for private moves. Only its public
    # old/new locations are used to invalidate memory.
    move = (bytes((MSG_MOVE,)) + struct.pack("<I", 99999999)
            + struct.pack("<BBII", 1, 4, 2, 8)
            + struct.pack("<BBII", 1, 16, 0, 1)
            + struct.pack("<I", 0))
    probe._update_public_clock([move])
    assert probe._known_facedown == {}


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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_pre_errata_card_metadata_and_script_load_at_startup():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = (511001039,) + VANILLA_DECK[1:]  # Dark Magician of Chaos (Pre-Errata)
    with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                      root / "scripts") as probe:
        probe.first_decision(42, deck)
        assert probe.errors == []
        assert probe._card_row(511001039, "alias, type") == (40737112, 33)

