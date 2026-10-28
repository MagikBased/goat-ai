"""Audit legal choices against the information visible at each decision."""

from collections import Counter
from collections.abc import Iterable

from goat_ai.actions import Action
from goat_ai.replay import DecisionRecord, Trajectory


class VisibilityViolation(ValueError):
    """A recorded legal choice discloses information absent from its observation."""


def _choice_cards(action: Action) -> Iterable[dict]:
    if action.kind in ("select_card", "tribute"):
        yield action.parameters
    if action.kind in ("select_card", "select_cards", "finish_selection",
                       "tribute_cards", "sort_cards"):
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
        hand_choices: Counter[int] = Counter()
        for choice in _choice_cards(action):
            controller = choice.get("controller")
            location = choice.get("location")
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
