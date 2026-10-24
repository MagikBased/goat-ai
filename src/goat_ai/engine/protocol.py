"""An engine must perform real rule resolution and return already-redacted views."""

from dataclasses import dataclass
from typing import Protocol

from goat_ai.actions import Action
from goat_ai.observations import Observation


class SimulatorUnavailable(RuntimeError):
    """Raised when no audited historical engine is installed."""


@dataclass(frozen=True)
class RulesProfile:
    name: str = "tcg-goat-2005-08-17"
    april_2005_banlist: bool = True
    first_turn_draw: bool = True
    obsolete_ignition_priority: bool = True


@dataclass(frozen=True)
class Decision:
    observation: Observation
    legal_actions: tuple[Action, ...]
    terminal: bool = False
    winner: int | None = None

    def __post_init__(self) -> None:
        if self.terminal and self.legal_actions:
            raise ValueError("terminal decision cannot have actions")
        if self.winner not in (None, 0, 1):
            raise ValueError("winner must be 0, 1, or None for draw")
        if not self.terminal and not self.legal_actions:
            raise ValueError("nonterminal decision requires legal actions")
        if any(a.actor != self.observation.acting_player for a in self.legal_actions):
            raise ValueError("legal action actor mismatch")


class RulesEngine(Protocol):
    ruleset: RulesProfile

    def reset(self, deck1: str, deck2: str, seed: int) -> Decision: ...

    def step(self, action: Action) -> Decision: ...


class UnavailableOcgcore:
    """Fail-closed boundary until GOAT mode and hidden-info behavior are validated."""

    ruleset = RulesProfile()

    def reset(self, deck1: str, deck2: str, seed: int) -> Decision:
        raise SimulatorUnavailable(
            "GOAT ocgcore integration is unfinished: build a GOAT-mode core, load pinned "
            "card data/scripts, map response messages, and audit player-visible queries. "
            "See docs/architecture.md."
        )

    def step(self, action: Action) -> Decision:
        raise SimulatorUnavailable("GOAT ocgcore integration is unfinished")

