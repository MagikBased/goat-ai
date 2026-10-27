"""Small sourced MR1 Synchro protocol fixture, not an Edison simulator."""

from pathlib import Path

from goat_ai.engine.decks import Decklist, read_advanced_restrictions, read_ydk
from goat_ai.engine.edison_decks import validate_edison_deck
from goat_ai.engine.mr1_vanilla_adapter import Mr1VanillaEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.engine.protocol import RulesProfile

JUNK_SYNCHRON = 63977008
JUNK_WARRIOR = 60800381
BOKOICHI = 8715625
PROBE_ELIGIBLE_IDS = frozenset(VANILLA_DECK) | {JUNK_SYNCHRON, JUNK_WARRIOR, BOKOICHI}


class Mr1SynchroProbeEngine(Mr1VanillaEngine):
    """Allow one 2008 Synchro pair inside a narrow MR1 decision experiment."""

    probe_mode = "mr1_synchro_probe"

    def __init__(self, native_root: str | Path) -> None:
        super().__init__(native_root)
        self.ruleset = RulesProfile(name="mr1-synchro-protocol",
                                    april_2005_banlist=False)

    def _load_deck(self, path: str) -> Decklist:
        deck = read_ydk(path)
        if deck.side or any(code != JUNK_WARRIOR for code in deck.extra):
            raise ValueError("MR1 Synchro probe allows only Junk Warrior in Extra, no Side")
        restrictions = read_advanced_restrictions(
            Path(__file__).resolve().parents[3]
            / "configs/historical/edison_2010_03_01_advanced_limits.tsv")
        validate_edison_deck(deck, PROBE_ELIGIBLE_IDS, restrictions,
                             self.root / "database/cards.cdb")
        return deck
