"""Strict decoding of selected ocgcore API-11 decision messages.

These are internal protocol values. They must not be handed to an agent until
the observation and action visibility boundary is audited.
"""

import struct
from dataclasses import dataclass

from goat_ai.engine.ocgcore_probe import MSG_SELECT_CHAIN, MSG_SELECT_IDLECMD


@dataclass(frozen=True)
class NativeChoice:
    kind: str
    response: int | bytes
    code: int | None = None
    controller: int | None = None
    location: int | None = None
    sequence: int | None = None


@dataclass(frozen=True)
class NativeDecision:
    player: int
    choices: tuple[NativeChoice, ...]


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def integer(self, width: int) -> int:
        if self.offset + width > len(self.data):
            raise ValueError("truncated native decision")
        value = int.from_bytes(self.data[self.offset:self.offset + width], "little")
        self.offset += width
        return value

    def finish(self) -> None:
        if self.offset != len(self.data):
            raise ValueError("trailing bytes in native decision")


def decode_decision(message: bytes) -> NativeDecision:
    """Decode chain and idle choices; fail on every other request type."""
    reader = _Reader(message)
    kind = reader.integer(1)
    if kind == MSG_SELECT_CHAIN:
        player = reader.integer(1)
        reader.integer(1)  # special count, independent from normal option count
        forced = reader.integer(1)
        reader.integer(8)  # timing hints
        count = reader.integer(4)
        if count or forced:
            raise NotImplementedError("nonempty or forced chain choices are not decoded")
        reader.finish()
        return NativeDecision(player, (NativeChoice("pass", -1),))
    if kind == 15:  # MSG_SELECT_CARD
        player = reader.integer(1)
        reader.integer(1)  # cancelable
        minimum = reader.integer(4)
        maximum = reader.integer(4)
        count = reader.integer(4)
        if minimum != 1 or maximum != 1 or not count:
            raise NotImplementedError("multi-card selection is not decoded")
        choices = []
        for index in range(count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(4)
            reader.integer(4)  # position
            # Response type 0: size then uint32 card indices.
            choices.append(NativeChoice("select_card", struct.pack("<III", 0, 1, index),
                                        code, controller, location, sequence))
        reader.finish()
        return NativeDecision(player, tuple(choices))
    if kind == 18:  # MSG_SELECT_PLACE
        player = reader.integer(1)
        count = reader.integer(1)
        forbidden = reader.integer(4)
        reader.finish()
        if count != 1:
            raise NotImplementedError("multi-place selection is not decoded")
        choices = []
        for group in range(4):
            controller = player if group < 2 else 1 - player
            location = 0x4 if group % 2 == 0 else 0x8
            for sequence in range(8):
                if not forbidden & (1 << (group * 8 + sequence)):
                    choices.append(NativeChoice("place", bytes((controller, location, sequence)),
                                                controller=controller, location=location,
                                                sequence=sequence))
        if not choices:
            raise ValueError("no legal place in MSG_SELECT_PLACE")
        return NativeDecision(player, tuple(choices))
    if kind != MSG_SELECT_IDLECMD:
        raise NotImplementedError(f"native decision message {kind} is not decoded")

    player = reader.integer(1)
    choices = []
    groups = (
        ("normal_summon", 0, 4, False),
        ("special_summon", 1, 4, False),
        ("change_position", 2, 1, False),
        ("set_monster", 3, 4, False),
        ("set_spell_trap", 4, 4, False),
        ("activate", 5, 4, True),
    )
    for action_kind, command, sequence_width, has_effect in groups:
        count = reader.integer(4)
        for index in range(count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(sequence_width)
            if has_effect:
                reader.integer(8)  # effect description
                reader.integer(1)  # response flag
            choices.append(NativeChoice(action_kind, (index << 16) | command,
                                        code, controller, location, sequence))
    if reader.integer(1):
        choices.append(NativeChoice("battle_phase", 6))
    if reader.integer(1):
        choices.append(NativeChoice("end_phase", 7))
    reader.integer(1)  # can shuffle hand; no action exposed yet
    reader.finish()
    if player not in (0, 1) or not choices:
        raise ValueError("invalid or empty idle decision")
    return NativeDecision(player, tuple(choices))
