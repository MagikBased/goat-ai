"""MR1 protocol experiment for Normal Monster decks; not an Edison simulator."""

import sqlite3
from collections import Counter
from pathlib import Path

from goat_ai.engine.decks import Decklist, read_ydk
from goat_ai.engine.ocgcore_probe import OcgcoreProbe
from goat_ai.engine.protocol import Decision, RulesProfile
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.replay.fingerprint import sha256_unchanged_file


class Mr1VanillaEngine(RestrictedOcgcoreEngine):
    """Exercise complete native MR1 duels without GOAT card/script overrides.

    The Main Deck is restricted to 40–60 Normal Monsters from the pinned
    database, with no Extra or Side Deck. This is only a decision/replay probe:
    it does not check the 2010 release pool or establish Edison correctness.
    """

    def __init__(self, native_root: str | Path) -> None:
        self.root = Path(native_root)
        self.ruleset = RulesProfile(name="mr1-vanilla-protocol",
                                    april_2005_banlist=False)
        self.probe: OcgcoreProbe | None = None
        self._choices = ()
        self._actions = ()
        self._last_observation = None
        self._selection_indices = None

    def _load_deck(self, path: str) -> Decklist:
        deck = read_ydk(path)
        if not 40 <= len(deck.main) <= 60 or deck.extra or deck.side:
            raise ValueError("MR1 vanilla probe needs 40–60 Main Deck cards and empty Extra/Side")
        with sqlite3.connect(
            f"file:{(self.root / 'database/cards.cdb').resolve()}?mode=ro", uri=True,
        ) as connection:
            counts: Counter[int] = Counter()
            for code in deck.main:
                row = connection.execute(
                    "SELECT alias, type FROM datas WHERE id=?", (code,),
                ).fetchone()
                if row is None or row[1] != 17:
                    raise ValueError(f"MR1 vanilla probe requires pinned Normal Monster: {code}")
                counts[row[0] or code] += 1
                if counts[row[0] or code] > 3:
                    raise ValueError(f"MR1 vanilla probe exceeds three copies: {code}")
        return deck

    def reset(self, deck1: str, deck2: str, seed: int) -> Decision:
        self.close()
        cards1 = self._load_deck(deck1)
        cards2 = self._load_deck(deck2)
        self.probe = OcgcoreProbe(self.root / "build/libocgcore.so",
                                  self.root / "database/cards.cdb",
                                  self.root / "scripts", mode="mr1_vanilla")
        try:
            self.probe.first_decision(seed, cards1.main, cards2.main)
            return self._decision()
        except Exception:
            self.close()
            raise

    def replay_manifest(self) -> dict[str, str]:
        if self.probe is None:
            raise RuntimeError("native duel is not active")
        required = ("build/libocgcore.so", "database/cards.cdb")
        result = {name: sha256_unchanged_file(self.root / name) for name in required}
        result.update({f"scripts/{name}": digest
                       for name, digest in self.probe.loaded_script_sha256.items()})
        return result
