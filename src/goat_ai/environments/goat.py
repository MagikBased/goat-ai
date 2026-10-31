"""Stable environment boundary; actual duel behavior is delegated to a rules engine."""

from dataclasses import asdict
from pathlib import Path

from goat_ai.actions import Action
from goat_ai.engine import Decision, RulesEngine
from goat_ai.engine.protocol import UnavailableOcgcore
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord, Trajectory
from goat_ai.replay.fingerprint import sha256_file


class GoatEnvironment:
    def __init__(
        self, player1_deck: str, player2_deck: str, seed: int = 0,
        engine: RulesEngine | None = None,
    ) -> None:
        self.decks = (player1_deck, player2_deck)
        self.seed = seed
        self.engine = engine if engine is not None else UnavailableOcgcore()
        self._decision: Decision | None = None
        self._history: list[DecisionRecord] = []

    def reset(self, seed: int | None = None) -> Observation:
        if seed is not None:
            self.seed = seed
        self._decision = self.engine.reset(*self.decks, self.seed)
        self._history = []
        return self._decision.observation

    def _current(self) -> Decision:
        if self._decision is None:
            raise RuntimeError("call reset before accessing a duel")
        return self._decision

    def legal_actions(self) -> tuple[Action, ...]:
        return self._current().legal_actions

    def step(self, action: Action) -> Observation:
        decision = self._current()
        if decision.terminal:
            raise RuntimeError("duel is terminal")
        if action not in decision.legal_actions:
            raise ValueError("illegal action")
        next_decision = self.engine.step(action)
        self._history.append(DecisionRecord(decision.observation, decision.legal_actions, action))
        self._decision = next_decision
        return self._decision.observation

    def is_terminal(self) -> bool:
        return self._current().terminal

    def result(self) -> int | None:
        decision = self._current()
        if not decision.terminal:
            raise RuntimeError("duel has not ended")
        return decision.winner

    def trajectory(self) -> Trajectory:
        decision = self._current()
        if not decision.terminal:
            raise RuntimeError("duel has not ended")
        hashes = (tuple(sha256_file(path) for path in self.decks)
                  if all(Path(path).is_file() for path in self.decks) else None)
        manifest = getattr(self.engine, "replay_manifest", None)
        assets = manifest() if manifest is not None else None
        return Trajectory(self.engine.ruleset.name, self.decks, self.seed,
                          tuple(self._history), decision.winner,
                          schema_version=30,
                          rules_profile=asdict(self.engine.ruleset),
                          deck_sha256=hashes, asset_sha256=assets,
                          terminal_observation=decision.observation)

    def close(self) -> None:
        close = getattr(self.engine, "close", None)
        if close is not None:
            close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

