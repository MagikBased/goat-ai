"""Real ocgcore adapter for normal-monster decks and selected scripted cards.

This bridge exposes every choice decoded by native_messages. It fails on an
unsupported request; it does not silently hide legal choices or fake rules.
General GOAT card/effect support remains M1 work.
"""

import json
import sqlite3
import struct
from dataclasses import replace
from pathlib import Path

from goat_ai.actions import Action
from goat_ai.engine.decks import Decklist, read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.engine.native_messages import NativeChoice
from goat_ai.engine.ocgcore_probe import OcgcoreProbe
from goat_ai.engine.protocol import Decision, RulesProfile, SimulatorUnavailable
from goat_ai.observations import TargetSlotView
from goat_ai.replay.fingerprint import sha256_unchanged_file


class RestrictedOcgcoreEngine:
    supported_spells = frozenset({55144522, 14087893, 504700116})
    supported_monsters = frozenset({11384280})

    def __init__(self, native_root: str | Path,
                 ruleset: RulesProfile | None = None) -> None:
        self.root = Path(native_root)
        self.ruleset = ruleset or RulesProfile()
        supported = RulesProfile()
        if (self.ruleset.name != supported.name
                or self.ruleset.april_2005_banlist is not True
                or self.ruleset.first_turn_draw is not True
                or self.ruleset.obsolete_ignition_priority is not True
                or self.ruleset.side_deck_policy not in ("historical", "community")):
            raise ValueError("native GOAT adapter does not support the requested rules profile")
        self.probe: OcgcoreProbe | None = None
        self._choices: tuple[NativeChoice, ...] = ()
        self._actions: tuple[Action, ...] = ()
        self._last_observation = None
        self._selection_indices: tuple[int, ...] | None = None

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

    def _decision(self, pending_attack: TargetSlotView | None = None) -> Decision:
        if self.probe is None or self.probe._pending_message is None:
            raise RuntimeError("no pending native decision")
        try:
            native = self.probe.decode_pending()
        except NotImplementedError as exc:
            raise SimulatorUnavailable(f"native request unsupported by restricted adapter: {exc}") from exc
        if native.sum_selection is not None:
            selection = native.sum_selection
            if self._selection_indices is None:
                self._selection_indices = ()
            selected = self._selection_indices
            selected_cards = selection.selected_cards(selected)
            last = selected[-1] if selected else -1
            choices = [replace(choice, cards=selected_cards)
                       for choice in native.choices
                       if choice.response > last
                       and selection.has_completion((*selected, choice.response))]
            if selection.accepts_indices(selected):
                choices.append(NativeChoice(
                    "finish_selection", self._card_selection_response(selected),
                    cards=selected_cards))
            if not choices:
                raise SimulatorUnavailable("staged sum selection has no legal continuation")
            native = replace(native, choices=tuple(choices))
        elif native.card_selection is not None:
            selection = native.card_selection
            if self._selection_indices is None:
                self._selection_indices = ()
            selected = self._selection_indices
            selected_cards = tuple(selection.cards[index] for index in selected)
            choices = ([replace(choice, cards=selected_cards)
                        for choice in native.choices if choice.response not in selected]
                       if len(selected) < selection.maximum else [])
            if len(selected) >= selection.minimum:
                choices.append(NativeChoice(
                    "finish_selection", self._card_selection_response(selected),
                    cards=selected_cards))
            if selection.cancelable:
                choices.append(NativeChoice("cancel", -1))
            native = replace(native, choices=tuple(choices))
        else:
            self._selection_indices = None
        observation = self.probe.observation(native.player)
        if pending_attack is not None and native.player == pending_attack.controller \
                and any(choice.kind == "select_card" and choice.location == 0x04
                        for choice in native.choices):
            observation = replace(observation, pending_attack=pending_attack)
        if any(link.card_code == 38723936 and link.controller != native.player
               for link in observation.chain):
            # Question forbids inspecting its controller's Graveyard at the
            # announcement. Previously visible cards remain available to an
            # agent only through its own memory of earlier decisions.
            hidden = 1 - native.player
            graveyards = list(observation.graveyards)
            graveyards[hidden] = tuple(replace(card, code=None, position="hidden")
                                       for card in graveyards[hidden])
            observation = replace(observation, graveyards=tuple(graveyards))
        zones = {0x04: "monster", 0x08: "spell_trap", 0x10: "graveyard", 0x20: "banished"}
        visible_cards = (*observation.field, *observation.graveyards[0],
                         *observation.graveyards[1], *observation.banished[0],
                         *observation.banished[1])
        blind_opponent_hand_choice = (bool(native.choices)
                                      and all(choice.kind == "select_card"
                                              and choice.location == 0x02
                                              and choice.controller == 1 - native.player
                                              for choice in native.choices))
        def public_code(code: int, controller: int, location: int,
                        sequence: int) -> int | None:
            if controller == native.player:
                return code
            if location == 0x02:
                # A hand choice is legal to expose only after a reveal
                # addressed to the acting player in this native transition.
                # Exchange and Dragged Down can choose after a response window;
                # retain the addressed reveal while that chain remains open.
                persistent_reveal = any(link.card_code in (5556668, 16435215)
                                        for link in observation.chain)
                reveals = (observation.private_reveals if persistent_reveal else
                           self.probe._decision_private_reveals)
                reveal = next((event for event in reversed(reveals)
                               if event.recipient == native.player
                               and event.turn == observation.turn and any(
                                   card.controller == controller and card.location == location
                                   for card in event.cards)), None)
                if reveal is not None and any(card.code == code for card in reveal.cards):
                    return code
                if blind_opponent_hand_choice:
                    # A copied Inexperienced Spy, for example, offers hand
                    # positions before revealing its selected card. Keep all
                    # choices but omit identities and native hand indices.
                    return None
                raise SimulatorUnavailable("hand choice lacks a recipient-scoped reveal")
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
                    target = {"controller": controller, "location": location}
                    if location not in (0x01, 0x40) and not (
                            location == 0x02 and controller != native.player):
                        target["sequence"] = sequence
                    visible_code = public_code(code, controller, location, sequence)
                    if visible_code is not None:
                        target["code"] = visible_code
                    cards.append(target)
                parameters["cards"] = cards
            if choice.zones:
                parameters["zones"] = [
                    {"controller": controller, "location": location, "sequence": sequence}
                    for controller, location, sequence in choice.zones
                ]
            if choice.location is not None:
                parameters["location"] = choice.location
            if choice.position is not None:
                parameters["position"] = choice.position
            if choice.race is not None:
                parameters["race"] = choice.race
            if choice.attribute is not None:
                parameters["attribute"] = choice.attribute
            if choice.number is not None:
                parameters["number"] = choice.number
            if choice.announced_card is not None:
                parameters["code"] = choice.announced_card
            if choice.prompt_id is not None:
                parameters["prompt_id"] = choice.prompt_id
            if native.card_selection is not None:
                parameters["selection_minimum"] = native.card_selection.minimum
                parameters["selection_maximum"] = native.card_selection.maximum
                parameters["selected_count"] = len(self._selection_indices)
            if native.sum_selection is not None:
                parameters["selection_minimum"] = native.sum_selection.minimum
                parameters["selection_maximum"] = native.sum_selection.maximum
                parameters["selected_count"] = len(self._selection_indices)
                parameters["selection_sum_target"] = native.sum_selection.target
                parameters["selection_sum_mode"] = (
                    "exact" if native.sum_selection.mode == 0 else "greater")
            if (choice.sequence is not None and choice.location not in (0x01, 0x40)
                    and not (choice.location == 0x02 and choice.controller != native.player)):
                parameters["sequence"] = choice.sequence
            if choice.controller is not None:
                parameters["controller"] = choice.controller
            if kind in ("select_cards", "tribute_cards") and any(
                    card[2] in (0x01, 0x40) for card in choice.cards):
                parameters["cards"].sort(key=lambda card: json.dumps(card, sort_keys=True))
            actions.append(Action(str(index), kind, native.player, parameters))
        paired = list(zip(native.choices, actions, strict=True))
        if any(choice.kind != "sort_cards" and (
                choice.location in (0x01, 0x40)
                or any(card[2] in (0x01, 0x40) for card in choice.cards))
               for choice in native.choices):
            # Native Deck/Extra Deck order is private. Publish choices in an
            # order derived only from visible fields, not native slot order.
            paired.sort(key=lambda pair: (pair[1].kind,
                        json.dumps(pair[1].parameters, sort_keys=True)))
        self._choices = tuple(choice for choice, _ in paired)
        self._actions = tuple(replace(action, id=str(index))
                              for index, (_, action) in enumerate(paired))
        self._last_observation = observation
        return Decision(self._last_observation, self._actions)

    @staticmethod
    def _card_selection_response(indices: tuple[int, ...]) -> bytes:
        ordered = tuple(sorted(indices))
        return struct.pack("<II", 0, len(ordered)) + struct.pack(
            f"<{len(ordered)}I", *ordered)

    def step(self, action: Action) -> Decision:
        if self.probe is None or action not in self._actions:
            raise ValueError("illegal action or engine not reset")
        index = self._actions.index(action)
        try:
            choice = self._choices[index]
            if self._selection_indices is not None and choice.kind == "select_card":
                if not isinstance(choice.response, int):
                    raise RuntimeError("staged selection candidate has no native index")
                selected = (*self._selection_indices, choice.response)
                native = self.probe.decode_pending()
                if native.sum_selection is not None:
                    self._selection_indices = selected
                    return self._decision()
                selection = native.card_selection
                if selection is None:
                    raise RuntimeError("staged selection lost its native prompt")
                if len(selected) < selection.maximum:
                    self._selection_indices = selected
                    return self._decision()
                response = self._card_selection_response(selected)
            else:
                response = choice.response
            self._selection_indices = None
            transition = self.probe.respond(response)
            if transition.terminal:
                self._choices = ()
                self._actions = ()
                self._last_observation = self.probe.observation(
                    self._last_observation.viewer, terminal=True)
                return Decision(self._last_observation, (), terminal=True,
                                winner=transition.winner)
            attack = (TargetSlotView(action.actor, "monster", action.parameters["sequence"])
                      if action.kind == "attack" else None)
            return self._decision(attack)
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.probe is not None:
            self.probe.close()
            self.probe = None
        self._choices = ()
        self._actions = ()
        self._selection_indices = None

    def replay_manifest(self) -> dict[str, str]:
        """Hash native files and every script loaded during the current duel."""
        if self.probe is None:
            raise RuntimeError("native duel is not active")
        required = (
            "build/libocgcore.so", "database/cards.cdb",
            "database/goat-entries.cdb", "database/cards-unofficial.cdb",
            "banlist/GOAT.lflist.conf",
        )
        result = {name: sha256_unchanged_file(self.root / name) for name in required}
        result.update({f"scripts/{name}": digest
                       for name, digest in self.probe.loaded_script_sha256.items()})
        return result

