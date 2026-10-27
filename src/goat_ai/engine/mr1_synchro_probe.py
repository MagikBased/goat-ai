"""Small sourced MR1 Synchro protocol fixture, not an Edison simulator."""

from pathlib import Path

from goat_ai.engine.decks import Decklist, read_advanced_restrictions, read_ydk
from goat_ai.engine.edison_decks import validate_edison_deck
from goat_ai.engine.mr1_vanilla_adapter import Mr1VanillaEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.engine.protocol import RulesProfile

JUNK_SYNCHRON = 63977008
JUNK_WARRIOR = 60800381
BLACK_ROSE_DRAGON = 73580471
STARDUST_DRAGON = 44508094
CURSE_OF_DRAGON = 28279543
MIRROR_FORCE = 44095762
BOKOICHI = 8715625
PROBE_ELIGIBLE_IDS = frozenset(VANILLA_DECK) | {
    JUNK_SYNCHRON, JUNK_WARRIOR, BLACK_ROSE_DRAGON, STARDUST_DRAGON,
    CURSE_OF_DRAGON, MIRROR_FORCE, BOKOICHI}


class Mr1SynchroProbeEngine(Mr1VanillaEngine):
    """Allow sourced 2008 Synchro cards inside a narrow MR1 experiment."""

    probe_mode = "mr1_synchro_probe"

    def __init__(self, native_root: str | Path) -> None:
        super().__init__(native_root)
        self.ruleset = RulesProfile(name="mr1-synchro-protocol",
                                    april_2005_banlist=False)

    def _load_deck(self, path: str) -> Decklist:
        deck = read_ydk(path)
        if deck.side or any(code not in (JUNK_WARRIOR, BLACK_ROSE_DRAGON, STARDUST_DRAGON)
                            for code in deck.extra):
            raise ValueError("MR1 Synchro probe allows only Junk Warrior, "
                             "Black Rose Dragon, or Stardust Dragon in Extra, no Side")
        restrictions = read_advanced_restrictions(
            Path(__file__).resolve().parents[3]
            / "configs/historical/edison_2010_03_01_advanced_limits.tsv")
        validate_edison_deck(deck, PROBE_ELIGIBLE_IDS, restrictions,
                             self.root / "database/cards.cdb")
        return deck
