"""Strict decoding of selected ocgcore API-11 decision messages.

These are internal protocol values. They must not be handed to an agent until
the observation and action visibility boundary is audited.
"""

import struct
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, permutations
from math import comb, factorial

from goat_ai.engine.ocgcore_probe import MSG_SELECT_CHAIN, MSG_SELECT_IDLECMD

# Preserve the existing flat action contract through the observed 3,003-way
# Return prompt. Larger card selections use staged, linear-size choices.
MAX_CARD_SELECTION_COMBINATIONS = 4096
MAX_SUM_SELECTION_COMBINATIONS = 4096
MAX_ZONE_SELECTION_COMBINATIONS = 2048


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
    prompt_id: int | None = None
    zones: tuple[tuple[int, int, int], ...] = ()
    attribute: int | None = None
    number: int | None = None
    announced_card: int | None = None


@dataclass(frozen=True)
class NativeCardSelection:
    cards: tuple[tuple[int, int, int, int], ...]
    minimum: int
    maximum: int
    cancelable: bool

    def accepts(self, response: int | bytes) -> bool:
        """Validate one complete native choice without enumerating subsets."""
        if isinstance(response, int):
            return self.cancelable and response == -1
        if not isinstance(response, bytes) or len(response) < 8:
            return False
        kind, size = struct.unpack_from("<II", response)
        if kind != 0 or not self.minimum <= size <= self.maximum \
                or len(response) != 8 + 4 * size:
            return False
        indices = struct.unpack_from(f"<{size}I", response, 8)
        return all(index < len(self.cards) for index in indices) \
            and tuple(sorted(set(indices))) == indices


@dataclass(frozen=True)
class NativeSumSelection:
    """Implicit required cards plus optional native-index choices."""

    required: tuple[tuple[int, int, int, int, int], ...]
    cards: tuple[tuple[int, int, int, int, int], ...]
    minimum: int
    maximum: int
    target: int
    mode: int

    def accepts(self, response: int | bytes) -> bool:
        if not isinstance(response, bytes) or len(response) < 8:
            return False
        kind, size = struct.unpack_from("<II", response)
        if kind != 0 or len(response) != 8 + 4 * size:
            return False
        indices = struct.unpack_from(f"<{size}I", response, 8)
        return self.accepts_indices(indices)

    def selected_cards(self, indices: tuple[int, ...]) -> tuple[tuple[int, int, int, int], ...]:
        return tuple(card[:4] for card in self.required) + tuple(
            self.cards[index][:4] for index in indices)

    def accepts_indices(self, indices: tuple[int, ...]) -> bool:
        if (not self.minimum <= len(indices) <= self.maximum
                or any(index < 0 or index >= len(self.cards) for index in indices)
                or tuple(sorted(set(indices))) != indices):
            return False
        params = tuple(card[4] for card in self.required) + tuple(
            self.cards[index][4] for index in indices)
        if not params:
            return False
        if self.mode == 0:
            @lru_cache(None)
            def exact(index: int, remaining: int) -> bool:
                lower, higher = params[index] & 0xffff, params[index] >> 16
                if index == len(params) - 1:
                    return remaining in (lower, higher)
                return ((remaining > lower and exact(index + 1, remaining - lower))
                        or (higher > 0 and remaining > higher
                            and exact(index + 1, remaining - higher)))
            return exact(0, self.target)
        smallest = [min(param & 0xffff, param >> 16)
                    if param >> 16 else param & 0xffff for param in params]
        largest = [max(param & 0xffff, param >> 16) for param in params]
        return sum(largest) >= self.target and sum(smallest) - min(smallest) < self.target

    def has_completion(self, prefix: tuple[int, ...]) -> bool:
        """Check whether a sorted prefix can finish without listing all subsets."""
        if (len(prefix) > self.maximum
                or any(index < 0 or index >= len(self.cards) for index in prefix)
                or tuple(sorted(set(prefix))) != prefix):
            return False
        if self.accepts_indices(prefix):
            return True
        start = prefix[-1] + 1 if prefix else 0
        if len(prefix) >= self.maximum or start >= len(self.cards):
            return False
        fixed = (*self.required, *(self.cards[index] for index in prefix))
        if self.mode == 0:
            remaining = {self.target}
            for card in fixed:
                lower, higher = card[4] & 0xffff, card[4] >> 16
                values = (lower, higher) if higher else (lower,)
                remaining = {total - value for total in remaining
                             for value in values if total > value}
                if not remaining:
                    return False

            @lru_cache(None)
            def search(index: int, count: int, total: int) -> bool:
                if count >= self.maximum:
                    return False
                for candidate in range(index, len(self.cards)):
                    param = self.cards[candidate][4]
                    low, high = param & 0xffff, param >> 16
                    for value in ((low, high) if high else (low,)):
                        if total == value and count + 1 >= self.minimum:
                            return True
                        if total > value and search(candidate + 1, count + 1,
                                                    total - value):
                            return True
                return False

            return any(search(start, len(prefix), total) for total in remaining)

        low_sum = high_sum = 0
        smallest = 0x10000
        for card in fixed:
            low, high = card[4] & 0xffff, card[4] >> 16
            minimum = min(low, high) if high else low
            low_sum += minimum
            high_sum += max(low, high)
            smallest = min(smallest, minimum)

        @lru_cache(None)
        def search(index: int, count: int, low_total: int,
                   high_total: int, min_value: int) -> bool:
            if count >= self.maximum or low_total - min_value >= self.target:
                return False
            for candidate in range(index, len(self.cards)):
                param = self.cards[candidate][4]
                low, high = param & 0xffff, param >> 16
                minimum = min(low, high) if high else low
                next_low = low_total + minimum
                next_high = high_total + max(low, high)
                next_min = min(min_value, minimum)
                if (count + 1 >= self.minimum and next_high >= self.target
                        and next_low - next_min < self.target):
                    return True
                if search(candidate + 1, count + 1, next_low, next_high, next_min):
                    return True
            return False

        return search(start, len(prefix), low_sum, high_sum, smallest)


