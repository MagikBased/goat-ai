"""Source-layout replay container tests; no decision reconstruction claim."""

import lzma
import json
import struct
import sys

import pytest

from goat_ai.replay.edopro_container import (
    COMPRESSED,
    DUEL_FLAG_64BIT,
    EXTENDED_HEADER,
    HEADER,
    NEW_REPLAY,
    ReplayContainerError,
    YRP1,
    YRPX,
    parse_edopro_container,
)


def _name(value: str) -> bytes:
    return value.encode("utf-16-le").ljust(40, b"\x00")


def _container(magic: int, payload: bytes, *, compressed: bool = False,
               extended: bool = False) -> bytes:
    flags = NEW_REPLAY | DUEL_FLAG_64BIT
    props = b"\x00" * 8
    body = payload
    if compressed:
        flags |= COMPRESSED
        dictionary = 1 << 20
        filters = [{"id": lzma.FILTER_LZMA1, "dict_size": dictionary,
                    "lc": 3, "lp": 0, "pb": 2}]
        body = lzma.compress(payload, format=lzma.FORMAT_RAW, filters=filters)
        props = bytes((93,)) + dictionary.to_bytes(4, "little") + b"\x00" * 3
    if extended:
        flags |= EXTENDED_HEADER
    header = HEADER.pack(magic, 1, flags, 12345, len(payload), 0, props)
    if extended:
        header += struct.pack("<5Q", 1, 11, 12, 13, 14)
    return header + body


def _prefix(magic: int) -> bytes:
    names = (struct.pack("<I", 1) + _name("Private player A")
             + struct.pack("<I", 1) + _name("Private player B"))
    settings = struct.pack("<III", 8000, 5, 1) if magic == YRP1 else b""
    return names + settings + struct.pack("<Q", 34226374444)


def test_yrp1_reads_decks_and_responses_without_exporting_private_values():
    payload = (_prefix(YRP1) + struct.pack("<I2II", 2, 10, 20, 0)
               + struct.pack("<I3II", 3, 30, 40, 50, 0)
               + struct.pack("<I", 0)  # no custom rule cards
               + b"\x02\x01\x02\x01\xff\x00")
    replay = parse_edopro_container(_container(YRP1, payload, compressed=True,
                                                extended=True))
    assert replay.header.format == "yrp"
    assert replay.header.seed_words == (11, 12, 13, 14)
    assert replay.duel_flags == 34226374444
    assert replay.player_count == 2
    assert replay.decks[0].main == (10, 20)
    assert replay.decks[1].main == (30, 40, 50)
    assert replay.responses == (b"\x01\x02", b"\xff")
    summary = replay.summary()
    assert summary["decision_reconstruction"] == "not_implemented"
    assert summary["main_deck_counts"] == [2, 3]
    assert summary["response_count"] == 2
    assert "Private player" not in str(summary)
    assert "10, 20" not in str(summary)


def test_yrpx_reads_packet_stream_without_mislabeling_as_decisions():
    payload = (_prefix(YRPX) + bytes((40,)) + struct.pack("<I", 2) + b"AB"
               + bytes((41,)) + struct.pack("<I", 1) + b"C")
    replay = parse_edopro_container(_container(YRPX, payload))
    assert replay.header.format == "yrpX"
    assert [(p.message, p.payload) for p in replay.packets] == [
        (40, b"AB"), (41, b"C")]
    assert replay.summary()["packet_count"] == 2
    assert replay.summary()["response_count"] == 0
    assert replay.summary()["selection_prompt_packet_count"] == 0
    assert replay.summary()["embedded_yrp_response_count"] is None
    assert not replay.decks


