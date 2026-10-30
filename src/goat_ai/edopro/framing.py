"""Bounded framing for EDOPro room packets.

Project Ignis WindBot's YGOSharp.Network BinaryClient uses an unsigned
little-endian two-byte payload length, excluding the header. The first byte
of each payload is the client-to-server or server-to-client packet type.
This module handles framing only, not a duel protocol or training intake.
"""

from dataclasses import dataclass


MAX_PACKET_BYTES = 0xFFFF


@dataclass(frozen=True)
class RoomPacket:
    kind: int
    body: bytes


def frame_packet(kind: int, body: bytes = b"") -> bytes:
    """Encode one room packet, excluding any transport-specific connection data."""
    if type(kind) is not int or not 0 <= kind <= 255:
        raise ValueError("room packet kind must be one byte")
    if not isinstance(body, bytes):
        raise TypeError("room packet body must be bytes")
    size = len(body) + 1
    if size > MAX_PACKET_BYTES:
        raise ValueError("room packet exceeds the 16-bit payload limit")
    return size.to_bytes(2, "little") + bytes((kind,)) + body


class RoomPacketDecoder:
    """Incrementally decode a TCP stream without assuming packet boundaries."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> tuple[RoomPacket, ...]:
        if not isinstance(data, bytes):
            raise TypeError("room packet input must be bytes")
        self._buffer.extend(data)
        packets: list[RoomPacket] = []
        while len(self._buffer) >= 2:
            size = int.from_bytes(self._buffer[:2], "little")
            if size == 0:
                self._buffer.clear()
                raise ValueError("room packet has no type byte")
            if len(self._buffer) < size + 2:
                break
            packets.append(RoomPacket(self._buffer[2], bytes(self._buffer[3:size + 2])))
            del self._buffer[:size + 2]
        return tuple(packets)

    def finish(self) -> None:
        """Reject a truncated packet when the connection has ended."""
        if self._buffer:
            raise ValueError("truncated room packet")

