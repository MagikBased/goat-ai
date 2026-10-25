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
    counters: tuple[tuple[int, int], ...] = ()  # (counter type, count) on face-up monsters.
    equipped_to: tuple[int, int] | None = None  # Public target monster slot; card ID may be hidden.


@dataclass(frozen=True)
class TargetSlotView:
    controller: int
    zone: str
    sequence: int


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
    known_opponent_cards: tuple[int, ...] = ()
    restrictions: tuple[str, ...] = ()
    own_extra_deck: tuple[CardView, ...] = ()
    known_opponent_field_cards: tuple[KnownCardView, ...] = ()
    public_reveals: tuple[PublicRevealView, ...] = ()
    disabled_zones: tuple[DisabledZoneView, ...] = ()
    private_reveals: tuple[PrivateRevealView, ...] = ()
    own_main_deck: tuple[int, ...] = ()  # Initial card multiset, never shuffled order.
    known_opponent_hand_cards: tuple[int, ...] = ()  # Publicly tracked multiset, no hand slots.

    def __post_init__(self) -> None:
        if self.viewer not in (0, 1) or self.acting_player not in (0, 1):
            raise ValueError("viewer and acting player must be 0 or 1")
        if any(card.controller != self.viewer for card in self.hand):
            raise ValueError("observation hand must contain viewer's cards only")
        if any(target.controller not in (0, 1)
               or target.zone not in ("monster", "spell_trap")
               or not 0 <= target.sequence < (7 if target.zone == "monster" else 8)
               for link in self.chain for target in link.targets):
            raise ValueError("chain targets must identify public field slots")
        if any(card.controller != self.viewer or card.zone != "extra" or card.code is None
               for card in self.own_extra_deck):
            raise ValueError("own Extra Deck must contain only visible viewer cards")
        if any(card.controller != self.viewer and card.position == "facedown" and card.code is not None
               for card in self.field):
            raise ValueError("opponent facedown identity must be hidden")
        for card in (*self.hand, *self.field, *self.graveyards[0], *self.graveyards[1],
                     *self.banished[0], *self.banished[1], *self.own_extra_deck):
            if (card.zone != "monster" or card.position != "faceup") and (
                    card.attack is not None or card.defense is not None or card.counters):
                raise ValueError("dynamic stats and counters require a face-up monster")
            if ((card.attack is None) != (card.defense is None)
                    or any(kind <= 0 or count <= 0 for kind, count in card.counters)
                    or tuple(sorted(card.counters)) != card.counters):
                raise ValueError("invalid visible monster stats or counters")
            if card.equipped_to is not None and (
                    card.zone != "spell_trap"
                    or len(card.equipped_to) != 2
                    or card.equipped_to[0] not in (0, 1)
                    or not 0 <= card.equipped_to[1] < 7):
                raise ValueError("equip target requires a field Spell or Trap")
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

