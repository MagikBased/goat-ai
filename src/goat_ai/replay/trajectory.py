"""JSON trajectories; only visible observations are admitted by the schema."""

import json
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class DecisionRecord:
    observation: Observation
    legal_actions: tuple[Action, ...]
    selected_action: Action

    def __post_init__(self) -> None:
        if self.selected_action not in self.legal_actions:
            raise ValueError("selected action must be legal")
        if self.selected_action.actor != self.observation.acting_player:
            raise ValueError("selected action actor mismatch")


@dataclass(frozen=True)
class Trajectory:
    ruleset: str
    decks: tuple[str, str]
    seed: int
    decisions: tuple[DecisionRecord, ...]
    winner: int | None
    source: str = "self_play"
    skill_metadata: dict | None = None
    schema_version: int = 17
    rules_profile: dict | None = None
    deck_sha256: tuple[str, str] | None = None
    asset_sha256: dict[str, str] | None = None
    terminal_observation: Observation | None = None


def _json_dataclass(value):
    """Let JSON traverse nested dataclasses without recursively copying them."""
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")


def write_trajectory(path: str | Path, trajectory: Trajectory, *,
                     fast_json: bool = False) -> None:
    version = trajectory.schema_version
    if version not in range(1, 32):
        raise ValueError("unsupported trajectory schema")
    if version < 28 and any("effect_option" in action.parameters
                            for record in trajectory.decisions
                            for action in (*record.legal_actions, record.selected_action)):
        raise ValueError("effect options require schema v28")
    if version >= 18 and trajectory.terminal_observation is None:
        raise ValueError("schema v18 requires a terminal observation")
    if version < 18 and trajectory.terminal_observation is not None:
        raise ValueError("terminal observation requires schema v18")
    views = [record.observation for record in trajectory.decisions]
    if trajectory.terminal_observation is not None:
        views.append(trajectory.terminal_observation)
    for view in views:
        if version < 6 and view.known_opponent_field_cards:
            raise ValueError("known opponent field cards require schema v6")
        if version < 8 and view.public_reveals:
            raise ValueError("public reveals require schema v8")
        if version < 9 and view.disabled_zones:
            raise ValueError("disabled zones require schema v9")
        if version < 10 and view.private_reveals:
            raise ValueError("private reveals require schema v10")
        if version < 11 and view.own_main_deck:
            raise ValueError("own Main Deck composition requires schema v11")
        cards = (*view.hand, *view.own_extra_deck, *view.field,
                 *view.graveyards[0], *view.graveyards[1],
                 *view.banished[0], *view.banished[1])
        if version < 12 and any(
                card.attack is not None or card.defense is not None or card.counters
                for card in cards):
            raise ValueError("public monster stats require schema v12")
        if version < 17 and view.known_opponent_hand_cards:
            raise ValueError("known opponent hand cards require schema v17")
        if version < 19 and any(card.equipped_to is not None for card in cards):
            raise ValueError("Equip target slots require schema v19")
        if version < 21 and any(link.targets for link in view.chain):
            raise ValueError("chain target slots require schema v21")
        if version < 22 and view.pending_attack is not None:
            raise ValueError("pending attacker slot requires schema v22")
        if version < 23 and view.turn_player is not None:
            raise ValueError("turn player requires schema v23")
        if version >= 23 and view.turn_player is None:
            raise ValueError("schema v23 requires the public turn player")
        if version < 24 and any(card.race is not None for card in cards):
            raise ValueError("current monster Type requires schema v24")
        if version < 25 and (view.pending_summon is not None
                             or any(card.owner is not None for card in cards)):
            raise ValueError("summon context and original owner require schema v25")
        if version >= 25 and any(card.zone == "monster" and card.position == "faceup"
                                 and card.owner is None for card in view.field):
            raise ValueError("schema v25 requires owner for face-up monsters")
        if version < 26 and any(card.faceup_turns is not None for card in cards):
            raise ValueError("public face-up age requires schema v26")
        if version < 27 and view.recent_attacks:
            raise ValueError("public attack slots require schema v27")
        if version < 29 and any(card.attribute is not None for card in cards):
            raise ValueError("current monster Attribute requires schema v29")
        if version < 30 and any(card.level is not None for card in cards):
            raise ValueError("current monster Level requires schema v30")
        if version < 31 and any(card.level is not None for card in view.hand):
            raise ValueError("current own-hand Level requires schema v31")
    if fast_json:
        try:
            import orjson
        except ImportError as error:
            raise RuntimeError("fast trajectory JSON requires the speed extra: "
                               "pip install '.[speed]'") from error
        Path(path).write_bytes(orjson.dumps(trajectory, option=orjson.OPT_APPEND_NEWLINE))
    else:
        Path(path).write_text(json.dumps(trajectory, default=_json_dataclass,
                                         separators=(",", ":")) + "\n", encoding="utf-8")


