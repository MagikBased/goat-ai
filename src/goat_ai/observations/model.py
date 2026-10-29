"""Only player-visible information belongs in these values."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CardView:
    controller: int
    zone: str
    position: str
    code: int | None = None  # None means identity is hidden from this viewer.
    sequence: int | None = None
    orientation: str | None = None  # attack/defense for monsters on the field.
    attack: int | None = None  # Current visible ATK; never set for face-down cards.
    defense: int | None = None  # Current visible DEF.
    counters: tuple[tuple[int, int], ...] = ()  # (type, count) on face-up field cards.
    equipped_to: tuple[int, int] | None = None  # Public target monster slot; card ID may be hidden.
    race: int | None = None  # Current Type mask of a face-up monster, including field effects.
    owner: int | None = None  # Original owner of a face-up field monster; public in a duel.
    faceup_turns: int | None = None  # Turn boundaries since becoming face-up on the field.


@dataclass(frozen=True)
class TargetSlotView:
    controller: int
    zone: str
    sequence: int


@dataclass(frozen=True)
class PublicAttackView:
    """Public field slots in an announced attack; no target card identity."""

    turn: int
    attacker: TargetSlotView
    target: TargetSlotView | None = None  # None for a direct attack.


@dataclass(frozen=True)
class PendingSummonView:
    """Public monster being summoned while a negation response is offered."""

    kind: str  # normal, flip, or special
    controller: int
    sequence: int
    code: int | None  # None for a face-down Special Summon.


@dataclass(frozen=True)
class ChainLinkView:
    index: int
    card_code: int
    controller: int
    location: int
    sequence: int
    targets: tuple[TargetSlotView, ...] = ()


@dataclass(frozen=True)
class KnownCardView:
    """Publicly seen opponent card that is now face-down at this field slot."""

    controller: int
    zone: str
    sequence: int
    code: int


@dataclass(frozen=True)
class PublicRevealView:
    """Cards publicly revealed from one player's Deck at a decision boundary."""

    turn: int
    player: int
    zone: str
    codes: tuple[int, ...]


@dataclass(frozen=True)
class DisabledZoneView:
    """A field slot disabled by a public, currently active effect."""

    player: int
    zone: str
    sequence: int


@dataclass(frozen=True)
class RevealedCardView:
    code: int
    controller: int
    location: int


@dataclass(frozen=True)
class PrivateRevealView:
    """A multiset of cards shown only to the addressed player."""

    turn: int
    recipient: int
    cards: tuple[RevealedCardView, ...]


