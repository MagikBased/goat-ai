"""All agents consume the same redacted observation and legal action list."""

import random
from collections.abc import Callable, Sequence
from typing import ClassVar, Protocol

from goat_ai.actions import Action
from goat_ai.observations import Observation


class Agent(Protocol):
    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action: ...


class RandomAgent:
    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        if not legal_actions:
            raise ValueError("no legal actions")
        return self.rng.choice(legal_actions)


class HeuristicAgent:
    """Simple generic action preference; no deck or card ID scripts."""

    _scores: ClassVar[dict[str, int]] = {
        "attack": 5, "activate": 4, "special_summon": 3,
        "normal_summon": 2, "flip_summon": 2, "set": 1,
        "change_position": 0, "pass": -1, "phase_transition": -2,
    }

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        if not legal_actions:
            raise ValueError("no legal actions")
        return max(legal_actions, key=lambda a: self._scores.get(a.kind, 0))


class HumanAgent:
    def __init__(self, input_fn: Callable[[str], str] = input,
                 output_fn: Callable[[str], None] = print) -> None:
        self.input_fn = input_fn
        self.output_fn = output_fn

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        if not legal_actions:
            raise ValueError("no legal actions")
        self.output_fn(f"Turn {observation.turn}, {observation.phase}, player {observation.acting_player}")
        for index, action in enumerate(legal_actions):
            self.output_fn(f"{index}: {action.kind} {action.parameters}")
        while True:
            answer = self.input_fn("Action number: ")
            try:
                index = int(answer)
                if 0 <= index < len(legal_actions):
                    return legal_actions[index]
            except ValueError:
                pass
            self.output_fn("Choose a listed number.")

