"""JSON trajectories; only visible observations are admitted by the schema."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from goat_ai.actions import Action
from goat_ai.observations import CardView, Observation


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
    schema_version: int = 1


def write_trajectory(path: str | Path, trajectory: Trajectory) -> None:
    Path(path).write_text(json.dumps(asdict(trajectory), separators=(",", ":")) + "\n", encoding="utf-8")


def read_trajectory(path: str | Path) -> Trajectory:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1:
        raise ValueError("unsupported trajectory schema")

    def cards(items: list[dict]) -> tuple[CardView, ...]:
        return tuple(CardView(**item) for item in items)

    records = []
    for record in raw["decisions"]:
        view = record["observation"]
        view["hand"] = cards(view["hand"])
        view["field"] = cards(view["field"])
        view["graveyards"] = tuple(cards(zone) for zone in view["graveyards"])
        view["banished"] = tuple(cards(zone) for zone in view["banished"])
        for key in ("life_points", "deck_counts", "extra_deck_counts", "chain",
                    "public_history", "known_opponent_cards", "restrictions"):
            view[key] = tuple(view[key])
        records.append(DecisionRecord(Observation(**view),
                                      tuple(Action(**a) for a in record["legal_actions"]),
                                      Action(**record["selected_action"])))
    return Trajectory(raw["ruleset"], tuple(raw["decks"]), raw["seed"], tuple(records),
                      raw["winner"], raw["source"], raw.get("skill_metadata"), 1)

