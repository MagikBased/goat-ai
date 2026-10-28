"""All agents consume the same redacted observation and legal action list."""

import random
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import ClassVar, Protocol

from goat_ai.actions import Action
from goat_ai.observations import CardView, Observation

from .tactical_guard import (
    BLACK_LUSTER_SOLDIER,
    SHEEP_TOKENS,
    THOUSAND_EYES_RESTRICT,
    THUNDER_DRAGON,
    TSUKUYOMI,
    admissible_action_indices,
    known_thunder_copies_in_deck,
    safe_position_indices,
    safe_target_indices,
    tribe_race_value,
)


class Agent(Protocol):
    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action: ...


class RandomAgent:
    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        if not legal_actions:
            raise ValueError("no legal actions")
        return self.rng.choice(legal_actions)


class HeuristicAgent:
    """Simple generic action preference; optional public Flip type metadata."""

    teacher_version: ClassVar[int] = 1
    _scores: ClassVar[dict[str, int]] = {
        "attack": 5, "activate": 4, "special_summon": 3,
        "normal_summon": 2, "flip_summon": 2, "set": 1,
        "change_position": 0, "pass": -1, "phase_transition": -2,
    }

    def __init__(self, flip_monster_codes: Collection[int] = ()) -> None:
        self.flip_monster_codes = frozenset(flip_monster_codes)

    def _score(self, action: Action) -> int:
        if (action.kind == "set_monster"
                and action.parameters.get("code") in self.flip_monster_codes):
            return 3
        return self._scores.get(action.kind, 0)

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        if not legal_actions:
            raise ValueError("no legal actions")
        return max(legal_actions, key=self._score)


class CombatHeuristicAgent(HeuristicAgent):
    """Generic visible-stat combat choices; never consults native private state."""

    teacher_version: ClassVar[int] = 3  # use schema-v22 attacker context in both target phases

    def __init__(self, flip_monster_codes: Collection[int] = ()) -> None:
        super().__init__(flip_monster_codes)
        self._pending_attack: tuple[int, int, int] | None = None

    @staticmethod
    def _battle_stat(card: CardView) -> int | None:
        return card.attack if card.orientation == "attack" else card.defense

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        if not legal_actions:
            raise ValueError("no legal actions")
        pending_attack = ((observation.turn, observation.pending_attack.controller,
                           observation.pending_attack.sequence)
                          if observation.pending_attack is not None
                          else self._pending_attack)
        self._pending_attack = None
        opponents = [card for card in observation.field
                     if card.zone == "monster" and card.controller != observation.viewer]
        own = {(card.controller, card.sequence): card for card in observation.field
               if card.zone == "monster" and card.controller == observation.viewer}
        attacks = [action for action in legal_actions if action.kind == "attack"]
        if attacks:
            visible = all(card.position == "faceup" and card.attack is not None
                          and card.defense is not None for card in opponents)
            def attack_power(action: Action) -> int:
                card = own.get((action.actor, action.parameters.get("sequence")))
                return card.attack or 0 if card is not None else 0

            safe = [action for action in attacks if not opponents or not visible
                    or any(attack_power(action) >= self._battle_stat(card)
                           for card in opponents)]
            if safe:
                chosen = max(safe, key=attack_power)
                self._pending_attack = (observation.turn, chosen.actor,
                                        chosen.parameters["sequence"])
                return chosen
            transition = next((action for action in legal_actions
                               if action.kind in ("main2", "end_phase")), None)
            if transition is not None:
                return transition
        if (pending_attack is not None
                and pending_attack[:2] == (observation.turn, observation.viewer)
                and (pending_attack[1], pending_attack[2]) in own
                and observation.phase in ("battle_start", "battle_step")
                and not observation.chain and legal_actions[0].kind == "select_card"):
            candidates = [action for action in legal_actions
                          if action.kind == "select_card"
                          and action.parameters.get("controller") != observation.viewer
                          and action.parameters.get("location") == 4]
            by_slot = {(card.controller, card.sequence): card for card in opponents}
            def target_card(action: Action) -> CardView | None:
                return by_slot.get((action.parameters["controller"],
                                    action.parameters.get("sequence")))

            visible_targets = [action for action in candidates
                               if (card := target_card(action))
                               is not None and card.position == "faceup"
                               and card.attack is not None and card.defense is not None]
            attacker = own[(pending_attack[1], pending_attack[2])]
            favorable = [action for action in visible_targets
                         if attacker.attack is not None
                         and attacker.attack >= self._battle_stat(target_card(action))]
            if favorable:
                return min(favorable, key=lambda action: self._battle_stat(
                    target_card(action)))
            hidden = [action for action in candidates if action not in visible_targets]
            if hidden:
                return hidden[0]
        return super().select_action(observation, legal_actions)


