"""Observation-only agents for exercising native rules-engine paths."""

from collections.abc import Sequence

from goat_ai.actions import Action
from goat_ai.observations import Observation

from .baseline import RandomAgent


class FirstActivationProbeAgent(RandomAgent):
    """Prefer an as-yet-unused card activation, then play randomly."""

    def __init__(self, seed: int = 0) -> None:
        super().__init__(seed)
        self.activated: set[int] = set()

    def select_action(self, observation: Observation,
                      legal_actions: Sequence[Action]) -> Action:
        candidates = [action for action in legal_actions
                      if action.kind in ("activate", "chain")
                      and type(action.parameters.get("code")) is int
                      and action.parameters["code"] not in self.activated]
        if candidates:
            selected = self.rng.choice(candidates)
            self.activated.add(selected.parameters["code"])
            return selected
        return super().select_action(observation, legal_actions)
