"""Only player-visible information belongs in these values."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CardView:
    controller: int
    zone: str
    position: str
    code: int | None = None  # None means identity is hidden from this viewer.
    sequence: int | None = None


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
    chain: tuple[str, ...] = ()
    public_history: tuple[str, ...] = ()
    known_opponent_cards: tuple[int, ...] = ()
    restrictions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.viewer not in (0, 1) or self.acting_player not in (0, 1):
            raise ValueError("viewer and acting player must be 0 or 1")
        if any(card.controller != self.viewer for card in self.hand):
            raise ValueError("observation hand must contain viewer's cards only")
        if any(card.controller != self.viewer and card.position == "facedown" and card.code is not None
               for card in self.field):
            raise ValueError("opponent facedown identity must be hidden")
        if self.opponent_hand_count < 0 or any(n < 0 for n in self.deck_counts):
            raise ValueError("counts must be nonnegative")

