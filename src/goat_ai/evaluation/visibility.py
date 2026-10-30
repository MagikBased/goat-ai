"""Audit legal choices against the information visible at each decision."""

from collections import Counter
from collections.abc import Iterable

from goat_ai.actions import Action
from goat_ai.replay import DecisionRecord, Trajectory


class VisibilityViolation(ValueError):
    """A recorded legal choice discloses information absent from its observation."""


def _choice_cards(action: Action) -> Iterable[dict]:
    if action.kind in ("select_card", "unselect_card", "tribute"):
        yield action.parameters
    if action.kind in ("select_card", "select_cards", "finish_selection",
                       "tribute_cards", "sort_cards", "select_counters"):
        yield from action.parameters.get("cards", ())


def audit_decision_visibility(record: DecisionRecord) -> Counter[str]:
    """Check field and hand selection payloads without inspecting engine state."""
    observation = record.observation
    if observation.viewer != observation.acting_player:
        raise VisibilityViolation("decision observation is not for the acting player")
    field = {(card.controller, card.zone, card.sequence): card
             for card in observation.field}
    known_hand = Counter(observation.known_opponent_hand_cards)
    counts: Counter[str] = Counter()
    for action in record.legal_actions:
        if action.actor != observation.acting_player:
            raise VisibilityViolation("legal action actor differs from acting player")
        if action.parameters.get("location") in (1, 64) and "sequence" in action.parameters:
            raise VisibilityViolation("Deck choice exposes native slot")
        if "effect_option" in action.parameters and (
                action.kind not in ("activate", "chain")
                or type(action.parameters.get("code")) is not int
                or type(action.parameters["effect_option"]) is not int
                or not 0 <= action.parameters["effect_option"] < (1 << 20)):
            raise VisibilityViolation("effect option lacks a visible card or valid index")
        if action.kind == "select_counters":
            cards = action.parameters.get("cards", ())
            counter_type = action.parameters.get("counter_type")
            total = action.parameters.get("counter_total")
            staged = action.parameters.get("counter_stage") is True
            slots = set()
            if (type(counter_type) is not int or type(total) is not int
                    or total <= 0 or not isinstance(cards, (list, tuple))
                    or not cards or not all(isinstance(card, dict) for card in cards)):
                raise VisibilityViolation("counter selection has invalid public allocation")
            amounts = tuple(card.get("amount") for card in cards)
            if any(type(amount) is not int for amount in amounts):
                raise VisibilityViolation("counter selection has invalid public allocation")
            paid = sum(amounts)
            if staged:
                index = action.parameters.get("counter_index")
                count = action.parameters.get("counter_card_count")
                remaining = action.parameters.get("counter_remaining")
                if (type(index) is not int or type(count) is not int
                        or type(remaining) is not int or not 0 <= index < count <= 22
                        or len(cards) != index + 1 or paid + remaining != total
                        or remaining < 0):
                    raise VisibilityViolation("counter stage has invalid public progress")
            elif paid != total:
                raise VisibilityViolation("counter selection has invalid public allocation")
            for choice in cards:
                zone = {4: "monster", 8: "spell_trap"}.get(choice.get("location"))
                slot = (choice.get("controller"), zone, choice.get("sequence"))
                card = field.get(slot)
                amount = choice.get("amount")
                if (card is None or card.position != "faceup" or slot in slots
                        or type(amount) is not int or amount < (0 if staged else 1)
                        or amount > dict(card.counters).get(counter_type, 0)):
                    raise VisibilityViolation("counter selection exceeds visible field counters")
                slots.add(slot)
        hand_choices: Counter[int] = Counter()
        for choice in _choice_cards(action):
            controller = choice.get("controller")
            location = choice.get("location")
            if location in (1, 64) and "sequence" in choice:
                raise VisibilityViolation("Deck choice exposes native slot")
            if controller == observation.viewer:
                continue
            if location in (4, 8):
                zone = "monster" if location == 4 else "spell_trap"
                card = field.get((controller, zone, choice.get("sequence")))
                if card is None:
                    raise VisibilityViolation("opponent field choice has no visible slot")
                counts["opponent_field_choices"] += 1
                if card.position == "facedown":
                    counts["hidden_field_choices"] += 1
                    if "code" in choice or any(
                            key in choice for key in ("attack", "defense", "counters")):
                        raise VisibilityViolation("face-down opponent choice reveals card data")
                elif choice.get("code") != card.code:
                    raise VisibilityViolation("face-up opponent choice disagrees with observation")
            elif location == 2:
                counts["opponent_hand_choices"] += 1
                if "sequence" in choice:
                    raise VisibilityViolation("opponent hand choice exposes native slot")
                code = choice.get("code")
                if code is not None:
                    if not known_hand[code]:
                        raise VisibilityViolation(
                            "opponent hand choice reveals unknown identity")
                    hand_choices[code] += 1
                    if hand_choices[code] > known_hand[code]:
                        raise VisibilityViolation(
                            "opponent hand choice exceeds known copies")
    return counts


def audit_trajectory_visibility(trajectory: Trajectory) -> Counter[str]:
    if trajectory.schema_version < 17:
        raise VisibilityViolation("schema v17 or newer is required for known-hand audit")
    counts: Counter[str] = Counter()
    for index, record in enumerate(trajectory.decisions):
        try:
            counts.update(audit_decision_visibility(record))
        except VisibilityViolation as error:
            raise VisibilityViolation(f"decision {index}: {error}") from error
    counts["decisions"] = len(trajectory.decisions)
    return counts