def test_yrpx_exposes_bounded_embedded_yrp1_without_private_summary_values():
    legacy_payload = (_prefix(YRP1) + struct.pack("<I2II", 2, 10, 20, 0)
                      + struct.pack("<I1II", 1, 30, 0)
                      + struct.pack("<I", 0) + b"\x01\x05\x00")
    legacy = _container(YRP1, legacy_payload)
    packets = (bytes((11,)) + struct.pack("<I", 1) + b"X"
               + bytes((231,)) + struct.pack("<I", len(legacy)) + legacy)
    replay = parse_edopro_container(_container(YRPX, _prefix(YRPX) + packets))
    embedded = replay.embedded_legacy_replay()
    assert embedded is not None
    assert embedded.header.format == "yrp"
    assert embedded.decks[0].main == (10, 20)
    assert embedded.responses == (b"\x05",)
    summary = replay.summary()
    assert summary["selection_prompt_packet_count"] == 1
    assert summary["embedded_yrp_response_count"] == 1
    assert "Private player" not in str(summary)
    assert "10, 20" not in str(summary)


def test_yrpx_rejects_wrong_or_duplicate_embedded_replay():
    wrong = _container(YRPX, _prefix(YRPX))
    record = bytes((231,)) + struct.pack("<I", len(wrong)) + wrong
    replay = parse_edopro_container(_container(YRPX, _prefix(YRPX) + record))
    with pytest.raises(ReplayContainerError, match="not yrp1"):
        replay.embedded_legacy_replay()
    replay = parse_edopro_container(_container(YRPX, _prefix(YRPX) + record * 2))
    with pytest.raises(ReplayContainerError, match="multiple embedded"):
        replay.embedded_legacy_replay()


def test_yrpx_accepts_bounded_zero_padding_without_lzma_end_marker():
    payload = _prefix(YRPX) + bytes((40,)) + struct.pack("<I", 1) + b"A"
    flags = NEW_REPLAY | DUEL_FLAG_64BIT | COMPRESSED
    dictionary = 1 << 20
    filters = [{"id": lzma.FILTER_LZMA1, "dict_size": dictionary,
                "lc": 3, "lp": 0, "pb": 2}]
    props = bytes((93,)) + dictionary.to_bytes(4, "little") + b"\x00" * 3

    def packed(suffix: bytes) -> bytes:
        # EDOPro's raw LZMA stream need not carry an EOS marker. A real
        # yrpX may emit zero padding beyond its declared payload size.
        compressed = lzma.compress(payload + suffix, format=lzma.FORMAT_RAW,
                                   filters=filters)[:-1]
        return HEADER.pack(YRPX, 1, flags, 12345, len(payload), 0, props) + compressed

    replay = parse_edopro_container(packed(b"\x00" * 3))
    assert [(packet.message, packet.payload) for packet in replay.packets] == [(40, b"A")]
    with pytest.raises(ReplayContainerError, match="compressed replay"):
        parse_edopro_container(packed(b"\x00X"))
    with pytest.raises(ReplayContainerError, match="compressed replay"):
        parse_edopro_container(packed(b"\x00" * 9))


def test_inspection_cli_outputs_only_structural_summary(tmp_path, monkeypatch, capsys):
    from scripts.inspect_edopro_replay import main

    path = tmp_path / "private.yrpX"
    path.write_bytes(_container(YRPX, _prefix(YRPX)))
    monkeypatch.setattr(sys, "argv", ["inspect_edopro_replay.py", str(path)])
    main()
    report = json.loads(capsys.readouterr().out)
    assert report[0]["format"] == "yrpX"
    assert report[0]["decision_reconstruction"] == "not_implemented"
    assert "Private player" not in str(report)


@pytest.mark.parametrize("damage", (
    lambda data: data[:20],
    lambda data: data[:-1],
    lambda data: b"yrp2" + data[4:],
    lambda data: data[:16] + (128 * 1024 * 1024 + 1).to_bytes(4, "little") + data[20:],
))
def test_container_fails_closed_on_truncation_unknown_magic_and_size(damage):
    payload = _prefix(YRPX) + bytes((40,)) + struct.pack("<I", 1) + b"A"
    with pytest.raises(ReplayContainerError):
        parse_edopro_container(damage(_container(YRPX, payload)))
