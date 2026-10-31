"""Audit legal choices against the information visible at each decision."""

from collections import Counter
from collections.abc import Iterable

from goat_ai.actions import Action
from goat_ai.replay import DecisionRecord, Trajectory


class VisibilityViolation(ValueError):
    """A recorded legal choice discloses information absent from its observation."""


_ZONE_KINDS = frozenset(("place", "place_zones", "disable_zone", "disable_zones"))


def _audit_zone_action(action: Action) -> None:
    """Zone prompts choose public coordinates, including empty opponent slots."""
    parameters = action.parameters
    if any(key in parameters for key in ("code", "attack", "defense", "counters")):
        raise VisibilityViolation("zone choice carries card identity or private stats")
    allowed = ({"zones", "selection_minimum", "selection_maximum", "selected_count"}
               if action.kind.endswith("zones") else
               {"controller", "location", "sequence"})
    if set(parameters) - allowed:
        raise VisibilityViolation("zone choice carries non-coordinate data")
    zones = (parameters.get("zones") if action.kind.endswith("zones") else
             (parameters,))
    if not isinstance(zones, (tuple, list)) or not zones:
        raise VisibilityViolation("zone choice has no public coordinates")
    seen = set()
    for zone in zones:
        if not isinstance(zone, dict):
            raise VisibilityViolation("zone choice has invalid public coordinates")
        if set(zone) != {"controller", "location", "sequence"}:
            raise VisibilityViolation("zone choice carries non-coordinate data")
        controller, location, sequence = (zone.get(key) for key in (
            "controller", "location", "sequence"))
        if (type(controller) is not int or controller not in (0, 1)
                or type(location) is not int or location not in (4, 8)
                or type(sequence) is not int
                or not 0 <= sequence < (7 if location == 4 else 8)):
            raise VisibilityViolation("zone choice has invalid public coordinates")
        slot = (controller, location, sequence)
        if slot in seen:
            raise VisibilityViolation("zone choice repeats a public coordinate")
        seen.add(slot)


def _choice_cards(action: Action) -> Iterable[dict]:
    # A card reference can be the action's source as well as a selection
    # payload. Check both: an unlisted action kind must not become a route for
    # exposing the identity of an opponent's hidden card.
    if (action.kind not in _ZONE_KINDS and "controller" in action.parameters
            and "location" in action.parameters):
        yield action.parameters
    if "cards" in action.parameters:
        cards = action.parameters["cards"]
        if not isinstance(cards, (tuple, list)) or not all(
                isinstance(card, dict) for card in cards):
            raise VisibilityViolation("card choices have invalid payload")
        yield from cards


def audit_decision_visibility(record: DecisionRecord) -> Counter[str]:
    """Check field and hand selection payloads without inspecting engine state."""
    observation = record.observation
    if observation.viewer != observation.acting_player:
        raise VisibilityViolation("decision observation is not for the acting player")
    field = {(card.controller, card.zone, card.sequence): card
             for card in observation.field}
    public_piles = {
        (card.controller, location, card.sequence): card
        for location, pile in ((16, observation.graveyards[1 - observation.viewer]),
                               (32, observation.banished[1 - observation.viewer]))
        for card in pile
    }
    known_hand = Counter(observation.known_opponent_hand_cards)
    counts: Counter[str] = Counter()
    for index, action in enumerate(record.legal_actions):
        if action.id != str(index):
            raise VisibilityViolation("legal action ID is not a public ordinal")
        if action.actor != observation.acting_player:
            raise VisibilityViolation("legal action actor differs from acting player")
        if action.kind in _ZONE_KINDS:
            _audit_zone_action(action)
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
            elif location in (16, 32):
                card = public_piles.get((controller, location, choice.get("sequence")))
                if card is None:
                    raise VisibilityViolation("opponent pile choice has no visible slot")
                if card.position == "facedown":
                    if "code" in choice or any(
                            key in choice for key in ("attack", "defense", "counters")):
                        raise VisibilityViolation("face-down opponent pile choice reveals card data")
                elif "code" in choice and choice["code"] != card.code:
                    raise VisibilityViolation("opponent pile choice disagrees with observation")
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
