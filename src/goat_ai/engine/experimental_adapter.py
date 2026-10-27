"""Fail-closed native adapter for probing unaudited GOAT decks.

This accepts whitelist-legal cards, but successful startup does not certify
historical behavior or information safety. Keep it out of training and
competitive evaluation until those properties have regression coverage.
"""

import struct

from goat_ai.actions import Action
from goat_ai.engine.decks import Decklist, read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.engine.ocgcore_probe import OcgcoreProbe
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine


class ExperimentalOcgcoreEngine(RestrictedOcgcoreEngine):
    def _load_deck(self, path: str) -> Decklist:
        deck = read_ydk(path)
        limits = read_goat_whitelist(self.root / "banlist/GOAT.lflist.conf")
        validate_goat_deck(
            deck, limits, self.root / "database/cards.cdb",
            self.root / "database/goat-entries.cdb",
            self.root / "database/cards-unofficial.cdb",
            self.ruleset.side_deck_policy,
        )
        return deck

    def reset_recorded(self, seed_words: tuple[int, int, int, int],
                       deck1: Decklist, deck2: Decklist):
        """Start a legacy replay with its recorded Deck order and native RNG words."""
        self.close()
        limits = read_goat_whitelist(self.root / "banlist/GOAT.lflist.conf")
        for deck in (deck1, deck2):
            validate_goat_deck(
                deck, limits, self.root / "database/cards.cdb",
                self.root / "database/goat-entries.cdb",
                self.root / "database/cards-unofficial.cdb",
                self.ruleset.side_deck_policy,
            )
        self.probe = OcgcoreProbe(self.root / "build/libocgcore.so",
                                  self.root / "database/cards.cdb", self.root / "scripts")
        try:
            self.probe.first_replay_decision(seed_words, deck1.main, deck2.main,
                                             deck1.extra, deck2.extra)
            return self._decision()
        except Exception:
            self.close()
            raise

    def action_for_recorded_response(self, response: bytes) -> Action:
        """Find the unique public action that emits one saved native response."""
        matches = [action for choice, action in zip(self._choices, self._actions, strict=True)
                   if (struct.pack("<I", choice.response & 0xffffffff)
                       if isinstance(choice.response, int) else choice.response) == response]
        if len(matches) != 1:
            raise ValueError("recorded response has no unique public action")
        return matches[0]

    def action_for_selection_index(self, index: int) -> Action:
        """Find one staged public pick by the native candidate index."""
        matches = [action for choice, action in zip(self._choices, self._actions, strict=True)
                   if choice.kind in ("select_card", "place_zones", "disable_zones")
                   and choice.response == index]
        if len(matches) != 1:
            raise ValueError("recorded selection index has no unique public action")
        return matches[0]

    def recorded_selection_in_progress(self) -> bool:
        return self._selection_indices is not None
