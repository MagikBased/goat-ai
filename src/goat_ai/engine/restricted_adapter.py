"""Real ocgcore adapter for normal-monster decks and selected scripted cards.

This bridge exposes every choice decoded by native_messages. It fails on an
unsupported request; it does not silently hide legal choices or fake rules.
General GOAT card/effect support remains M1 work.
"""

import sqlite3
from pathlib import Path

from goat_ai.actions import Action
from goat_ai.engine.decks import Decklist, read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.engine.native_messages import NativeChoice, decode_decision
from goat_ai.engine.ocgcore_probe import OcgcoreProbe
from goat_ai.engine.protocol import Decision, RulesProfile, SimulatorUnavailable
from goat_ai.replay.fingerprint import sha256_file


class RestrictedOcgcoreEngine:
    supported_spells = frozenset({55144522, 14087893, 504700116})
    supported_monsters = frozenset({11384280})

    def __init__(self, native_root: str | Path,
                 ruleset: RulesProfile | None = None) -> None:
        self.root = Path(native_root)
        self.ruleset = ruleset or RulesProfile()
        self.probe: OcgcoreProbe | None = None
        self._choices: tuple[NativeChoice, ...] = ()
        self._actions: tuple[Action, ...] = ()
        self._last_observation = None

    def _load_deck(self, path: str) -> Decklist:
        deck = read_ydk(path)
        database = self.root / "database/cards.cdb"
        goat_database = self.root / "database/goat-entries.cdb"
        unofficial_database = self.root / "database/cards-unofficial.cdb"
        limits = read_goat_whitelist(self.root / "banlist/GOAT.lflist.conf")
        validate_goat_deck(deck, limits, database, goat_database, unofficial_database,
                           self.ruleset.side_deck_policy)
        if deck.extra or deck.side or len(deck.main) != 40:
            raise SimulatorUnavailable("restricted adapter currently supports a 40-card main deck only")
        with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as connection:
            connection.execute("ATTACH DATABASE ? AS goat",
                               (f"file:{goat_database.resolve()}?mode=ro",))
            connection.execute("ATTACH DATABASE ? AS unofficial",
                               (f"file:{unofficial_database.resolve()}?mode=ro",))
            for code in deck.main:
                row = connection.execute("SELECT type FROM goat.datas WHERE id=?",
                                         (code,)).fetchone()
                if row is None:
                    row = connection.execute("SELECT type FROM main.datas WHERE id=?",
                                             (code,)).fetchone()
                if row is None:
                    row = connection.execute("SELECT type FROM unofficial.datas WHERE id=?",
                                             (code,)).fetchone()
                if row is None or (row[0] != 17 and code not in self.supported_spells
                                   and code not in self.supported_monsters):
                    raise SimulatorUnavailable(
                        f"restricted adapter cannot simulate card {code}; card script is not audited"
                    )
                script_dir = "goat" if code == 504700116 else "official"
                if code in self.supported_spells | self.supported_monsters and not (
                    self.root / f"scripts/{script_dir}/c{code}.lua"
                ).is_file():
                    raise SimulatorUnavailable(f"card {code} script missing; rerun setup_native.py")
        return deck

    def reset(self, deck1: str, deck2: str, seed: int) -> Decision:
        self.close()
        cards1 = self._load_deck(deck1)
        cards2 = self._load_deck(deck2)
        self.probe = OcgcoreProbe(self.root / "build/libocgcore.so",
                                  self.root / "database/cards.cdb", self.root / "scripts")
        try:
            self.probe.first_decision(seed, cards1.main, cards2.main,
                                      cards1.extra, cards2.extra)
            return self._decision()
        except Exception:
            self.close()
            raise

    def _decision(self) -> Decision:
        if self.probe is None or self.probe._pending_message is None:
            raise RuntimeError("no pending native decision")
        try:
            native = decode_decision(self.probe._pending_message)
        except NotImplementedError as exc:
            raise SimulatorUnavailable(f"native request unsupported by restricted adapter: {exc}") from exc
        observation = self.probe.observation(native.player)
        zones = {0x04: "monster", 0x08: "spell_trap", 0x10: "graveyard", 0x20: "banished"}
        visible_cards = (*observation.field, *observation.graveyards[0],
                         *observation.graveyards[1], *observation.banished[0],
                         *observation.banished[1])
        def public_code(code: int, controller: int, location: int,
                        sequence: int) -> int | None:
            if controller == native.player:
                return code
            visible = next((card for card in visible_cards
                            if card.controller == controller
                            and card.zone == zones.get(location)
                            and card.sequence == sequence), None)
            if visible is None:
                raise SimulatorUnavailable("native choice references an unobserved card")
            return visible.code

        actions = []
        for index, choice in enumerate(native.choices):
            kind = choice.kind
            if kind == "change_position" and choice.location == 0x04:
                target = next((card for card in observation.field
                               if card.controller == choice.controller
                               and card.zone == "monster"
                               and card.sequence == choice.sequence), None)
                if target is None:
                    raise SimulatorUnavailable("position choice references an unobserved monster")
                if target.position == "facedown":
                    kind = "flip_summon"
            parameters = {}
            if choice.code is not None:
                code = public_code(choice.code, choice.controller,
                                   choice.location, choice.sequence)
                if code is not None:
                    parameters["code"] = code
            if choice.cards:
                cards = []
                for code, controller, location, sequence in choice.cards:
                    target = {"controller": controller, "location": location,
                              "sequence": sequence}
                    visible_code = public_code(code, controller, location, sequence)
                    if visible_code is not None:
                        target["code"] = visible_code
                    cards.append(target)
                parameters["cards"] = cards
            if choice.location is not None:
                parameters["location"] = choice.location
            if choice.position is not None:
                parameters["position"] = choice.position
            if choice.race is not None:
                parameters["race"] = choice.race
            if choice.prompt_id is not None:
                parameters["prompt_id"] = choice.prompt_id
            if choice.sequence is not None:
                parameters["sequence"] = choice.sequence
            if choice.controller is not None:
                parameters["controller"] = choice.controller
            actions.append(Action(str(index), kind, native.player, parameters))
        self._choices = native.choices
        self._actions = tuple(actions)
        self._last_observation = observation
        return Decision(self._last_observation, self._actions)

    def step(self, action: Action) -> Decision:
        if self.probe is None or action not in self._actions:
            raise ValueError("illegal action or engine not reset")
        index = self._actions.index(action)
        try:
            transition = self.probe.respond(self._choices[index].response)
            if transition.terminal:
                self._choices = ()
                self._actions = ()
                return Decision(self._last_observation, (), terminal=True,
                                winner=transition.winner)
            return self._decision()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.probe is not None:
            self.probe.close()
            self.probe = None
        self._choices = ()
        self._actions = ()

    def replay_manifest(self) -> dict[str, str]:
        """Hash native files and every script loaded during the current duel."""
        if self.probe is None:
            raise RuntimeError("native duel is not active")
        required = (
            "build/libocgcore.so", "database/cards.cdb",
            "database/goat-entries.cdb", "database/cards-unofficial.cdb",
            "banlist/GOAT.lflist.conf",
        )
        result = {name: sha256_file(self.root / name) for name in required}
        result.update({f"scripts/{name}": digest
                       for name, digest in self.probe.loaded_script_sha256.items()})
        return result