@dataclass(frozen=True)
class Observation:
    viewer: int
    acting_player: int
    turn: int
    phase: str
    life_points: tuple[int, int]
    hand: tuple[CardView, ...]
    field: tuple[CardView, ...]
    graveyards: tuple[tuple[CardView, ...], tuple[CardView, ...]]
    banished: tuple[tuple[CardView, ...], tuple[CardView, ...]]
    opponent_hand_count: int
    deck_counts: tuple[int, int]
    extra_deck_counts: tuple[int, int]
    chain: tuple[ChainLinkView, ...] = ()
    public_history: tuple[str, ...] = ()
    recent_attacks: tuple[PublicAttackView, ...] = ()
    known_opponent_cards: tuple[int, ...] = ()
    restrictions: tuple[str, ...] = ()
    own_extra_deck: tuple[CardView, ...] = ()
    known_opponent_field_cards: tuple[KnownCardView, ...] = ()
    public_reveals: tuple[PublicRevealView, ...] = ()
    disabled_zones: tuple[DisabledZoneView, ...] = ()
    private_reveals: tuple[PrivateRevealView, ...] = ()
    own_main_deck: tuple[int, ...] = ()  # Initial card multiset, never shuffled order.
    known_opponent_hand_cards: tuple[int, ...] = ()  # Publicly tracked multiset, no hand slots.
    pending_attack: TargetSlotView | None = None  # Own attacker while choosing its target.
    turn_player: int | None = None  # Current turn owner; differs from actor during responses.
    pending_summon: PendingSummonView | None = None

    def __post_init__(self) -> None:
        if self.viewer not in (0, 1) or self.acting_player not in (0, 1):
            raise ValueError("viewer and acting player must be 0 or 1")
        if self.turn_player is not None and (
                type(self.turn_player) is not int or self.turn_player not in (0, 1)):
            raise ValueError("turn player must be 0 or 1 when recorded")
        if self.pending_summon is not None and (
                self.pending_summon.kind not in ("normal", "flip", "special")
                or self.pending_summon.controller not in (0, 1)
                or not 0 <= self.pending_summon.sequence < 7
                or self.pending_summon.code is not None
                and (type(self.pending_summon.code) is not int
                     or self.pending_summon.code <= 0)):
            raise ValueError("invalid pending summon")
        if any(card.controller != self.viewer for card in self.hand):
            raise ValueError("observation hand must contain viewer's cards only")
        if self.pending_attack is not None and (
                self.viewer != self.acting_player
                or self.pending_attack.controller != self.viewer
                or self.pending_attack.zone != "monster"
                or not 0 <= self.pending_attack.sequence < 7
                or not any(card.controller == self.viewer and card.zone == "monster"
                           and card.sequence == self.pending_attack.sequence
                           and card.position == "faceup" for card in self.field)):
            raise ValueError("pending attack must identify the acting player's face-up monster")
        if any(target.controller not in (0, 1)
               or target.zone not in ("monster", "spell_trap")
               or not 0 <= target.sequence < (7 if target.zone == "monster" else 8)
               for link in self.chain for target in link.targets):
            raise ValueError("chain targets must identify public field slots")
        if len(self.recent_attacks) > 32 or any(
               type(attack.turn) is not int or not 1 <= attack.turn <= self.turn
               or attack.attacker.zone != "monster"
               or attack.attacker.controller not in (0, 1)
               or not 0 <= attack.attacker.sequence < 7
               or attack.target is not None and (
                   attack.target.zone != "monster"
                   or attack.target.controller not in (0, 1)
                   or not 0 <= attack.target.sequence < 7)
               for attack in self.recent_attacks):
            raise ValueError("recent attacks must identify public monster slots")
        if any(card.controller != self.viewer or card.zone != "extra" or card.code is None
               for card in self.own_extra_deck):
            raise ValueError("own Extra Deck must contain only visible viewer cards")
        if any(card.controller != self.viewer and card.position == "facedown" and card.code is not None
               for card in self.field):
            raise ValueError("opponent facedown identity must be hidden")
        if self.pending_summon is not None:
            pending_card = next((card for card in self.field
                                 if card.zone == "monster"
                                 and card.controller == self.pending_summon.controller
                                 and card.sequence == self.pending_summon.sequence), None)
            if (pending_card is None or self.pending_summon.code is not None
                    and (pending_card.position != "faceup"
                         or pending_card.code != self.pending_summon.code)):
                raise ValueError("pending summon must identify a visible field slot")
        for card in (*self.hand, *self.field, *self.graveyards[0], *self.graveyards[1],
                     *self.banished[0], *self.banished[1], *self.own_extra_deck):
            if (card.zone != "monster" or card.position != "faceup") and (
                    card.attack is not None or card.defense is not None
                    or card.race is not None or card.owner is not None):
                raise ValueError("dynamic monster data require a face-up monster")
            if card.counters and (card.zone not in ("monster", "spell_trap")
                                  or card.position != "faceup"):
                raise ValueError("counters require a face-up field card")
            if ((card.attack is None) != (card.defense is None)
                    or (card.race is not None and (type(card.race) is not int
                                                   or not 0 < card.race < 1 << 64))
                    or (card.owner is not None and
                        (type(card.owner) is not int or card.owner not in (0, 1)))
                    or any(kind <= 0 or count <= 0 for kind, count in card.counters)
                    or tuple(sorted(card.counters)) != card.counters):
                raise ValueError("invalid visible monster stats or counters")
            if card.equipped_to is not None and (
                    card.zone != "spell_trap"
                    or len(card.equipped_to) != 2
                    or card.equipped_to[0] not in (0, 1)
                    or not 0 <= card.equipped_to[1] < 7):
                raise ValueError("equip target requires a field Spell or Trap")
            if card.faceup_turns is not None and (
                    card.zone not in ("monster", "spell_trap")
                    or card.position != "faceup"
                    or type(card.faceup_turns) is not int
                    or not 0 <= card.faceup_turns <= self.turn):
                raise ValueError("face-up age requires a public field card")
        facedown_slots = {(card.controller, card.zone, card.sequence)
                          for card in self.field if card.controller != self.viewer
                          and card.position == "facedown"}
        known_slots = [(card.controller, card.zone, card.sequence)
                       for card in self.known_opponent_field_cards]
        if (len(known_slots) != len(set(known_slots))
                or any(slot not in facedown_slots or card.code <= 0
                       for slot, card in zip(known_slots, self.known_opponent_field_cards))):
            raise ValueError("known opponent card must match one face-down field slot")
        if any(reveal.turn < 0 or reveal.player not in (0, 1) or reveal.zone != "deck_top"
               or not reveal.codes or any(code <= 0 for code in reveal.codes)
               for reveal in self.public_reveals):
            raise ValueError("invalid public Deck reveal")
        disabled_slots = [(slot.player, slot.zone, slot.sequence)
                          for slot in self.disabled_zones]
        if len(disabled_slots) != len(set(disabled_slots)) or any(
                slot.player not in (0, 1) or slot.zone not in ("monster", "spell_trap")
                or not 0 <= slot.sequence < (7 if slot.zone == "monster" else 8)
                for slot in self.disabled_zones):
            raise ValueError("invalid disabled field zone")
        if any(reveal.turn < 0 or reveal.recipient != self.viewer or not reveal.cards
               or any(card.code <= 0 or card.controller not in (0, 1)
                      or not 0 <= card.location <= 255 for card in reveal.cards)
               for reveal in self.private_reveals):
            raise ValueError("private reveal must belong to the observation viewer")
        if (self.own_main_deck != tuple(sorted(self.own_main_deck))
                or any(code <= 0 for code in self.own_main_deck)):
            raise ValueError("own Main Deck must be an unordered card multiset")
        if self.opponent_hand_count < 0 or any(n < 0 for n in self.deck_counts):
            raise ValueError("counts must be nonnegative")
        if (len(self.known_opponent_hand_cards) > self.opponent_hand_count
                or tuple(sorted(self.known_opponent_hand_cards))
                != self.known_opponent_hand_cards
                or any(code <= 0 for code in self.known_opponent_hand_cards)):
            raise ValueError("known opponent hand must be a valid unordered subset")

