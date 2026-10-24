"""Strict decoding of selected ocgcore API-11 decision messages.

These are internal protocol values. They must not be handed to an agent until
the observation and action visibility boundary is audited.
"""

import struct
from dataclasses import dataclass
from itertools import combinations
from math import comb

from goat_ai.engine.ocgcore_probe import MSG_SELECT_CHAIN, MSG_SELECT_IDLECMD


@dataclass(frozen=True)
class NativeChoice:
    kind: str
    response: int | bytes
    code: int | None = None
    controller: int | None = None
    location: int | None = None
    sequence: int | None = None
    cards: tuple[tuple[int, int, int, int], ...] = ()
    position: int | None = None
    race: int | None = None


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
    """Decode supported native choices; fail on every other request type."""
    reader = _Reader(message)
    kind = reader.integer(1)
    if kind == 13:  # MSG_SELECT_YESNO
        player = reader.integer(1)
        reader.integer(8)  # prompt description; not yet exposed to the agent
        reader.finish()
        if player not in (0, 1):
            raise ValueError("invalid yes/no player")
        return NativeDecision(player, (NativeChoice("no", 0), NativeChoice("yes", 1)))
    if kind == 19:  # MSG_SELECT_POSITION
        player = reader.integer(1)
        reader.integer(4)  # card identity is not needed to choose a position
        mask = reader.integer(1)
        reader.finish()
        if player not in (0, 1) or not mask or mask & ~0xF:
            raise ValueError("invalid position selection")
        choices = tuple(NativeChoice("select_position", position, position=position)
                        for position in (1, 2, 4, 8) if mask & position)
        return NativeDecision(player, choices)
    if kind == 140:  # MSG_ANNOUNCE_RACE
        player = reader.integer(1)
        count = reader.integer(1)
        available = reader.integer(8)
        reader.finish()
        bits = tuple(1 << index for index in range(64) if available & (1 << index))
        if player not in (0, 1) or not 1 <= count <= len(bits) or comb(len(bits), count) > 2048:
            raise NotImplementedError("race announcement bounds are not supported")
        choices = tuple(NativeChoice("announce_race", struct.pack("<Q", mask), race=mask)
                        for group in combinations(bits, count)
                        for mask in (sum(group),))
        return NativeDecision(player, choices)
    if kind == 20:  # MSG_SELECT_TRIBUTE
        player = reader.integer(1)
        cancelable = reader.integer(1)
        minimum = reader.integer(4)
        maximum = reader.integer(4)
        count = reader.integer(4)
        if player not in (0, 1) or maximum > 5 or count > 32:
            raise NotImplementedError("tribute selection bounds are not supported")
        cards = []
        for _ in range(count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(4)
            weight = reader.integer(1)
            cards.append((code, controller, location, sequence, weight))
        reader.finish()
        if sum(comb(count, size) for size in range(min(count, maximum) + 1)) > 2048:
            raise NotImplementedError("tribute selection has too many combinations")
        choices = []
        for size in range(min(count, maximum) + 1):
            for indices in combinations(range(count), size):
                if sum(cards[index][4] for index in indices) < minimum:
                    continue
                response = struct.pack("<II", 0, size) + struct.pack(f"<{size}I", *indices)
                selected = tuple(cards[index][:4] for index in indices)
                if size == 1:
                    code, controller, location, sequence = selected[0]
                    choices.append(NativeChoice("tribute", response, code, controller,
                                                location, sequence))
                else:
                    choices.append(NativeChoice("tribute_cards", response, cards=selected))
        if cancelable:
            choices.append(NativeChoice("cancel", -1))
        if not choices:
            raise ValueError("empty tribute selection")
        return NativeDecision(player, tuple(choices))
    if kind == MSG_SELECT_CHAIN:
        player = reader.integer(1)
        reader.integer(1)  # special count, independent from normal option count
        forced = reader.integer(1)
        reader.integer(8)  # timing hints
        count = reader.integer(4)
        choices = []
        for index in range(count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(4)
            reader.integer(4)  # position
            reader.integer(8)  # effect description
            reader.integer(1)  # response flag
            choices.append(NativeChoice("chain", index, code, controller,
                                        location, sequence))
        if not forced:
            choices.append(NativeChoice("pass", -1))
        reader.finish()
        if not choices:
            raise ValueError("forced chain has no legal choices")
        return NativeDecision(player, tuple(choices))
    if kind == 15:  # MSG_SELECT_CARD
        player = reader.integer(1)
        cancelable = reader.integer(1)
        minimum = reader.integer(4)
        maximum = reader.integer(4)
        count = reader.integer(4)
        if not count or minimum > maximum or maximum > count:
            raise NotImplementedError(
                f"card selection mode not decoded: cancelable={cancelable} "
                f"minimum={minimum} maximum={maximum} count={count}")
        cards = []
        for index in range(count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(4)
            reader.integer(4)  # position
            cards.append((code, controller, location, sequence))
        option_count = sum(comb(count, size) for size in range(minimum, maximum + 1))
        if option_count > 2048:
            raise NotImplementedError(f"card selection has {option_count} combinations")
        choices = []
        for size in range(minimum, maximum + 1):
            for indices in combinations(range(count), size):
                # Response type 0: size then uint32 card indices.
                response = struct.pack("<II", 0, size) + struct.pack(f"<{size}I", *indices)
                selected = tuple(cards[index] for index in indices)
                if size == 1:
                    code, controller, location, sequence = selected[0]
                    choices.append(NativeChoice("select_card", response, code,
                                                controller, location, sequence))
                else:
                    choices.append(NativeChoice("select_cards", response, cards=selected))
        if cancelable:
            choices.append(NativeChoice("cancel", -1))
        reader.finish()
        return NativeDecision(player, tuple(choices))
    if kind == 26:  # MSG_SELECT_UNSELECT_CARD
        player = reader.integer(1)
        finishable = reader.integer(1)
        cancelable = reader.integer(1)
        reader.integer(4)  # minimum cards in the completed selection
        reader.integer(4)  # maximum cards in the completed selection
        choices = []
        count = reader.integer(4)
        for index in range(count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(4)
            reader.integer(4)  # position
            choices.append(NativeChoice("select_card", struct.pack("<II", 1, index),
                                        code, controller, location, sequence))
        unselect_count = reader.integer(4)
        for index in range(unselect_count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(4)
            reader.integer(4)  # position
            choices.append(NativeChoice("unselect_card",
                                        struct.pack("<II", 1, count + index),
                                        code, controller, location, sequence))
        if finishable:
            choices.append(NativeChoice("finish_selection", -1))
        elif cancelable:
            choices.append(NativeChoice("cancel", -1))
        reader.finish()
        if not choices:
            raise ValueError("empty select/unselect decision")
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
    if kind == 10:  # MSG_SELECT_BATTLECMD
        player = reader.integer(1)
        choices = []
        activate_count = reader.integer(4)
        for index in range(activate_count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(4)
            reader.integer(8)  # effect description
            reader.integer(1)  # response flag
            choices.append(NativeChoice("activate", index << 16, code, controller,
                                        location, sequence))
        attack_count = reader.integer(4)
        for index in range(attack_count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(1)
            reader.integer(1)  # direct-attack flag
            choices.append(NativeChoice("attack", (index << 16) | 1, code,
                                        controller, location, sequence))
        if reader.integer(1):
            choices.append(NativeChoice("main2", 2))
        if reader.integer(1):
            choices.append(NativeChoice("end_phase", 3))
        reader.finish()
        if not choices:
            raise ValueError("empty battle command")
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
    if reader.integer(1):
        choices.append(NativeChoice("shuffle_hand", 8))
    reader.finish()
    if player not in (0, 1) or not choices:
        raise ValueError("invalid or empty idle decision")
    return NativeDecision(player, tuple(choices))