@dataclass(frozen=True)
class NativeZoneSelection:
    zones: tuple[tuple[int, int, int], ...]
    count: int
    kind: str

    def accepts(self, response: int | bytes) -> bool:
        if not isinstance(response, bytes) or len(response) != 3 * self.count:
            return False
        selected = tuple(tuple(response[start:start + 3])
                         for start in range(0, len(response), 3))
        return len(set(selected)) == self.count and all(zone in self.zones for zone in selected)


@dataclass(frozen=True)
class NativeDecision:
    player: int
    choices: tuple[NativeChoice, ...]
    card_selection: NativeCardSelection | None = None
    sum_selection: NativeSumSelection | None = None
    zone_selection: NativeZoneSelection | None = None


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


def decode_decision(message: bytes,
                    announcement_codes: tuple[int, ...] | None = None) -> NativeDecision:
    """Decode supported native choices; fail on every other request type."""
    reader = _Reader(message)
    kind = reader.integer(1)
    if kind == 12:  # MSG_SELECT_EFFECTYN
        player = reader.integer(1)
        code = reader.integer(4)
        controller = reader.integer(1)
        location = reader.integer(1)
        sequence = reader.integer(4)
        reader.integer(4)  # position
        prompt_id = reader.integer(8)
        reader.finish()
        if player not in (0, 1) or controller not in (0, 1):
            raise ValueError("invalid effect yes/no player or controller")
        return NativeDecision(player, (
            NativeChoice("no", 0, code, controller, location, sequence,
                         prompt_id=prompt_id),
            NativeChoice("yes", 1, code, controller, location, sequence,
                         prompt_id=prompt_id),
        ))
    if kind == 13:  # MSG_SELECT_YESNO
        player = reader.integer(1)
        prompt_id = reader.integer(8)
        reader.finish()
        if player not in (0, 1):
            raise ValueError("invalid yes/no player")
        return NativeDecision(player, (NativeChoice("no", 0, prompt_id=prompt_id),
                                       NativeChoice("yes", 1, prompt_id=prompt_id)))
    if kind == 14:  # MSG_SELECT_OPTION
        player = reader.integer(1)
        count = reader.integer(1)
        if player not in (0, 1) or not count:
            raise ValueError("invalid option selection")
        choices = tuple(NativeChoice("select_option", index,
                                     prompt_id=reader.integer(8))
                        for index in range(count))
        reader.finish()
        return NativeDecision(player, choices)
    if kind == 143:  # MSG_ANNOUNCE_NUMBER
        player = reader.integer(1)
        count = reader.integer(1)
        if player not in (0, 1) or not count:
            raise ValueError("invalid number announcement")
        choices = tuple(NativeChoice("announce_number", index,
                                     number=reader.integer(8))
                        for index in range(count))
        reader.finish()
        return NativeDecision(player, choices)
    if kind == 142:  # MSG_ANNOUNCE_CARD
        player = reader.integer(1)
        count = reader.integer(1)
        options = tuple(reader.integer(8) for _ in range(count))
        reader.finish()
        is_type = 0x4000010200000000
        and_op = 0x4000000400000000
        not_op = 0x4000000700000000
        extra = 0x4802040
        supported = (
            (1, is_type),  # Question: monster names.
            (extra, is_type, not_op),  # D.D. Designator: non-Extra names.
            (7, is_type),  # Prohibition: monster, Spell, or Trap names.
            (extra, is_type, 1, is_type, and_op, not_op),  # Mind Crush.
            (1, is_type, extra, is_type, not_op, and_op),  # Dark Designator.
        )
        if player not in (0, 1) or options not in supported:
            raise NotImplementedError(
                f"card announcement expression is not supported: {options!r}")
        if not announcement_codes:
            raise NotImplementedError("historical card announcement catalog is unavailable")
        return NativeDecision(player, tuple(
            NativeChoice("announce_card", code, announced_card=code)
            for code in announcement_codes))
    if kind in (21, 25):  # MSG_SORT_CHAIN / MSG_SORT_CARD
        player = reader.integer(1)
        count = reader.integer(4)
        if player not in (0, 1) or not 1 <= count <= 6 or factorial(count) > 2048:
            raise NotImplementedError("card or chain sorting bounds are not supported")
        cards = tuple((reader.integer(4), reader.integer(1), reader.integer(4),
                       reader.integer(4)) for _ in range(count))
        reader.finish()
        if any(controller not in (0, 1) or location not in (1, 2, 4, 8, 16, 32, 64)
               for _, controller, location, _ in cards):
            raise ValueError("invalid card sorting location")
        return NativeDecision(player, tuple(
            NativeChoice("sort_cards", bytes(order),
                         cards=tuple(cards[index] for index in order))
            for order in permutations(range(count))))
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
    if kind == 141:  # MSG_ANNOUNCE_ATTRIB
        player = reader.integer(1)
        count = reader.integer(1)
        available = reader.integer(4)
        reader.finish()
        bits = tuple(1 << index for index in range(32) if available & (1 << index))
        if player not in (0, 1) or not 1 <= count <= len(bits) or available & ~0x7F:
            raise ValueError("invalid attribute announcement")
        if comb(len(bits), count) > 2048:
            raise NotImplementedError("attribute announcement has too many combinations")
        choices = tuple(NativeChoice("announce_attribute", struct.pack("<I", mask),
                                     attribute=mask)
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
        if option_count > MAX_CARD_SELECTION_COMBINATIONS:
            reader.finish()
            selection = NativeCardSelection(tuple(cards), minimum, maximum,
                                            bool(cancelable))
            choices = tuple(NativeChoice("select_card", index, code, controller,
                                         location, sequence)
                            for index, (code, controller, location, sequence)
                            in enumerate(cards))
            return NativeDecision(player, choices, selection)
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
    if kind == 23:  # MSG_SELECT_SUM
        player = reader.integer(1)
        mode = reader.integer(1)
        target_sum = reader.integer(4)
        minimum = reader.integer(4)
        maximum = reader.integer(4)
        required_count = reader.integer(4)
        if player not in (0, 1) or mode not in (0, 1):
            raise NotImplementedError("sum selection mode unsupported")
        if required_count > (len(reader.data) - reader.offset - 4) // 18:
            raise ValueError("truncated mandatory sum cards")
        required = []
        for _ in range(required_count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(4)
            reader.integer(4)  # position
            sum_param = reader.integer(4)
            required.append((code, controller, location, sequence, sum_param))
        count = reader.integer(4)
        upper = min(maximum, count) if mode == 0 else count
        if count > (len(reader.data) - reader.offset) // 18:
            raise ValueError("truncated optional sum cards")
        if (not count and not required) or minimum > upper or target_sum <= 0:
            raise ValueError("invalid sum selection bounds")
        cards = []
        for _ in range(count):
            code = reader.integer(4)
            controller = reader.integer(1)
            location = reader.integer(1)
            sequence = reader.integer(4)
            reader.integer(4)  # position
            sum_param = reader.integer(4)
            cards.append((code, controller, location, sequence, sum_param))
        reader.finish()
        selection = NativeSumSelection(tuple(required), tuple(cards), minimum,
                                       upper, target_sum, mode)
        option_count = sum(comb(count, size) for size in range(minimum, upper + 1))
        if option_count > MAX_SUM_SELECTION_COMBINATIONS:
            choices = tuple(NativeChoice("select_card", index, code, controller,
                                         location, sequence)
                            for index, (code, controller, location, sequence, _)
                            in enumerate(cards))
            if not selection.has_completion(()):
                raise ValueError("sum selection has no valid responses")
            return NativeDecision(player, choices, sum_selection=selection)

        choices = []
        for size in range(minimum, upper + 1):
            for indices in combinations(range(count), size):
                if not selection.accepts_indices(indices):
                    continue
                response = struct.pack("<II", 0, size) + struct.pack(f"<{size}I", *indices)
                selected = selection.selected_cards(indices)
                if size == 1 and not required:
                    code, controller, location, sequence = selected[0]
                    choices.append(NativeChoice("select_card", response, code,
                                                controller, location, sequence))
                else:
                    choices.append(NativeChoice("select_cards", response, cards=selected))
        if not choices:
            raise ValueError("sum selection has no valid responses")
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
    if kind in (18, 24):  # MSG_SELECT_PLACE / MSG_SELECT_DISFIELD
        player = reader.integer(1)
        count = reader.integer(1)
        forbidden = reader.integer(4)
        reader.finish()
        if player not in (0, 1) or not count:
            raise ValueError("invalid field-zone selection")
        zones = []
        for group in range(4):
            controller = player if group < 2 else 1 - player
            location = 0x4 if group % 2 == 0 else 0x8
            for sequence in range(7 if location == 0x4 else 8):
                if not forbidden & (1 << (group * 8 + sequence)):
                    zones.append((controller, location, sequence))
        if count > len(zones):
            raise ValueError("field-zone selection has too few legal zones")
        if comb(len(zones), count) > MAX_ZONE_SELECTION_COMBINATIONS:
            selection = NativeZoneSelection(tuple(zones), count, "place_zones" if kind == 18
                                            else "disable_zones")
            return NativeDecision(player, tuple(NativeChoice(
                selection.kind, index, zones=(zone,))
                for index, zone in enumerate(zones)), zone_selection=selection)
        choices = []
        for selected in combinations(zones, count):
            response = bytes(value for zone in selected for value in zone)
            if count == 1:
                controller, location, sequence = selected[0]
                choices.append(NativeChoice(
                    "place" if kind == 18 else "disable_zone", response,
                    controller=controller, location=location, sequence=sequence))
            else:
                choices.append(NativeChoice(
                    "place_zones" if kind == 18 else "disable_zones", response,
                    zones=selected))
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
