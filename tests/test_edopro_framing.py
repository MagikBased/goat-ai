"""EDOPro room framing; these tests do not claim a working client."""

import pytest

from goat_ai.edopro.framing import MAX_PACKET_BYTES, RoomPacket, RoomPacketDecoder, frame_packet


def test_room_frame_matches_windbot_binary_client_header() -> None:
    assert frame_packet(0x10, b"abc") == b"\x04\x00\x10abc"
    assert frame_packet(0x01) == b"\x01\x00\x01"


def test_room_decoder_handles_fragmented_and_concatenated_packets() -> None:
    first = frame_packet(0x15, b"start")
    second = frame_packet(0x01, b"\x01\x02")
    decoder = RoomPacketDecoder()
    assert decoder.feed(first[:1]) == ()
    assert decoder.feed(first[1:4]) == ()
    assert decoder.feed(first[4:] + second + b"\x01") == (
        RoomPacket(0x15, b"start"), RoomPacket(0x01, b"\x01\x02"))
    assert decoder.feed(b"\x00\x16") == (RoomPacket(0x16, b""),)
    decoder.finish()


def test_room_framing_rejects_invalid_and_truncated_frames() -> None:
    with pytest.raises(ValueError, match="kind"):
        frame_packet(256)
    with pytest.raises(ValueError, match="limit"):
        frame_packet(0x01, bytes(MAX_PACKET_BYTES))
    decoder = RoomPacketDecoder()
    with pytest.raises(ValueError, match="type byte"):
        decoder.feed(b"\x00\x00")
    assert decoder.feed(b"\x04\x00\x10ab") == ()
    with pytest.raises(ValueError, match="truncated"):
        decoder.finish()
