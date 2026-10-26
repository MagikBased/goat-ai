"""Bounded EDOPro replay container reader, not a trajectory importer.

The layout follows edo9300/edopro gframe/replay.h and replay.cpp at
d0f111d6f3e0d4ee529b88a869ae0a971954bae3. Raw responses and packets are
retained for later reconstruction; they must never be used as player-visible
observations or imitation labels without a matching core and visibility audit.
"""

import hashlib
import lzma
import struct
from dataclasses import dataclass
from pathlib import Path

YRP1 = 0x31707279
YRPX = 0x58707279
COMPRESSED = 0x1
TAG = 0x2
SINGLE_MODE = 0x8
NEW_REPLAY = 0x20
HAND_TEST = 0x40
DUEL_FLAG_64BIT = 0x100
EXTENDED_HEADER = 0x200
HEADER = struct.Struct("<6I8s")
EXTENSION = struct.Struct("<5Q")  # header version, four native RNG words
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_PAYLOAD_BYTES = 128 * 1024 * 1024
MAX_PLAYERS = 16
MAX_CARDS_PER_ZONE = 255


class ReplayContainerError(ValueError):
    """An unsupported or malformed EDOPro replay container."""


@dataclass(frozen=True)
class ReplayHeader:
    format: str
    version: int
    flags: int
    timestamp: int
    payload_size: int
    header_version: int | None
    seed_words: tuple[int, int, int, int] | None


@dataclass(frozen=True)
class ReplayDeck:
    main: tuple[int, ...]
    extra: tuple[int, ...]


@dataclass(frozen=True)
class ReplayPacket:
    message: int
    payload: bytes


@dataclass(frozen=True)
class EdoReplayContainer:
    header: ReplayHeader
    sha256: str
    player_count: int
    duel_flags: int
    decks: tuple[ReplayDeck, ...]
    responses: tuple[bytes, ...]
    packets: tuple[ReplayPacket, ...]

    def summary(self) -> dict:
        """Return structural facts only; omit names, card IDs and raw choices."""
        return {
            "format": self.header.format,
            "sha256": self.sha256,
            "client_version": self.header.version,
            "flags": self.header.flags,
            "timestamp": self.header.timestamp,
            "header_version": self.header.header_version,
            "player_count": self.player_count,
            "duel_flags": self.duel_flags,
            "main_deck_counts": [len(deck.main) for deck in self.decks],
            "extra_deck_counts": [len(deck.extra) for deck in self.decks],
            "response_count": len(self.responses),
            "packet_count": len(self.packets),
            "decision_reconstruction": "not_implemented",
        }


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def take(self, size: int) -> bytes:
        if size < 0 or size > len(self.data) - self.offset:
            raise ReplayContainerError("truncated replay payload")
        result = self.data[self.offset:self.offset + size]
        self.offset += size
        return result

    def uint(self, width: int = 4) -> int:
        return int.from_bytes(self.take(width), "little")

    def cards(self) -> tuple[int, ...]:
        count = self.uint()
        if count > MAX_CARDS_PER_ZONE:
            raise ReplayContainerError("replay deck zone exceeds intake bound")
        return tuple(self.uint() for _ in range(count))

    def done(self) -> bool:
        return self.offset == len(self.data)


def _payload(data: bytes, flags: int, expected_size: int, properties: bytes) -> bytes:
    if expected_size > MAX_PAYLOAD_BYTES:
        raise ReplayContainerError("declared replay payload exceeds intake bound")
    if not flags & COMPRESSED:
        if expected_size != len(data):
            raise ReplayContainerError("uncompressed replay size mismatch")
        return data
    prop = properties[0]
    lc = prop % 9
    rest = prop // 9
    lp = rest % 5
    pb = rest // 5
    dictionary = int.from_bytes(properties[1:5], "little")
    if pb > 4 or dictionary < 4096 or dictionary > MAX_PAYLOAD_BYTES:
        raise ReplayContainerError("invalid LZMA replay properties")
    try:
        decoder = lzma.LZMADecompressor(
            format=lzma.FORMAT_RAW,
            filters=[{"id": lzma.FILTER_LZMA1, "dict_size": dictionary,
                      "lc": lc, "lp": lp, "pb": pb}],
        )
        result = decoder.decompress(data, max_length=MAX_PAYLOAD_BYTES + 1)
    except lzma.LZMAError as exc:
        raise ReplayContainerError("invalid compressed replay payload") from exc
    if (len(result) != expected_size or not decoder.eof
            or decoder.unused_data):
        raise ReplayContainerError("compressed replay size or end marker mismatch")
    return result


