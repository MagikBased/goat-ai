"""Decode only the ocgcore query fields needed for player-visible views."""

import struct
from dataclasses import dataclass

QUERY_CODE = 0x1
QUERY_POSITION = 0x2
QUERY_IS_PUBLIC = 0x100000
QUERY_END = 0x80000000


@dataclass(frozen=True)
class QueriedCard:
    code: int
    position: int
    is_public: bool


def decode_location(buffer: bytes) -> tuple[QueriedCard | None, ...]:
    """Parse API-11 QUERY_CODE | QUERY_POSITION frames for one location."""
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
            if flag in (QUERY_CODE, QUERY_POSITION):
                if len(payload) != 4:
                    raise ValueError("invalid query uint32")
                values[flag] = struct.unpack("<I", payload)[0]
            elif flag == QUERY_IS_PUBLIC:
                if len(payload) != 1:
                    raise ValueError("invalid public query flag")
                values[flag] = payload[0]
            else:
                raise ValueError(f"unexpected query flag {flag:#x}")
        if QUERY_CODE not in values or QUERY_POSITION not in values:
            raise ValueError("card query omits code or position")
        cards.append(QueriedCard(values[QUERY_CODE], values[QUERY_POSITION],
                                 bool(values.get(QUERY_IS_PUBLIC, 0))))
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