class CombatFlipHeuristicAgent(CombatHeuristicAgent):
    """Experimental combat teacher that first uses known Flip Summons."""

    teacher_version: ClassVar[int] = 1

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        flip = next((action for action in legal_actions
                     if action.kind == "flip_summon"
                     and action.parameters.get("code") in self.flip_monster_codes), None)
        if flip is not None:
            return flip
        return super().select_action(observation, legal_actions)


class TacticalHeuristicAgent(CombatFlipHeuristicAgent):
    """Flip-aware baseline with conservative, visible-board Trap decisions."""

    teacher_version: ClassVar[int] = 14  # reviewed removal and discard value
    RING: ClassVar[int] = 511000824
    TORRENTIAL: ClassVar[int] = 53582587
    SINISTER: ClassVar[int] = 511000818
    TRIBE: ClassVar[int] = 33184167
    SPIRIT_REAPER: ClassVar[int] = 504700038  # GOAT variant

    def __init__(self, flip_monster_codes: Collection[int] = (),
                 card_races: Mapping[int, int] | None = None,
                 *, card_facts: Mapping[int, tuple[int, int, int]] | None = None,
                 v8_guards: bool = True, v9_guards: bool | None = None,
                 v10_guards: bool | None = None,
                 v11_guards: bool | None = None,
                 v12_guards: bool | None = None,
                 v13_guards: bool | None = None,
                 v14_guards: bool | None = None,
                 reaper_set_guard: bool = False,
                 card_advantage_guard: bool = False) -> None:
        super().__init__(flip_monster_codes)
        self.card_races = dict(card_races or {})
        self.card_facts = dict(card_facts or {})
        self.v8_guards = v8_guards
        self.v9_guards = v8_guards if v9_guards is None else v9_guards
        self.v10_guards = self.v9_guards if v10_guards is None else v10_guards
        self.v11_guards = self.v10_guards if v11_guards is None else v11_guards
        self.v12_guards = self.v11_guards if v12_guards is None else v12_guards
        self.v13_guards = self.v12_guards if v13_guards is None else v13_guards
        self.v14_guards = self.v13_guards if v14_guards is None else v14_guards
        self.reaper_set_guard = reaper_set_guard
        self.card_advantage_guard = card_advantage_guard

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        if not legal_actions:
            raise ValueError("no legal actions")
        yes = next((action for action in legal_actions if action.kind == "yes"
                    and action.parameters.get("code") == self.SINISTER), None)
        if yes is not None:
            return yes

        if self.v8_guards and observation.chain:
            source = observation.chain[-1]
            if (self.v14_guards and source.controller == observation.viewer
                    and source.card_code == 4178474
                    and known_thunder_copies_in_deck(observation) == 0
                    and all(action.kind == "select_card"
                            and action.parameters.get("location") == 2
                            and action.parameters.get("controller") == observation.viewer
                            for action in legal_actions)):
                thunder = next((action for action in legal_actions
                                if action.parameters.get("code") == THUNDER_DRAGON), None)
                if thunder is not None:
                    return thunder
            if (self.v14_guards and source.controller == observation.viewer
                    and source.card_code == 45986603
                    and all(action.kind == "select_card"
                            and action.parameters.get("location") == 4
                            and action.parameters.get("controller") != observation.viewer
                            for action in legal_actions)):
                opponents = {(card.controller, card.sequence): card
                             for card in observation.field
                             if card.zone == "monster" and card.controller != observation.viewer
                             and card.position == "faceup" and card.code not in SHEEP_TOKENS}
                valuable = [action for action in legal_actions
                            if (action.parameters.get("controller"),
                                action.parameters.get("sequence")) in opponents]
                if valuable:
                    return max(valuable, key=lambda action: opponents[
                        (action.parameters["controller"],
                         action.parameters["sequence"])].attack or 0)
            if self.v9_guards and source.controller == observation.viewer:
                if (source.card_code == 31036355
                        and legal_actions[0].kind == "select_card"):
                    token = next((action for action in legal_actions
                                  if action.parameters.get("controller") == observation.viewer
                                  and action.parameters.get("code") in SHEEP_TOKENS), None)
                    if token is not None:
                        return token
                if (source.card_code == 34853266
                        and legal_actions[0].kind == "select_card"):
                    equipped_restrict = {
                        (card.controller, card.sequence) for card in observation.field
                        if card.zone == "monster" and card.controller == observation.viewer
                        and card.position == "faceup"
                        and card.code == THOUSAND_EYES_RESTRICT
                        and any(equip.equipped_to == (card.controller, card.sequence)
                                for equip in observation.field)}
                    restrict = next((action for action in legal_actions
                                     if (action.parameters.get("controller"),
                                         action.parameters.get("sequence"))
                                     in equipped_restrict), None)
                    if restrict is not None:
                        return restrict
            if (source.card_code == 44763025 and source.controller != observation.viewer
                    and legal_actions[0].kind == "select_card"):
                serpent = next((action for action in legal_actions
                                if action.parameters.get("code") == self.SINISTER
                                and action.parameters.get("controller") == observation.viewer
                                and action.parameters.get("location") == 2), None)
                if serpent is not None:
                    return serpent
            if (source.card_code == 504700054
                    and source.controller == observation.viewer):
                searches = [action for action in legal_actions
                            if action.kind == "select_cards"]
                if searches:
                    return max(searches, key=lambda action: sum(
                        card.get("code") == 504700054
                        for card in action.parameters.get("cards", ())))
            if (source.card_code == 504700116
                    and source.controller == observation.viewer
                    and legal_actions[0].kind == "select_card"):
                enemy = next((action for action in legal_actions
                              if action.parameters.get("controller") != observation.viewer
                              and action.parameters.get("location") == 4), None)
                if enemy is not None:
                    return enemy

        monsters = [card for card in observation.field if card.zone == "monster"]
        opposing = [card for card in monsters if card.controller != observation.viewer]
        if (observation.chain and observation.chain[-1].card_code == self.TRIBE
                and observation.chain[-1].controller == observation.viewer):
            races = [action for action in legal_actions if action.kind == "announce_race"]
            if races:
                return max(races, key=lambda action: tribe_race_value(
                    observation, action.parameters["race"], self.card_races))
        if (observation.chain and observation.chain[-1].card_code == self.RING
                and observation.chain[-1].controller == observation.viewer
                and legal_actions[0].kind == "select_card"):
            targets = [action for action in legal_actions if action.kind == "select_card"
                       and action.parameters.get("controller") != observation.viewer]
            by_slot = {(card.controller, card.sequence): card for card in opposing
                       if card.position == "faceup" and card.attack is not None}
            safe = [action for action in targets
                    if (card := by_slot.get((action.parameters.get("controller"),
                                             action.parameters.get("sequence")))) is not None
                    and card.attack < observation.life_points[observation.viewer]]
            if safe:
                return max(safe, key=lambda action: by_slot[
                    (action.parameters["controller"], action.parameters["sequence"])].attack)

        admissible = admissible_action_indices(
            observation, legal_actions, self.card_races,
            tactical_v8_guards=self.v8_guards,
            tactical_v9_guards=self.v9_guards,
            tactical_v10_guards=self.v10_guards,
            tactical_v11_guards=self.v11_guards,
            tactical_v12_guards=self.v12_guards,
            tactical_v13_guards=self.v13_guards,
            tactical_v14_guards=self.v14_guards,
            card_advantage_guard=self.card_advantage_guard,
            card_facts=self.card_facts)
        targets = safe_target_indices(
            observation, legal_actions, admissible,
            protect_removal_targets=self.v9_guards,
            prioritize_non_token_removal=self.v12_guards,
            avoid_resolving_normal_spell_targets=self.v14_guards,
            card_facts=self.card_facts)
        filtered = [legal_actions[i] for i in safe_position_indices(
            observation, legal_actions, targets,
            v10_guard=self.v10_guards)]
        if self.reaper_set_guard:
            reaper_set = any(action.kind == "set_monster"
                             and action.parameters.get("code") == self.SPIRIT_REAPER
                             for action in filtered)
            opponents = [card for card in observation.field
                         if card.zone == "monster"
                         and card.controller != observation.viewer]
            can_attack_directly = (not opponents and any(
                action.kind == "battle_phase" for action in filtered))
            can_beat_monster = any(
                card.position == "faceup"
                and (card.attack if card.orientation == "attack" else card.defense)
                is not None
                and (card.attack if card.orientation == "attack" else card.defense) < 300
                for card in opponents)
            if reaper_set and not can_attack_directly and not can_beat_monster:
                filtered = [action for action in filtered
                            if not (action.kind == "normal_summon"
                                    and action.parameters.get("code") == self.SPIRIT_REAPER)]
        if self.v11_guards and observation.phase == "main1":
            enemy = any(card.zone == "monster" and card.controller != observation.viewer
                        for card in observation.field)
            tsukuyomi = any(action.kind == "normal_summon"
                            and action.parameters.get("code") == TSUKUYOMI
                            for action in filtered)
            bls_activate = next((action for action in filtered
                                 if action.kind == "activate"
                                 and action.parameters.get("code") == BLACK_LUSTER_SOLDIER), None)
            bls_can_reset = any(action.kind == "change_position"
                                and action.parameters.get("code") == BLACK_LUSTER_SOLDIER
                                for action in legal_actions)
            if enemy and tsukuyomi and bls_activate is not None and bls_can_reset:
                return bls_activate
        if self.v13_guards and observation.phase == "main1" and not opposing:
            bls_ready = any(card.zone == "monster" and card.controller == observation.viewer
                            and card.code == BLACK_LUSTER_SOLDIER
                            and card.position == "faceup" and card.orientation == "attack"
                            for card in observation.field)
            battle = next((action for action in filtered
                           if action.kind == "battle_phase"), None)
            if bls_ready and battle is not None:
                return battle
        return super().select_action(observation, filtered)


