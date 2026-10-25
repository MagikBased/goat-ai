"""Minimal native ocgcore GOAT-mode startup probe, not a duel adapter.

The ABI and flag value are pinned to edo9300/ygopro-core baa3881. Do not use
this class as a player-facing environment: raw native messages may reveal
private information and most decision messages are not decoded here.
"""

import ctypes as c
import hashlib
import random
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path

from goat_ai.observations import (
    CardView,
    ChainLinkView,
    DisabledZoneView,
    KnownCardView,
    Observation,
    PrivateRevealView,
    PublicRevealView,
    RevealedCardView,
)

CORE_API_VERSION = (11, 0)
GOAT_FLAGS = 34226374444  # DUEL_MODE_GOAT in pinned ocgapi_constants.h
UPSTREAM_UTILITY_SHA256 = "59ebe317dbec0ef5134f485f039bbe0cee031aa68e6d0ac028123a318ee2cd2a"
GOAT_DECK_CONFIRM_OLD = b"Duel.ConfirmCards(tp,dg)"
GOAT_DECK_CONFIRM_HISTORICAL = b"Duel.ConfirmCards(1-tp,dg)"
LOCATION_DECK = 0x01
LOCATION_HAND = 0x02
LOCATION_MZONE = 0x04
LOCATION_SZONE = 0x08
LOCATION_GRAVE = 0x10
LOCATION_REMOVED = 0x20
LOCATION_EXTRA = 0x40
POSITION_FACEDOWN_DEFENSE = 0x08
MSG_SELECT_IDLECMD = 11
MSG_SELECT_CHAIN = 16
MSG_CHAINING = 70
MSG_CHAIN_END = 74
MSG_DRAW = 90
MSG_MOVE = 50
MSG_POS_CHANGE = 53
MSG_SET = 54
MSG_SWAP = 55
MSG_SHUFFLE_SET_CARD = 36
MSG_CONFIRM_DECKTOP = 30
MSG_CONFIRM_CARDS = 31
MSG_FIELD_DISABLED = 56
MSG_ATTACK = 110
MSG_DAMAGE_STEP_START = 113
MSG_DAMAGE_STEP_END = 114
MSG_PLAYER_HINT = 165
PHINT_DESC_ADD = 6
PHINT_DESC_REMOVE = 7
SCAPEGOAT_SUMMON_HINT = (504700123 << 20) | 1
STATUS_AWAITING = 1


class CardData(c.Structure):
    _fields_ = [
        ("code", c.c_uint32), ("alias", c.c_uint32),
        ("setcodes", c.POINTER(c.c_uint16)), ("type", c.c_uint32),
        ("level", c.c_uint32), ("attribute", c.c_uint32),
        ("race", c.c_uint64), ("attack", c.c_int32), ("defense", c.c_int32),
        ("lscale", c.c_uint32), ("rscale", c.c_uint32),
        ("link_marker", c.c_uint32),
    ]


class Player(c.Structure):
    _fields_ = [("startingLP", c.c_uint32), ("startingDrawCount", c.c_uint32),
                ("drawCountPerTurn", c.c_uint32)]


DataReader = c.CFUNCTYPE(None, c.c_void_p, c.c_uint32, c.POINTER(CardData))
ScriptReader = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p, c.c_char_p)
LogHandler = c.CFUNCTYPE(None, c.c_void_p, c.c_char_p, c.c_int)
DataReaderDone = c.CFUNCTYPE(None, c.c_void_p, c.POINTER(CardData))


class DuelOptions(c.Structure):
    _fields_ = [
        ("seed", c.c_uint64 * 4), ("flags", c.c_uint64),
        ("team1", Player), ("team2", Player),
        ("cardReader", DataReader), ("payload1", c.c_void_p),
        ("scriptReader", ScriptReader), ("payload2", c.c_void_p),
        ("logHandler", LogHandler), ("payload3", c.c_void_p),
        ("cardReaderDone", DataReaderDone), ("payload4", c.c_void_p),
        ("enableUnsafeLibraries", c.c_uint8),
    ]


class NewCard(c.Structure):
    _fields_ = [
        ("team", c.c_uint8), ("duelist", c.c_uint8), ("code", c.c_uint32),
        ("con", c.c_uint8), ("loc", c.c_uint32), ("seq", c.c_uint32),
        ("pos", c.c_uint32),
    ]


