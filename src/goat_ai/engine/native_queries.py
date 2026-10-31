"""Decode only the ocgcore query fields needed for player-visible views."""

import struct
from dataclasses import dataclass
from functools import lru_cache

QUERY_CODE = 0x1
QUERY_POSITION = 0x2
QUERY_ATTRIBUTE = 0x40
QUERY_RACE = 0x80
QUERY_ATTACK = 0x100
QUERY_DEFENSE = 0x200
QUERY_EQUIP_CARD = 0x4000
QUERY_COUNTERS = 0x20000
QUERY_OWNER = 0x40000
QUERY_IS_PUBLIC = 0x100000
QUERY_END = 0x80000000
MONSTER_FIELD_SLOTS = 7  # Pinned API-11 player.list_mzone layout.
SPELL_FIELD_SLOTS = 8  # Pinned API-11 player.list_szone layout.


@dataclass(frozen=True)
class QueriedCard:
    code: int
    position: int
    is_public: bool
    attack: int | None = None
    defense: int | None = None
    counters: tuple[tuple[int, int], ...] = ()
    equip_target: tuple[int, int, int] | None = None  # controller, location, sequence
    race: int | None = None  # Current Type mask; public only for face-up monsters.
    owner: int | None = None
    attribute: int | None = None  # Current Attribute mask; public for face-up monsters.


@dataclass(frozen=True)
class FieldSummary:
    """Public counts and field occupancy from one pinned OCG_DuelQueryField call."""

    life_points: tuple[int, int]
    monster_occupied: tuple[tuple[bool, ...], tuple[bool, ...]]
    spell_occupied: tuple[tuple[bool, ...], tuple[bool, ...]]
    deck_counts: tuple[int, int]
    hand_counts: tuple[int, int]
    grave_counts: tuple[int, int]
    banished_counts: tuple[int, int]
    extra_counts: tuple[int, int]


def decode_field_summary(buffer: bytes) -> FieldSummary:
    """Parse the public part of the pinned API-11 field query.

    The trailing chain payload is handled through native messages elsewhere.
    """
    if len(buffer) < 4:
        raise ValueError("truncated field query options")
    offset = 4
    life_points = []
    monster_occupied = []
    spell_occupied = []
    counts = []
    for _ in (0, 1):
        if offset + 4 > len(buffer):
            raise ValueError("truncated field query life points")
        life_points.append(struct.unpack_from("<I", buffer, offset)[0])
        offset += 4
        zones = []
        for size in (MONSTER_FIELD_SLOTS, SPELL_FIELD_SLOTS):
            occupied_slots = []
            for _ in range(size):
                if offset >= len(buffer):
                    raise ValueError("truncated field query zone")
                occupied = buffer[offset]
                if occupied not in (0, 1):
                    raise ValueError("invalid field query occupancy")
                offset += 6 if occupied else 1  # Occupancy, position, overlay count.
                if offset > len(buffer):
                    raise ValueError("truncated field query occupied zone")
                occupied_slots.append(bool(occupied))
            zones.append(tuple(occupied_slots))
        monster_occupied.append(zones[0])
        spell_occupied.append(zones[1])
        if offset + 24 > len(buffer):
            raise ValueError("truncated field query counts")
        counts.append(struct.unpack_from("<6I", buffer, offset))
        offset += 24
    if offset + 4 > len(buffer):
        raise ValueError("truncated field query chain count")
    return FieldSummary(
        tuple(life_points), tuple(monster_occupied), tuple(spell_occupied),
        tuple(player[0] for player in counts), tuple(player[1] for player in counts),
        tuple(player[2] for player in counts), tuple(player[3] for player in counts),
        tuple(player[4] for player in counts),
    )


