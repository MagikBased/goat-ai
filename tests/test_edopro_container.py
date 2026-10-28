"""Source-layout replay container tests; no decision reconstruction claim."""

import json
import lzma
import os
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from goat_ai.replay.edopro_container import (
    COMPRESSED,
    DUEL_FLAG_64BIT,
    EXTENDED_HEADER,
    HEADER,
    NEW_REPLAY,
    YRP1,
    YRPX,
    ReplayContainerError,
    ReplayDeck,
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


def _prefix(magic: int, *, settings: tuple[int, int, int] = (8000, 5, 1),
            duel_flags: int = 34226374444) -> bytes:
    names = (struct.pack("<I", 1) + _name("Private player A")
             + struct.pack("<I", 1) + _name("Private player B"))
    encoded_settings = struct.pack("<III", *settings) if magic == YRP1 else b""
    return names + encoded_settings + struct.pack("<Q", duel_flags)


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
    assert replay.settings is not None
    assert (replay.settings.starting_life_points,
            replay.settings.opening_hand_size,
            replay.settings.draw_count) == (8000, 5, 1)
    assert replay.player_count == 2
    assert replay.decks[0].main == (10, 20)
    assert replay.decks[1].main == (30, 40, 50)
    assert replay.responses == (b"\x01\x02", b"\xff")
    summary = replay.summary()
    assert summary["decision_reconstruction"] == "not_implemented"
    assert summary["main_deck_counts"] == [2, 3]
    assert summary["response_count"] == 2
    assert summary["duel_settings"] == {
        "starting_life_points": 8000, "opening_hand_size": 5, "draw_count": 1,
    }
    assert "Private player" not in str(summary)
    assert "10, 20" not in str(summary)


def test_yrpx_reads_packet_stream_without_mislabeling_as_decisions():
    payload = (_prefix(YRPX) + bytes((40,)) + struct.pack("<I", 2) + b"AB"
               + bytes((41,)) + struct.pack("<I", 1) + b"C")
    replay = parse_edopro_container(_container(YRPX, payload))
    assert replay.header.format == "yrpX"
    assert replay.settings is None
    assert [(p.message, p.payload) for p in replay.packets] == [
        (40, b"AB"), (41, b"C")]
    assert replay.summary()["packet_count"] == 2
    assert replay.summary()["response_count"] == 0
    assert replay.summary()["selection_prompt_packet_count"] == 0
    assert replay.summary()["embedded_yrp_response_count"] is None
    assert not replay.decks


def test_yrp1_retains_custom_rule_cards_without_exposing_ids_in_summary():
    payload = (_prefix(YRP1) + struct.pack("<I", 0) * 4
               + struct.pack("<II", 1, 987654321) + b"\x00")
    replay = parse_edopro_container(_container(YRP1, payload))
    assert replay.rule_cards == (987654321,)
    assert replay.summary()["rule_card_count"] == 1
    assert "987654321" not in str(replay.summary())


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
    assert embedded.settings is not None
    assert embedded.settings.draw_count == 1
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
    assert report[0]["goat_rules_screen"] == "unavailable_no_legacy_settings"
    assert "Private player" not in str(report)


def test_goat_pool_screen_reports_counts_without_private_card_ids(tmp_path,
                                                                 monkeypatch, capsys):
    from scripts.inspect_edopro_replay import main

    legacy_payload = (_prefix(YRP1) + struct.pack("<I2II", 2, 10, 20, 0)
                      + struct.pack("<I1II", 1, 30, 0)
                      + struct.pack("<I", 0) + b"\x01\x05\x00")
    legacy = _container(YRP1, legacy_payload)
    packet = bytes((231,)) + struct.pack("<I", len(legacy)) + legacy
    path = tmp_path / "private.yrpX"
    path.write_bytes(_container(YRPX, _prefix(YRPX) + packet))
    whitelist = tmp_path / "GOAT.lflist.conf"
    whitelist.write_text("$whitelist\n10 3\n20 0\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["inspect_edopro_replay.py", str(path),
                                       "--goat-whitelist", str(whitelist)])
    main()
    report = json.loads(capsys.readouterr().out)[0]
    assert report["goat_main_cards_outside_whitelist"] == 2
    assert report["goat_extra_cards_outside_whitelist"] == 0
    assert report["goat_exact_id_copy_excess"] == 0
    assert report["goat_pool_screen"] == "outside_pool_or_deck_size"
    assert "30" not in str(report)