class QueryInfo(c.Structure):
    _fields_ = [
        ("flags", c.c_uint32), ("con", c.c_uint8), ("loc", c.c_uint32),
        ("seq", c.c_uint32), ("overlay_seq", c.c_uint32),
    ]


@dataclass(frozen=True)
class FirstDecision:
    seed: int
    core_version: tuple[int, int]
    flags: int
    hand_counts: tuple[int, int]
    deck_counts: tuple[int, int]
    message_ids: tuple[int, ...]
    draw_events: tuple[tuple[int, int], ...]
    decision_message_id: int
    decision_player: int


@dataclass(frozen=True)
class NativeTransition:
    message_ids: tuple[int, ...]
    terminal: bool
    winner: int | None = None


def split_messages(buffer: bytes) -> tuple[bytes, ...]:
    """Core messages are length-prefixed frames; unknown IDs remain opaque."""
    messages = []
    offset = 0
    while offset < len(buffer):
        if len(buffer) - offset < 5:
            raise ValueError("truncated native message header")
        length = struct.unpack_from("<I", buffer, offset)[0]
        offset += 4
        if not length or offset + length > len(buffer):
            raise ValueError("invalid native message length")
        messages.append(buffer[offset:offset + length])
        offset += length
    return tuple(messages)


class OcgcoreProbe:
    """Owns one native duel; intended only for startup verification."""

    def __init__(self, library: Path, database: Path, scripts: Path) -> None:
        self.lib = c.CDLL(str(library.resolve()))
        self.db_path = database.resolve()
        self.db = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
        goat_database = database.parent / "goat-entries.cdb"
        self._has_goat_database = goat_database.is_file()
        if self._has_goat_database:
            self.db.execute("ATTACH DATABASE ? AS goat",
                            (f"file:{goat_database.resolve()}?mode=ro",))
        unofficial_database = database.parent / "cards-unofficial.cdb"
        self._has_unofficial_database = unofficial_database.is_file()
        if self._has_unofficial_database:
            self.db.execute("ATTACH DATABASE ? AS unofficial",
                            (f"file:{unofficial_database.resolve()}?mode=ro",))
        self.scripts = scripts.resolve()
        self.errors: list[str] = []
        self.loaded_script_sha256: dict[str, str] = {}
        self._setcodes: dict[int, c.Array] = {}
        self._duel = c.c_void_p()
        self._pending_message: bytes | None = None
        self._turn = 0
        self._phase = "unknown"
        self._chain: list[ChainLinkView] = []
        self._public_history: list[str] = []
        self._known_facedown: dict[tuple[int, int, int], int] = {}
        self._restriction_hints: dict[tuple[int, int], int] = {}
        self._public_reveals: list[PublicRevealView] = []
        self._private_reveals: list[PrivateRevealView] = []
        self._decision_private_reveals: list[PrivateRevealView] = []
        self._initial_main_decks: tuple[tuple[int, ...], tuple[int, ...]] = ((), ())
        self._announcement_codes: tuple[int, ...] | None = None
        self._disabled_zones: tuple[DisabledZoneView, ...] = ()
        self._bind()
        major, minor = c.c_int(), c.c_int()
        self.lib.OCG_GetVersion(c.byref(major), c.byref(minor))
        self.version = (major.value, minor.value)
        if self.version != CORE_API_VERSION:
            raise RuntimeError(f"ocgcore API {self.version} != pinned {CORE_API_VERSION}")
        self._reader = DataReader(self._read_card)
        self._script_reader = ScriptReader(self._read_script)
        self._logger = LogHandler(self._log)
        self._reader_done = DataReaderDone(lambda _payload, _data: None)

    def _bind(self) -> None:
        definitions = {
            "OCG_GetVersion": ([c.POINTER(c.c_int), c.POINTER(c.c_int)], None),
            "OCG_CreateDuel": ([c.POINTER(c.c_void_p), c.POINTER(DuelOptions)], c.c_int),
            "OCG_DestroyDuel": ([c.c_void_p], None),
            "OCG_DuelNewCard": ([c.c_void_p, c.POINTER(NewCard)], None),
            "OCG_StartDuel": ([c.c_void_p], None),
            "OCG_DuelProcess": ([c.c_void_p], c.c_int),
            "OCG_DuelGetMessage": ([c.c_void_p, c.POINTER(c.c_uint32)], c.c_void_p),
            "OCG_DuelSetResponse": ([c.c_void_p, c.c_void_p, c.c_uint32], None),
            "OCG_LoadScript": ([c.c_void_p, c.c_char_p, c.c_uint32, c.c_char_p], c.c_int),
            "OCG_DuelQueryCount": ([c.c_void_p, c.c_uint8, c.c_uint32], c.c_uint32),
            "OCG_DuelQueryLocation": ([c.c_void_p, c.POINTER(c.c_uint32),
                                        c.POINTER(QueryInfo)], c.c_void_p),
            "OCG_DuelQueryField": ([c.c_void_p, c.POINTER(c.c_uint32)], c.c_void_p),
        }
        for name, (argtypes, restype) in definitions.items():
            function = getattr(self.lib, name)
            function.argtypes = argtypes
            function.restype = restype

    def _read_card(self, _payload: int, code: int, result: c.POINTER(CardData)) -> None:
        row = self._card_row(code,
            "alias, setcode, type, level, attribute, race, atk, def")
        if row is None:
            self.errors.append(f"card {code} absent from database")
            return
        alias, setcode, card_type, level, attribute, race, attack, defense = row
        data = result.contents
        data.code = code
        data.alias = alias
        data.type = card_type
        data.level = level & 0xFF
        data.attribute = attribute
        data.race = race
        data.attack = attack
        data.defense = defense
        data.lscale = (level >> 24) & 0xFF
        data.rscale = (level >> 16) & 0xFF
        if setcode:
            parts = [(setcode >> shift) & 0xFFFF for shift in (0, 16, 32, 48)]
            self._setcodes[code] = (c.c_uint16 * 5)(*parts, 0)
            data.setcodes = self._setcodes[code]

    def _card_row(self, code: int, columns: str):
        if self._has_goat_database:
            row = self.db.execute(f"SELECT {columns} FROM goat.datas WHERE id=?",
                                  (code,)).fetchone()
            if row is not None:
                return row
        row = self.db.execute(
            f"SELECT {columns} FROM main.datas WHERE id=?", (code,),
        ).fetchone()
        if row is None and self._has_unofficial_database:
            row = self.db.execute(f"SELECT {columns} FROM unofficial.datas WHERE id=?",
                                  (code,)).fetchone()
        return row

    def decode_pending(self):
        """Decode the native prompt using the pinned historical card-name catalog."""
        from goat_ai.engine.native_messages import decode_decision

        if self._pending_message is None:
            raise RuntimeError("no pending native decision")
        if self._pending_message[0] != 142:
            return decode_decision(self._pending_message)
        if self._announcement_codes is None:
            from goat_ai.engine.decks import read_goat_whitelist

            pool = read_goat_whitelist(
                self.db_path.parent.parent / "banlist/GOAT.lflist.conf")
            # A historical card name may be Forbidden, so use all listed IDs.
            # GOAT variants report their alias as GetCode(); include the
            # original printed-name ID even when only its variant is listed.
            names = set(pool)
            for code in pool:
                row = self._card_row(code, "alias, type")
                if row is not None and row[1] & 1 and row[0]:
                    names.add(row[0])
            # The core rejects aliases and Tokens for this expression.
            self._announcement_codes = tuple(code for code in sorted(names)
                if (row := self._card_row(code, "alias, type")) is not None
                and row[0] == 0 and row[1] & 1 and not row[1] & 0x4000)
        return decode_decision(self._pending_message, self._announcement_codes)

    def _read_script(self, _payload: int, duel: int, name: bytes) -> int:
        relative = Path(name.decode("utf-8"))
        if relative.is_absolute() or ".." in relative.parts:
            self.errors.append(f"unsafe script path: {relative}")
            return 0
        path = self.scripts / relative
        if not path.is_file():
            path = self.scripts / "official" / relative
        if not path.is_file():
            path = self.scripts / "unofficial" / relative
        if not path.is_file():
            path = self.scripts / "goat" / relative
        if not path.is_file():
            path = self.scripts / "pre-errata" / relative
        if not path.is_file():
            # Vanilla monsters have no card script. Missing effect scripts
            # remain fatal, so the probe cannot silently omit card behavior.
            if relative.name == "c0.lua":
                return 0
            if relative.name.startswith("c") and relative.stem[1:].isdigit():
                code = int(relative.stem[1:])
                row = self._card_row(code, "type")
                if row and (row[0] == 17 or row[0] & 0x4000):
                    # Normal monsters and generated Tokens have no scripts.
                    return 0
            if not path.is_file():
                self.errors.append(f"missing script: {relative}")
            return 0
        contents = path.read_bytes()
        if relative == Path("utility.lua"):
            if hashlib.sha256(contents).hexdigest() != UPSTREAM_UTILITY_SHA256 \
                    or contents.count(GOAT_DECK_CONFIRM_OLD) != 1:
                self.errors.append("pinned GOAT utility script changed; deck-confirm patch not applied")
                return 0
            # Project Ignis' online variant confirms Deck contents to the
            # searching player. Historical verification addresses the opponent.
            contents = contents.replace(GOAT_DECK_CONFIRM_OLD,
                                        GOAT_DECK_CONFIRM_HISTORICAL)
        self.loaded_script_sha256[path.relative_to(self.scripts).as_posix()] = (
            hashlib.sha256(contents).hexdigest()
        )
        return self.lib.OCG_LoadScript(duel, contents, len(contents), name)

    def _log(self, _payload: int, message: bytes, _kind: int) -> None:
        self.errors.append(message.decode("utf-8", errors="replace"))

    def first_decision(self, seed: int, deck: tuple[int, ...],
                       opponent_deck: tuple[int, ...] | None = None,
                       extra: tuple[int, ...] = (),
                       opponent_extra: tuple[int, ...] = ()) -> FirstDecision:
        if self._duel.value:
            raise RuntimeError("probe instance already used")
        if len(deck) < 6:
            raise ValueError("probe deck requires at least six cards")
        if len(deck) < 40 or (opponent_deck is not None and len(opponent_deck) < 40):
            raise ValueError("native duel requires at least 40 main-deck cards per player")
        self._initial_main_decks = (tuple(sorted(deck)),
                                    tuple(sorted(opponent_deck if opponent_deck is not None
                                                 else deck)))
        # Four nonzero 64-bit words; exact split is part of reproducibility.
        words = tuple((seed + i + 1) & ((1 << 64) - 1) for i in range(4))
        opts = DuelOptions(
            (c.c_uint64 * 4)(*words), GOAT_FLAGS,
            Player(8000, 5, 1), Player(8000, 5, 1),
            self._reader, None, self._script_reader, None,
            self._logger, None, self._reader_done, None, 0,
        )
        status = self.lib.OCG_CreateDuel(c.byref(self._duel), c.byref(opts))
        if status != 0:
            raise RuntimeError(f"OCG_CreateDuel returned {status}: {self.errors}")
        for name in (b"constant.lua", b"utility.lua"):
            if not self._read_script(0, self._duel, name):
                raise RuntimeError(f"could not load {name.decode()}: {self.errors}")
        for team, cards in enumerate((deck, opponent_deck or deck)):
            shuffled = list(cards)
            random.Random(seed * 2 + team).shuffle(shuffled)
            for code in shuffled:
                card = NewCard(team, 0, code, team, LOCATION_DECK, 0,
                               POSITION_FACEDOWN_DEFENSE)
                self.lib.OCG_DuelNewCard(self._duel, c.byref(card))
        for team, cards in enumerate((extra, opponent_extra)):
            for code in cards:
                card = NewCard(team, 0, code, team, LOCATION_EXTRA, 0,
                               POSITION_FACEDOWN_DEFENSE)
                self.lib.OCG_DuelNewCard(self._duel, c.byref(card))
        if self.errors:
            raise RuntimeError(f"native setup failed: {self.errors}")
        self.lib.OCG_StartDuel(self._duel)
        messages: list[bytes] = []
        for _ in range(1000):
            status = self.lib.OCG_DuelProcess(self._duel)
            length = c.c_uint32()
            pointer = self.lib.OCG_DuelGetMessage(self._duel, c.byref(length))
            if length.value:
                messages.extend(split_messages(c.string_at(pointer, length.value)))
            if status == STATUS_AWAITING:
                break
            if status == 0:
                raise RuntimeError("duel ended before a decision")
        else:
            raise RuntimeError("native core did not reach a decision")
        if self.errors:
            raise RuntimeError(f"native processing errors: {self.errors}")
        self._update_public_clock(messages)
        decision = messages[-1]
        if decision[0] != MSG_SELECT_CHAIN or len(decision) < 2:
            raise RuntimeError(f"unsupported first decision message: {decision[0]}")
        self._pending_message = decision
        draw_events = []
        for message in messages:
            if message[0] == MSG_DRAW:
                if len(message) < 6:
                    raise ValueError("truncated MSG_DRAW")
                draw_events.append((message[1], struct.unpack_from("<I", message, 2)[0]))
        return FirstDecision(
            seed, self.version, GOAT_FLAGS,
            tuple(self.lib.OCG_DuelQueryCount(self._duel, p, LOCATION_HAND) for p in (0, 1)),
            tuple(self.lib.OCG_DuelQueryCount(self._duel, p, LOCATION_DECK) for p in (0, 1)),
            tuple(message[0] for message in messages), tuple(draw_events), decision[0], decision[1],
        )

    def _update_public_clock(self, messages: list[bytes]) -> None:
        phases = {1: "draw", 2: "standby", 4: "main1", 8: "battle_start",
                  16: "battle_step", 32: "damage_step", 64: "damage_calculation",
                  128: "battle", 256: "main2", 512: "end"}
        for message in messages:
            if message[0] == MSG_MOVE:
                if len(message) != 29:
                    raise ValueError("invalid MSG_MOVE length")
                old_key = (message[5], message[6],
                           struct.unpack_from("<I", message, 7)[0])
                new_key = (message[15], message[16],
                           struct.unpack_from("<I", message, 17)[0])
                known_code = self._known_facedown.pop(old_key, None)
                self._known_facedown.pop(new_key, None)
                if (known_code is not None and new_key[0] in (0, 1)
                        and new_key[1] in (LOCATION_MZONE, LOCATION_SZONE)
                        and struct.unpack_from("<I", message, 21)[0] & 0xA):
                    # A known facedown card can change control without
                    # exposing its current field identity. Carry only the
                    # previous memory, never the raw code in MSG_MOVE.
                    self._known_facedown[new_key] = known_code
            elif message[0] == MSG_POS_CHANGE:
                if len(message) != 10:
                    raise ValueError("invalid MSG_POS_CHANGE length")
                key = (message[5], message[6], message[7])
                self._known_facedown.pop(key, None)
                if (key[0] in (0, 1) and key[1] in (LOCATION_MZONE, LOCATION_SZONE)
                        and message[8] & 0x5 and message[9] & 0xA):
                    # The card was face-up immediately before this public change.
                    self._known_facedown[key] = struct.unpack_from("<I", message, 1)[0]
            elif message[0] == MSG_SET:
                if len(message) != 15:
                    raise ValueError("invalid MSG_SET length")
                key = (message[5], message[6], struct.unpack_from("<I", message, 7)[0])
                self._known_facedown.pop(key, None)
            elif message[0] == MSG_SWAP:
                self._known_facedown.clear()
            elif message[0] == MSG_SHUFFLE_SET_CARD:
                if len(message) < 3:
                    raise ValueError("invalid MSG_SHUFFLE_SET_CARD length")
                location = message[1]
                self._known_facedown = {key: code for key, code in
                                        self._known_facedown.items() if key[1] != location}
            elif message[0] == MSG_CONFIRM_DECKTOP:
                if len(message) < 6 or message[1] not in (0, 1):
                    raise ValueError("invalid MSG_CONFIRM_DECKTOP")
                count = struct.unpack_from("<I", message, 2)[0]
                if not count or len(message) != 6 + count * 10:
                    raise ValueError("invalid MSG_CONFIRM_DECKTOP card count")
                codes = tuple(struct.unpack_from("<I", message, 6 + index * 10)[0]
                              for index in range(count))
                self._public_reveals.append(PublicRevealView(
                    self._turn, message[1], "deck_top", codes))
            elif message[0] == MSG_CONFIRM_CARDS:
                if len(message) < 6 or message[1] not in (0, 1):
                    raise ValueError("invalid MSG_CONFIRM_CARDS")
                count = struct.unpack_from("<I", message, 2)[0]
                if len(message) != 6 + count * 10:
                    raise ValueError("invalid MSG_CONFIRM_CARDS card count")
                if count:
                    recipient = message[1]
                    cards = tuple(sorted((RevealedCardView(
                        struct.unpack_from("<I", message, 6 + index * 10)[0],
                        message[10 + index * 10], message[11 + index * 10])
                        for index in range(count)),
                        key=lambda card: (card.controller, card.location, card.code)))
                    reveal = PrivateRevealView(self._turn, recipient, cards)
                    self._private_reveals.append(reveal)
                    self._decision_private_reveals.append(reveal)
                    for index in range(count):
                        controller = message[10 + index * 10]
                        location = message[11 + index * 10]
                        if controller != recipient and location in (LOCATION_MZONE, LOCATION_SZONE):
                            sequence = struct.unpack_from("<I", message, 12 + index * 10)[0]
                            code = struct.unpack_from("<I", message, 6 + index * 10)[0]
                            self._known_facedown[(controller, location, sequence)] = code
            elif message[0] == MSG_FIELD_DISABLED:
                if len(message) != 5:
                    raise ValueError("invalid MSG_FIELD_DISABLED length")
                mask = struct.unpack_from("<I", message, 1)[0]
                self._disabled_zones = tuple(
                    DisabledZoneView(player, zone, sequence)
                    for player in (0, 1)
                    for zone, offset, size in (("monster", 0, 7), ("spell_trap", 8, 8))
                    for sequence in range(size)
                    if mask & (1 << (player * 16 + offset + sequence))
                )
            elif message[0] == MSG_PLAYER_HINT:
                if len(message) != 11 or message[1] not in (0, 1):
                    raise ValueError("invalid MSG_PLAYER_HINT")
                hint = message[2]
                description = struct.unpack_from("<Q", message, 3)[0]
                if description == SCAPEGOAT_SUMMON_HINT:
                    key = (message[1], description)
                    if hint == PHINT_DESC_ADD:
                        self._restriction_hints[key] = self._restriction_hints.get(key, 0) + 1
                    elif hint == PHINT_DESC_REMOVE:
                        count = self._restriction_hints.get(key, 0)
                        if not count:
                            raise ValueError("unmatched Scapegoat restriction hint removal")
                        if count == 1:
                            del self._restriction_hints[key]
                        else:
                            self._restriction_hints[key] = count - 1
            if message[0] == 40:
                self._turn += 1
                self._public_history.append(f"turn:{self._turn}")
            elif message[0] == 41:
                if len(message) < 3:
                    raise ValueError("truncated MSG_NEW_PHASE")
                phase = struct.unpack_from("<H", message, 1)[0]
                self._phase = phases.get(phase, f"phase_{phase}")
                self._public_history.append(f"phase:{self._phase}")
            elif message[0] == MSG_ATTACK:
                self._phase = "battle_step"
                self._public_history.append("attack")
            elif message[0] == MSG_DAMAGE_STEP_START:
                if len(message) != 1:
                    raise ValueError("invalid MSG_DAMAGE_STEP_START length")
                self._phase = "damage_step"
                self._public_history.append("damage_step:start")
            elif message[0] == MSG_DAMAGE_STEP_END:
                if len(message) != 1:
                    raise ValueError("invalid MSG_DAMAGE_STEP_END length")
                self._phase = "battle_step"
                self._public_history.append("damage_step:end")
            elif message[0] == MSG_CHAINING:
                if len(message) != 33:
                    raise ValueError("invalid MSG_CHAINING length")
                index = struct.unpack_from("<I", message, 29)[0]
                if index != len(self._chain) + 1:
                    raise ValueError("unexpected native chain index")
                self._chain.append(ChainLinkView(
                    index=index, card_code=struct.unpack_from("<I", message, 1)[0],
                    controller=message[15], location=message[16],
                    sequence=struct.unpack_from("<I", message, 17)[0],
                ))
                self._public_history.append(f"chain:{index}:start")
            elif message[0] == MSG_CHAIN_END:
                if len(message) != 1:
                    raise ValueError("invalid MSG_CHAIN_END length")
                self._chain.clear()
                self._public_history.append("chain:end")

    def _query_location(self, player: int, location: int):
        from goat_ai.engine.native_queries import (
            QUERY_ATTACK,
            QUERY_CODE,
            QUERY_COUNTERS,
            QUERY_DEFENSE,
            QUERY_POSITION,
            decode_location,
        )

        flags = QUERY_CODE | QUERY_POSITION
        if location == LOCATION_MZONE:
            flags |= QUERY_ATTACK | QUERY_DEFENSE | QUERY_COUNTERS
        query = QueryInfo(flags, player, location, 0, 0)
        length = c.c_uint32()
        pointer = self.lib.OCG_DuelQueryLocation(self._duel, c.byref(length), c.byref(query))
        if not pointer or not length.value:
            raise RuntimeError("native location query returned no data")
        return decode_location(c.string_at(pointer, length.value))

    def observation(self, viewer: int) -> Observation:
        """Build a redacted view; only audited fields are requested or returned."""
        if self._pending_message is None or viewer not in (0, 1):
            raise RuntimeError("observation requires a pending decision and valid viewer")
        from goat_ai.engine.native_queries import decode_life_points

        locations = {}
        for player in (0, 1):
            for location in (LOCATION_MZONE, LOCATION_SZONE, LOCATION_GRAVE,
                             LOCATION_REMOVED):
                locations[player, location] = self._query_location(player, location)
        hand = self._query_location(viewer, LOCATION_HAND)
        own_extra = self._query_location(viewer, LOCATION_EXTRA)
        length = c.c_uint32()
        pointer = self.lib.OCG_DuelQueryField(self._duel, c.byref(length))
        if not pointer or not length.value:
            raise RuntimeError("native field query returned no data")
        lp = decode_life_points(
            c.string_at(pointer, length.value),
            tuple(len(locations[p, LOCATION_MZONE]) for p in (0, 1)),
            tuple(len(locations[p, LOCATION_SZONE]) for p in (0, 1)),
        )

        def view_card(player: int, location: int, sequence: int, card) -> CardView:
            faceup = bool(card.position & 0x5)
            visible_code = card.code if player == viewer or faceup else None
            position = "faceup" if faceup else "facedown"
            zone = {LOCATION_MZONE: "monster", LOCATION_SZONE: "spell_trap",
                    LOCATION_GRAVE: "graveyard", LOCATION_REMOVED: "banished",
                    LOCATION_EXTRA: "extra"}[location]
            orientation = None
            if location == LOCATION_MZONE:
                if card.position in (0x1, 0x2):
                    orientation = "attack"
                elif card.position in (0x4, 0x8):
                    orientation = "defense"
                else:
                    raise ValueError(f"unexpected monster position {card.position:#x}")
            return CardView(player, zone, position, visible_code, sequence, orientation,
                            card.attack if location == LOCATION_MZONE and faceup else None,
                            card.defense if location == LOCATION_MZONE and faceup else None,
                            card.counters if location == LOCATION_MZONE and faceup else ())

        field = tuple(view_card(player, location, sequence, card)
                      for player in (0, 1) for location in (LOCATION_MZONE, LOCATION_SZONE)
                      for sequence, card in enumerate(locations[player, location]) if card is not None)
        graveyards = tuple(tuple(view_card(player, LOCATION_GRAVE, sequence, card)
                                 for sequence, card in enumerate(locations[player, LOCATION_GRAVE])
                                 if card is not None)
                           for player in (0, 1))
        banished = tuple(tuple(view_card(player, LOCATION_REMOVED, sequence, card)
                               for sequence, card in enumerate(locations[player, LOCATION_REMOVED])
                               if card is not None)
                         for player in (0, 1))
        return Observation(
            viewer=viewer, acting_player=self.decode_pending().player,
            turn=self._turn, phase=self._phase, life_points=lp,
            hand=tuple(CardView(viewer, "hand", "hidden", card.code, sequence)
                       for sequence, card in enumerate(hand) if card is not None),
            field=field, graveyards=graveyards, banished=banished,
            opponent_hand_count=self.lib.OCG_DuelQueryCount(self._duel, 1 - viewer,
                                                            LOCATION_HAND),
            deck_counts=tuple(self.lib.OCG_DuelQueryCount(self._duel, p, LOCATION_DECK)
                              for p in (0, 1)),
            extra_deck_counts=tuple(self.lib.OCG_DuelQueryCount(self._duel, p, LOCATION_EXTRA)
                                    for p in (0, 1)),
            own_extra_deck=tuple(view_card(viewer, LOCATION_EXTRA, sequence, card)
                                 for sequence, card in enumerate(own_extra)
                                 if card is not None),
            chain=tuple(self._chain),
            public_history=tuple(self._public_history[-64:]),
            known_opponent_cards=tuple(
                self._known_facedown[(card.controller,
                                      LOCATION_MZONE if card.zone == "monster" else LOCATION_SZONE,
                                      card.sequence)]
                for card in field if card.controller != viewer and card.position == "facedown"
                and (card.controller,
                     LOCATION_MZONE if card.zone == "monster" else LOCATION_SZONE,
                     card.sequence) in self._known_facedown),
            known_opponent_field_cards=tuple(
                KnownCardView(card.controller, card.zone, card.sequence,
                              self._known_facedown[(card.controller,
                                                    LOCATION_MZONE if card.zone == "monster"
                                                    else LOCATION_SZONE, card.sequence)])
                for card in field if card.controller != viewer and card.position == "facedown"
                and (card.controller,
                     LOCATION_MZONE if card.zone == "monster" else LOCATION_SZONE,
                     card.sequence) in self._known_facedown),
            restrictions=tuple(
                f"player{player}:cannot_summon_this_turn:scapegoat"
                for player in (0, 1)
                if self._restriction_hints.get((player, SCAPEGOAT_SUMMON_HINT), 0)),
            public_reveals=tuple(self._public_reveals),
            disabled_zones=self._disabled_zones,
            private_reveals=tuple(reveal for reveal in self._private_reveals
                                  if reveal.recipient == viewer),
            own_main_deck=self._initial_main_decks[viewer],
        )

    def pass_empty_chain(self) -> tuple[int, ...]:
        """Advance one zero-option chain response; never expose raw state to an agent."""
        message = self._pending_message
        if message is None or len(message) < 16 or message[0] != MSG_SELECT_CHAIN:
            raise RuntimeError("expected a pending MSG_SELECT_CHAIN")
        option_count = struct.unpack_from("<I", message, 12)[0]
        if option_count or message[3]:
            raise RuntimeError("chain has choices or a forced response")
        return self.respond(-1).message_ids

    def respond(self, response_value: int | bytes) -> NativeTransition:
        """Send one native response and process until another decision or terminal."""
        if self._pending_message is None:
            raise RuntimeError("no pending native decision")
        choices = self.decode_pending().choices
        if response_value not in {choice.response for choice in choices}:
            raise ValueError("illegal native response")
        self._decision_private_reveals.clear()
        if isinstance(response_value, int):
            response = c.c_int32(response_value)
            self.lib.OCG_DuelSetResponse(self._duel, c.byref(response), c.sizeof(response))
        else:
            response = c.create_string_buffer(response_value)
            self.lib.OCG_DuelSetResponse(self._duel, response, len(response_value))
        self._pending_message = None
        frames_seen: list[bytes] = []
        for _ in range(1000):
            status = self.lib.OCG_DuelProcess(self._duel)
            length = c.c_uint32()
            pointer = self.lib.OCG_DuelGetMessage(self._duel, c.byref(length))
            if length.value:
                frames = split_messages(c.string_at(pointer, length.value))
                frames_seen.extend(frames)
                self._update_public_clock(list(frames))
                if status == STATUS_AWAITING:
                    self._pending_message = frames[-1]
            if self.errors:
                raise RuntimeError(f"native processing errors: {self.errors}")
            win_frames = [frame for frame in frames_seen if frame[0] == 5]
            if win_frames:
                if len(win_frames) != 1 or len(win_frames[0]) < 2:
                    raise RuntimeError("invalid MSG_WIN")
                winner = win_frames[0][1]
                self._pending_message = None
                return NativeTransition(tuple(frame[0] for frame in frames_seen), True,
                                        winner if winner in (0, 1) else None)
            if status == STATUS_AWAITING:
                if self._pending_message is None:
                    raise RuntimeError("native core awaited a response without a message")
                return NativeTransition(tuple(frame[0] for frame in frames_seen), False)
            if status == 0:
                raise RuntimeError("duel ended without MSG_WIN")
        raise RuntimeError("native core did not reach the next decision")

    def close(self) -> None:
        if self._duel.value:
            self.lib.OCG_DestroyDuel(self._duel)
            self._duel = c.c_void_p()
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