class HumanAgent:
    def __init__(self, input_fn: Callable[[str], str] = input,
                 output_fn: Callable[[str], None] = print,
                 card_names: dict[int, str] | None = None,
                 page_size: int = 40) -> None:
        if page_size < 1:
            raise ValueError("page size must be positive")
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.card_names = card_names or {}
        self.page_size = page_size

    def _name(self, code: int | None) -> str:
        return (self.card_names.get(code, f"Card #{code}")
                if code is not None else "Hidden card")

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        if not legal_actions:
            raise ValueError("no legal actions")
        self.output_fn(f"Turn {observation.turn}, {observation.phase}, "
                       f"player {observation.acting_player}; LP {observation.life_points}")
        self.output_fn("Hand: " + (", ".join(self._name(card.code)
                                              for card in observation.hand) or "empty"))
        for seat in (observation.acting_player, 1 - observation.acting_player):
            field = [card for card in observation.field if card.controller == seat]
            self.output_fn(f"Player {seat} field: " + (
                ", ".join(f"{card.zone} {card.sequence}: {self._name(card.code)} "
                          f"({card.position}{', ' + card.orientation if card.orientation else ''})"
                          for card in field) or "empty"))
        self.output_fn(f"Opponent hand: {observation.opponent_hand_count}; "
                       f"Decks: {observation.deck_counts}; "
                       f"Graveyards: {tuple(map(len, observation.graveyards))}")
        if observation.known_opponent_hand_cards:
            self.output_fn("Known opponent hand cards: " + ", ".join(
                self._name(code) for code in observation.known_opponent_hand_cards))
        if observation.chain:
            self.output_fn("Chain: " + " -> ".join(
                f"{index}: {self._name(link.card_code)}"
                for index, link in enumerate(observation.chain, 1)))
        labels = []
        for action in legal_actions:
            code = action.parameters.get("code")
            label = f" {self._name(code)}" if isinstance(code, int) else ""
            labels.append(f"{action.kind}{label} {action.parameters}")
        matching = list(range(len(legal_actions)))
        offset = 0

        def show_page() -> None:
            end = min(offset + self.page_size, len(matching))
            self.output_fn(f"Actions {offset + 1}-{end} of {len(matching)} "
                           "(n next, p previous, /text search, / clear)")
            for index in matching[offset:end]:
                self.output_fn(f"{index}: {labels[index]}")

        show_page()
        while True:
            answer = self.input_fn("Action number or command: ").strip()
            if answer == "n":
                if offset + self.page_size < len(matching):
                    offset += self.page_size
                    show_page()
                else:
                    self.output_fn("No next page.")
                continue
            if answer == "p":
                if offset:
                    offset = max(0, offset - self.page_size)
                    show_page()
                else:
                    self.output_fn("No previous page.")
                continue
            if answer.startswith("/"):
                term = answer[1:].casefold()
                found = [index for index, label in enumerate(labels)
                         if term in label.casefold()]
                if not found:
                    self.output_fn("No actions match that search.")
                else:
                    matching = found
                    offset = 0
                    show_page()
                continue
            try:
                index = int(answer)
                if 0 <= index < len(legal_actions):
                    return legal_actions[index]
            except ValueError:
                pass
            self.output_fn("Choose an action number or use n, p, or /text.")