def test_goat_pool_screen_rejects_main_extra_copy_excess_per_player():
    from scripts.inspect_edopro_replay import goat_pool_screen

    cards = tuple(range(1, 41))
    replay = SimpleNamespace(
        decks=(ReplayDeck(cards, (1,)), ReplayDeck(cards, ())),
        embedded_legacy_replay=lambda: None,
    )
    whitelist = {code: 3 for code in cards}
    whitelist[1] = 1
    report = goat_pool_screen(replay, whitelist)
    assert report["goat_pool_screen"] == "exact_id_copy_limit_exceeded"
    assert report["goat_exact_id_copy_excess"] == 1
    assert report["goat_main_cards_outside_whitelist"] == 0
    assert report["goat_extra_cards_outside_whitelist"] == 0
    assert "(1," not in str(report)

    replay.decks = (ReplayDeck(cards, ()), ReplayDeck(cards, ()))
    report = goat_pool_screen(replay, whitelist)
    assert report["goat_pool_screen"] == "candidate_only"
    assert report["goat_exact_id_copy_excess"] == 0


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_native_deck_screen_catches_alias_copies_and_nonfusion_extra():
    from goat_ai.engine.decks import read_goat_whitelist
    from goat_ai.engine.probe_deck import VANILLA_DECK
    from scripts.inspect_edopro_replay import (
        goat_native_deck_screen,
        goat_pool_screen,
    )

    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    whitelist = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    replay = SimpleNamespace(
        decks=(ReplayDeck(VANILLA_DECK, ()), ReplayDeck(VANILLA_DECK, ())),
        embedded_legacy_replay=lambda: None,
    )
    assert goat_native_deck_screen(replay, root, whitelist)[
        "goat_native_deck_screen"] == "candidate_only"

    # Both permitted IDs point to one canonical limited card in the pinned DB.
    alias_main = (77585514, 77585513, *VANILLA_DECK[2:])
    replay.decks = (ReplayDeck(alias_main, ()), ReplayDeck(VANILLA_DECK, ()))
    assert goat_pool_screen(replay, whitelist)["goat_pool_screen"] == "candidate_only"
    report = goat_native_deck_screen(replay, root, whitelist)
    assert report["goat_native_deck_screen"] == "rejected"
    assert report["goat_native_decks_rejected"] == 1
    assert "775855" not in str(report)

    replay.decks = (ReplayDeck(VANILLA_DECK, (97923414,)),
                    ReplayDeck(VANILLA_DECK, ()))
    assert goat_pool_screen(replay, whitelist)["goat_pool_screen"] == "candidate_only"
    assert goat_native_deck_screen(replay, root, whitelist)[
        "goat_native_deck_screen"] == "rejected"


def test_goat_rules_screen_rejects_wrong_setup_without_private_values():
    from scripts.inspect_edopro_replay import goat_rules_screen

    payload = (_prefix(YRP1, settings=(4000, 6, 2), duel_flags=0)
               + struct.pack("<I", 0) * 5)
    replay = parse_edopro_container(_container(YRP1, payload))
    assert goat_rules_screen(replay) == {
        "goat_rules_screen": "unsupported_setup",
        "goat_rules_mismatches": ["duel_flags", "starting_life_points",
                                  "opening_hand_size", "draw_count"],
    }


def test_goat_rules_screen_checks_embedded_legacy_settings():
    from scripts.inspect_edopro_replay import goat_rules_screen

    payload = _prefix(YRP1) + struct.pack("<I", 0) * 5
    legacy = _container(YRP1, payload)
    packet = bytes((231,)) + struct.pack("<I", len(legacy)) + legacy
    replay = parse_edopro_container(_container(YRPX, _prefix(YRPX) + packet))
    assert goat_rules_screen(replay) == {
        "goat_rules_screen": "setup_candidate_only", "goat_rules_mismatches": [],
    }


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