def parse_edopro_container(data: bytes) -> EdoReplayContainer:
    """Parse YRP1/YRPX structure; this does not recover legal choices or views."""
    if len(data) > MAX_FILE_BYTES:
        raise ReplayContainerError("replay file exceeds intake bound")
    if len(data) < HEADER.size:
        raise ReplayContainerError("truncated replay header")
    magic, version, flags, timestamp, size, _hash, props = HEADER.unpack_from(data)
    if magic not in (YRP1, YRPX):
        raise ReplayContainerError("unsupported replay magic (only EDOPro yrp1/yrpX)")
    header_size = HEADER.size
    header_version = None
    seed_words = None
    if flags & EXTENDED_HEADER:
        if len(data) < header_size + EXTENSION.size:
            raise ReplayContainerError("truncated extended replay header")
        header_version, *words = EXTENSION.unpack_from(data, header_size)
        if header_version > 1:
            raise ReplayContainerError("unsupported extended replay header version")
        seed_words = tuple(words)
        header_size += EXTENSION.size
    payload = _payload(data[header_size:], flags, size, props)
    reader = _Reader(payload)
    if flags & SINGLE_MODE:
        counts = (1, 1)
        reader.take(80)
    else:
        counts = []
        for _ in range(2):
            count = reader.uint() if flags & NEW_REPLAY else 2 if flags & TAG else 1
            if count < 1 or count > MAX_PLAYERS:
                raise ReplayContainerError("invalid replay player count")
            reader.take(40 * count)  # UTF-16 names are private metadata.
            counts.append(count)
    player_count = sum(counts)
    if player_count > MAX_PLAYERS:
        raise ReplayContainerError("replay player count exceeds intake bound")
    if magic == YRP1:
        reader.take(12)  # starting LP, opening hand, draw count
    duel_flags = reader.uint(8 if flags & DUEL_FLAG_64BIT else 4)
    if magic == YRP1 and flags & SINGLE_MODE:
        reader.take(reader.uint(2))  # single-player script name
    decks: list[ReplayDeck] = []
    if magic == YRP1 and (not flags & SINGLE_MODE or flags & HAND_TEST):
        for _ in range(player_count):
            decks.append(ReplayDeck(reader.cards(), reader.cards()))
        if flags & NEW_REPLAY and not flags & HAND_TEST:
            reader.cards()  # custom rule-card IDs, not Main Deck cards
    responses: list[bytes] = []
    packets: list[ReplayPacket] = []
    if magic == YRP1:
        while not reader.done():
            length = reader.uint(1)
            if length == 0:
                if not reader.done():
                    raise ReplayContainerError("bytes after replay response terminator")
                break
            responses.append(reader.take(length))
    else:
        while not reader.done():
            message = reader.uint(1)
            length = reader.uint()
            packets.append(ReplayPacket(message, reader.take(length)))
    header = ReplayHeader("yrp" if magic == YRP1 else "yrpX", version, flags,
                          timestamp, size, header_version, seed_words)
    return EdoReplayContainer(header, hashlib.sha256(data).hexdigest(),
                              player_count, duel_flags, tuple(decks),
                              tuple(responses), tuple(packets))


def read_edopro_container(path: str | Path) -> EdoReplayContainer:
    file = Path(path)
    if file.stat().st_size > MAX_FILE_BYTES:
        raise ReplayContainerError("replay file exceeds intake bound")
    return parse_edopro_container(file.read_bytes())
