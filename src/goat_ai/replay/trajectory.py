"""JSON trajectories; only visible observations are admitted by the schema."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from goat_ai.actions import Action
from goat_ai.observations import (
    CardView,
    ChainLinkView,
    DisabledZoneView,
    KnownCardView,
    Observation,
    PrivateRevealView,
    PublicRevealView,
    RevealedCardView,
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
    schema_version: int = 13
    rules_profile: dict | None = None
    deck_sha256: tuple[str, str] | None = None
    asset_sha256: dict[str, str] | None = None


def write_trajectory(path: str | Path, trajectory: Trajectory) -> None:
    Path(path).write_text(json.dumps(asdict(trajectory), separators=(",", ":")) + "\n", encoding="utf-8")


def read_trajectory(path: str | Path) -> Trajectory:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    version = raw.get("schema_version")
    if version not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13):
        raise ValueError("unsupported trajectory schema")

    def cards(items: list[dict]) -> tuple[CardView, ...]:
        result = []
        for item in items:
            if version < 12:
                item = {key: value for key, value in item.items()
                        if key not in ("attack", "defense", "counters")}
            else:
                item["counters"] = tuple(tuple(counter) for counter in item.get("counters", ()))
            result.append(CardView(**item))
        return tuple(result)

    records = []
    for record in raw["decisions"]:
        view = record["observation"]
        view["hand"] = cards(view["hand"])
        if "own_extra_deck" in view:
            view["own_extra_deck"] = cards(view["own_extra_deck"])
        view["field"] = cards(view["field"])
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
        if version >= 2:
            view["chain"] = tuple(ChainLinkView(**link) for link in view["chain"])
        else:
            view["chain"] = tuple(view["chain"])
        for key in ("life_points", "deck_counts", "extra_deck_counts",
                    "public_history", "known_opponent_cards", "restrictions"):
            view[key] = tuple(view[key])
        records.append(DecisionRecord(Observation(**view),
                                      tuple(Action(**a) for a in record["legal_actions"]),
                                      Action(**record["selected_action"])))
    hashes = raw.get("deck_sha256")
    return Trajectory(
        raw["ruleset"], tuple(raw["decks"]), raw["seed"], tuple(records),
        raw["winner"], raw["source"], raw.get("skill_metadata"), version,
        raw.get("rules_profile"), tuple(hashes) if hashes is not None else None,
        raw.get("asset_sha256"),
    )