def read_trajectory(path: str | Path, *, fast_json: bool = False) -> Trajectory:
    data = Path(path).read_bytes()
    if fast_json:
        try:
            import orjson
        except ImportError as error:
            raise RuntimeError("fast trajectory JSON requires the speed extra: "
                               "pip install '.[speed]'") from error
        raw = orjson.loads(data)
    else:
        raw = json.loads(data)
    version = raw.get("schema_version")
    if version not in range(1, 32):
        raise ValueError("unsupported trajectory schema")
    if version < 28 and any("effect_option" in action.get("parameters", {})
                            for record in raw.get("decisions", ())
                            for action in (*record.get("legal_actions", ()),
                                           record.get("selected_action", {}))):
        raise ValueError("effect options require schema v28")

    def cards(items: list[dict]) -> tuple[CardView, ...]:
        result = []
        for item in items:
            if version < 12:
                item = {key: value for key, value in item.items()
                        if key not in ("attack", "defense", "counters")}
            else:
                item["counters"] = tuple(tuple(counter) for counter in item.get("counters", ()))
            if version >= 19 and item.get("equipped_to") is not None:
                item["equipped_to"] = tuple(item["equipped_to"])
            else:
                item.pop("equipped_to", None)
            if version < 24:
                item.pop("race", None)
            if version < 25:
                item.pop("owner", None)
            if version < 26:
                item.pop("faceup_turns", None)
            if version < 29:
                item.pop("attribute", None)
            if version < 30:
                item.pop("level", None)
            elif version < 31 and item.get("zone") == "hand":
                item.pop("level", None)
            result.append(CardView(**item))
        return tuple(result)

    def observation(view: dict) -> Observation:
        if version >= 31 and any("level" not in card for card in view["hand"]):
            raise ValueError("schema v31 requires a Level field for own hand cards")
        view["hand"] = cards(view["hand"])
        if "own_extra_deck" in view:
            view["own_extra_deck"] = cards(view["own_extra_deck"])
        if version >= 24 and any(card.get("zone") == "monster"
                                 and card.get("position") == "faceup"
                                 and "race" not in card for card in view["field"]):
            raise ValueError("schema v24 requires a Type field for face-up monsters")
        if version >= 29 and any(card.get("zone") == "monster"
                                 and card.get("position") == "faceup"
                                 and "attribute" not in card for card in view["field"]):
            raise ValueError("schema v29 requires an Attribute field for face-up monsters")
        if version >= 30 and any(card.get("zone") == "monster"
                                 and card.get("position") == "faceup"
                                 and "level" not in card for card in view["field"]):
            raise ValueError("schema v30 requires a Level field for face-up monsters")
        view["field"] = cards(view["field"])
        if version >= 25 and any(card.zone == "monster" and card.position == "faceup"
                                 and card.owner is None for card in view["field"]):
            raise ValueError("schema v25 requires owner for face-up monsters")
        view["graveyards"] = tuple(cards(zone) for zone in view["graveyards"])
        view["banished"] = tuple(cards(zone) for zone in view["banished"])
        if version >= 6:
            view["known_opponent_field_cards"] = tuple(
                KnownCardView(**card) for card in view["known_opponent_field_cards"])
        else:
            view.pop("known_opponent_field_cards", None)
        if version >= 8:
            view["public_reveals"] = tuple(PublicRevealView(
                reveal["turn"], reveal["player"], reveal["zone"], tuple(reveal["codes"]))
                for reveal in view["public_reveals"])
        else:
            view.pop("public_reveals", None)
        if version >= 9:
            view["disabled_zones"] = tuple(DisabledZoneView(**slot)
                                           for slot in view["disabled_zones"])
        else:
            view.pop("disabled_zones", None)
        if version >= 10:
            view["private_reveals"] = tuple(PrivateRevealView(
                reveal["turn"], reveal["recipient"],
                tuple(RevealedCardView(**card) for card in reveal["cards"]))
                for reveal in view["private_reveals"])
        else:
            view.pop("private_reveals", None)
        if version >= 11:
            view["own_main_deck"] = tuple(view["own_main_deck"])
        else:
            view.pop("own_main_deck", None)
        if version >= 17:
            view["known_opponent_hand_cards"] = tuple(view["known_opponent_hand_cards"])
        else:
            view.pop("known_opponent_hand_cards", None)
        if version >= 22 and view.get("pending_attack") is not None:
            view["pending_attack"] = TargetSlotView(**view["pending_attack"])
        else:
            view.pop("pending_attack", None)
        if version >= 25 and view.get("pending_summon") is not None:
            view["pending_summon"] = PendingSummonView(**view["pending_summon"])
        else:
            view.pop("pending_summon", None)
        if version >= 27:
            if "recent_attacks" not in view:
                raise ValueError("schema v27 requires public attack history")
            view["recent_attacks"] = tuple(PublicAttackView(
                attack["turn"], TargetSlotView(**attack["attacker"]),
                TargetSlotView(**attack["target"])
                if attack["target"] is not None else None)
                for attack in view["recent_attacks"])
        else:
            view.pop("recent_attacks", None)
        if version >= 23:
            if (type(view.get("turn_player")) is not int
                    or view["turn_player"] not in (0, 1)):
                raise ValueError("schema v23 requires the public turn player")
        else:
            view.pop("turn_player", None)
        if version >= 2:
            view["chain"] = tuple(ChainLinkView(
                link["index"], link["card_code"], link["controller"],
                link["location"], link["sequence"],
                tuple(TargetSlotView(**target) for target in link.get("targets", ()))
                if version >= 21 else ()) for link in view["chain"])
        else:
            view["chain"] = tuple(view["chain"])
        for key in ("life_points", "deck_counts", "extra_deck_counts",
                    "public_history", "known_opponent_cards", "restrictions"):
            view[key] = tuple(view[key])
        return Observation(**view)

    records = [DecisionRecord(observation(record["observation"]),
                              tuple(Action(**a) for a in record["legal_actions"]),
                              Action(**record["selected_action"]))
               for record in raw["decisions"]]
    terminal = raw.get("terminal_observation") if version >= 18 else None
    if version >= 18 and terminal is None:
        raise ValueError("schema v18 requires a terminal observation")
    hashes = raw.get("deck_sha256")
    return Trajectory(
        raw["ruleset"], tuple(raw["decks"]), raw["seed"], tuple(records),
        raw["winner"], raw["source"], raw.get("skill_metadata"), version,
        raw.get("rules_profile"), tuple(hashes) if hashes is not None else None,
        raw.get("asset_sha256"), observation(terminal) if terminal is not None else None,
    )

