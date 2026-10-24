"""Fail-closed native adapter for probing unaudited GOAT decks.

This accepts whitelist-legal cards, but successful startup does not certify
historical behavior or information safety. Keep it out of training and
competitive evaluation until those properties have regression coverage.
"""

from goat_ai.engine.decks import read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.engine.protocol import SimulatorUnavailable
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine


class ExperimentalOcgcoreEngine(RestrictedOcgcoreEngine):
    def _load_deck(self, path: str) -> tuple[int, ...]:
        deck = read_ydk(path)
        limits = read_goat_whitelist(self.root / "banlist/GOAT.lflist.conf")
        validate_goat_deck(
            deck, limits, self.root / "database/cards.cdb",
            self.root / "database/goat-entries.cdb",
            self.root / "database/cards-unofficial.cdb",
        )
        if len(deck.main) != 40 or deck.extra or deck.side:
            raise SimulatorUnavailable(
                "experimental adapter currently requires a 40-card main deck "
                "with no Extra or Side Deck"
            )
        return deck.main
