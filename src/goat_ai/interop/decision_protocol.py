"""Versioned JSON decision messages for non-Python game clients.

The caller supplies only one player's visible observation and legal actions.
The returned action ID is scoped to that one decision, never a native pointer.
"""

import json
from dataclasses import asdict, dataclass, fields
from typing import Any

from goat_ai.actions import Action
from goat_ai.observations import (
    CardView,
    ChainLinkView,
    DisabledZoneView,
    KnownCardView,
    Observation,
    PendingSummonView,
    PrivateRevealView,
    PublicAttackView,
    PublicRevealView,
    RevealedCardView,
    TargetSlotView,
)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DecisionRequest:
    decision_id: int
    ruleset: str
    observation: Observation
    legal_actions: tuple[Action, ...]

    def __post_init__(self) -> None:
        if (type(self.decision_id) is not int or self.decision_id < 0
                or type(self.ruleset) is not str or not self.ruleset
                or not self.legal_actions
                or self.observation.viewer != self.observation.acting_player
                or any(type(action.id) is not str or not action.id
                       or type(action.kind) is not str or not action.kind
                       or type(action.actor) is not int
                       or type(action.parameters) is not dict
                       for action in self.legal_actions)
                or len({action.id for action in self.legal_actions}) != len(self.legal_actions)
                or any(action.actor != self.observation.acting_player
                       for action in self.legal_actions)):
            raise ValueError("decision needs a visible acting-player view and unique legal IDs")


def _object(cls: type, raw: Any):
    if type(raw) is not dict or set(raw) != {field.name for field in fields(cls)}:
        raise ValueError(f"invalid {cls.__name__} fields")
    return cls(**raw)


def _cards(items: Any) -> tuple[CardView, ...]:
    if type(items) is not list:
        raise ValueError("card zone must be an array")
    result = []
    for raw in items:
        card = dict(raw) if type(raw) is dict else raw
        if type(card) is not dict:
            raise ValueError("card must be an object")
        card["counters"] = tuple(tuple(pair) for pair in card.get("counters", ()))
        if card.get("equipped_to") is not None:
            card["equipped_to"] = tuple(card["equipped_to"])
        result.append(_object(CardView, card))
    return tuple(result)


def _pair(items: Any, parser) -> tuple:
    if type(items) is not list or len(items) != 2:
        raise ValueError("player zones and counts must have two entries")
    return tuple(parser(item) for item in items)


def _count(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("counts must be nonnegative integers")
    return value


def _observation(raw: Any) -> Observation:
    if type(raw) is not dict or set(raw) != {field.name for field in fields(Observation)}:
        raise ValueError("invalid Observation fields")
    view = dict(raw)
    view["hand"] = _cards(view["hand"])
    view["field"] = _cards(view["field"])
    view["graveyards"] = _pair(view["graveyards"], _cards)
    view["banished"] = _pair(view["banished"], _cards)
    view["own_extra_deck"] = _cards(view["own_extra_deck"])
    view["life_points"] = _pair(view["life_points"], _count)
    view["deck_counts"] = _pair(view["deck_counts"], _count)
    view["extra_deck_counts"] = _pair(view["extra_deck_counts"], _count)
    view["chain"] = tuple(ChainLinkView(
        link["index"], link["card_code"], link["controller"],
        link["location"], link["sequence"],
        tuple(_object(TargetSlotView, target) for target in link["targets"]))
        for link in view["chain"])
    view["recent_attacks"] = tuple(PublicAttackView(
        attack["turn"], _object(TargetSlotView, attack["attacker"]),
        _object(TargetSlotView, attack["target"])
        if attack["target"] is not None else None)
        for attack in view["recent_attacks"])
    view["known_opponent_field_cards"] = tuple(
        _object(KnownCardView, card) for card in view["known_opponent_field_cards"])
    view["public_reveals"] = tuple(PublicRevealView(
        reveal["turn"], reveal["player"], reveal["zone"], tuple(reveal["codes"]))
        for reveal in view["public_reveals"])
    view["disabled_zones"] = tuple(
        _object(DisabledZoneView, slot) for slot in view["disabled_zones"])
    view["private_reveals"] = tuple(PrivateRevealView(
        reveal["turn"], reveal["recipient"],
        tuple(_object(RevealedCardView, card) for card in reveal["cards"]))
        for reveal in view["private_reveals"])
    view["pending_attack"] = (_object(TargetSlotView, view["pending_attack"])
                              if view["pending_attack"] is not None else None)
    view["pending_summon"] = (_object(PendingSummonView, view["pending_summon"])
                              if view["pending_summon"] is not None else None)
    for key in ("public_history", "known_opponent_cards", "restrictions",
                "own_main_deck", "known_opponent_hand_cards"):
        view[key] = tuple(view[key])
    return Observation(**view)


def encode_request(request: DecisionRequest) -> str:
    return json.dumps({"schema_version": SCHEMA_VERSION,
                       "decision_id": request.decision_id,
                       "ruleset": request.ruleset,
                       "observation": asdict(request.observation),
                       "legal_actions": [asdict(action) for action in request.legal_actions]},
                      separators=(",", ":"))


def decode_request(line: str | bytes) -> DecisionRequest:
    raw = json.loads(line)
    if (type(raw) is not dict or set(raw) != {
            "schema_version", "decision_id", "ruleset", "observation", "legal_actions"}
            or type(raw["schema_version"]) is not int
            or raw["schema_version"] != SCHEMA_VERSION
            or type(raw["legal_actions"]) is not list):
        raise ValueError("unsupported decision request")
    return DecisionRequest(raw["decision_id"], raw["ruleset"],
                           _observation(raw["observation"]),
                           tuple(_object(Action, item) for item in raw["legal_actions"]))


def encode_response(decision_id: int, action_id: str) -> str:
    if (type(decision_id) is not int or decision_id < 0
            or type(action_id) is not str or not action_id):
        raise ValueError("invalid decision response")
    return json.dumps({"schema_version": SCHEMA_VERSION,
                       "decision_id": decision_id, "action_id": action_id},
                      separators=(",", ":"))


def decode_response(line: str | bytes, request: DecisionRequest) -> Action:
    raw = json.loads(line)
    if (type(raw) is not dict
            or set(raw) != {"schema_version", "decision_id", "action_id"}
            or type(raw["schema_version"]) is not int
            or raw["schema_version"] != SCHEMA_VERSION
            or type(raw["decision_id"]) is not int
            or raw["decision_id"] != request.decision_id
            or type(raw["action_id"]) is not str):
        raise ValueError("response does not match decision request")
    return next((action for action in request.legal_actions
                 if action.id == raw["action_id"]), None) or _illegal_response()


def _illegal_response():
    raise ValueError("response selected an unknown action ID")


def select_response(agent, request: DecisionRequest) -> str:
    selected = agent.select_action(request.observation, request.legal_actions)
    if selected not in request.legal_actions:
        raise ValueError("agent returned an action outside the legal set")
    return encode_response(request.decision_id, selected.id)
