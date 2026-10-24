"""Structured, variable-length legal actions supplied by the rules engine."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Action:
    # id is valid only at the current decision point, never a persistent card ID.
    id: str
    kind: str
    actor: int
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.kind or self.actor not in (0, 1):
            raise ValueError("action requires an id, kind, and actor 0 or 1")