@lru_cache(maxsize=4096)
def decode_location(buffer: bytes) -> tuple[QueriedCard | None, ...]:
    """Parse an API-11 location frame; identical native bytes have identical views."""
    if len(buffer) < 4:
        raise ValueError("truncated query-location header")
    size = struct.unpack_from("<I", buffer)[0]
    if size != len(buffer) - 4:
        raise ValueError("query-location size mismatch")
    cards = []
    offset = 4
    while offset < len(buffer):
        if offset + 2 > len(buffer):
            raise ValueError("truncated card query length")
        length = struct.unpack_from("<H", buffer, offset)[0]
        if length == 0:
            cards.append(None)
            offset += 2
            continue
        values: dict[int, int] = {}
        counters: tuple[tuple[int, int], ...] = ()
        equip_target: tuple[int, int, int] | None = None
        while True:
            if offset + 2 > len(buffer):
                raise ValueError("truncated card query record")
            length = struct.unpack_from("<H", buffer, offset)[0]
            offset += 2
            if length < 4 or offset + length > len(buffer):
                raise ValueError("invalid card query record length")
            flag = struct.unpack_from("<I", buffer, offset)[0]
            payload = buffer[offset + 4:offset + length]
            offset += length
            if flag == QUERY_END:
                if payload:
                    raise ValueError("QUERY_END has payload")
                break
            if flag in values:
                raise ValueError("duplicate query flag")
            if flag in (QUERY_CODE, QUERY_POSITION, QUERY_ATTRIBUTE,
                        QUERY_ATTACK, QUERY_DEFENSE):
                if len(payload) != 4:
                    raise ValueError("invalid query uint32")
                values[flag] = struct.unpack("<i" if flag in (QUERY_ATTACK, QUERY_DEFENSE)
                                             else "<I", payload)[0]
            elif flag == QUERY_RACE:
                if len(payload) != 8:
                    raise ValueError("invalid race query uint64")
                values[flag] = struct.unpack("<Q", payload)[0]
            elif flag == QUERY_COUNTERS:
                if len(payload) < 4:
                    raise ValueError("invalid counter query")
                count = struct.unpack_from("<I", payload)[0]
                if len(payload) != 4 + count * 4:
                    raise ValueError("counter query length mismatch")
                counters = tuple(sorted((packed & 0xFFFF, packed >> 16)
                                        for packed in struct.unpack_from(
                                            f"<{count}I", payload, 4)))
                values[flag] = count
            elif flag == QUERY_IS_PUBLIC:
                if len(payload) != 1:
                    raise ValueError("invalid public query flag")
                values[flag] = payload[0]
            elif flag == QUERY_OWNER:
                if len(payload) != 1 or payload[0] not in (0, 1):
                    raise ValueError("invalid owner query flag")
                values[flag] = payload[0]
            elif flag == QUERY_EQUIP_CARD:
                if len(payload) != 10:
                    raise ValueError("invalid equip target query")
                controller, location, sequence, _position = struct.unpack("<BBII", payload)
                if location:
                    equip_target = (controller, location, sequence)
                values[flag] = 1
            else:
                raise ValueError(f"unexpected query flag {flag:#x}")
        if QUERY_CODE not in values or QUERY_POSITION not in values:
            raise ValueError("card query omits code or position")
        cards.append(QueriedCard(values[QUERY_CODE], values[QUERY_POSITION],
                                 bool(values.get(QUERY_IS_PUBLIC, 0)),
                                 values.get(QUERY_ATTACK), values.get(QUERY_DEFENSE),
                                 counters, equip_target, values.get(QUERY_RACE),
                                 values.get(QUERY_OWNER), values.get(QUERY_ATTRIBUTE)))
    return tuple(cards)


def decode_life_points(buffer: bytes, monster_slots: tuple[int, int],
                       spell_slots: tuple[int, int]) -> tuple[int, int]:
    """Read only LP from the pinned GOAT query-field layout."""
    if len(buffer) < 8:
        raise ValueError("truncated field query")
    offset = 4  # duel options; full 64-bit flags are not included here
    life_points = []
    for player in (0, 1):
        if offset + 4 > len(buffer):
            raise ValueError("truncated player life points")
        life_points.append(struct.unpack_from("<I", buffer, offset)[0])
        offset += 4
        for _ in range(monster_slots[player] + spell_slots[player]):
            if offset >= len(buffer):
                raise ValueError("truncated field zone")
            occupied = buffer[offset]
            offset += 1
            if occupied:
                offset += 5  # position and overlay count
        offset += 6 * 4  # deck, hand, grave, banished, extra, faceup-extra counts
    if offset > len(buffer):
        raise ValueError("truncated field query counts")
    return tuple(life_points)
