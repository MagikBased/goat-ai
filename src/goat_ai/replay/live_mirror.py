"""Live native-response mirror for an optional EDOPro room policy seat.

The room host owns its duel and hidden state. This mirror receives its seed,
preordered Decks and public response stream inside the trusted server process.
Only player-visible Observation and Action values cross into an Agent.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from goat_ai.actions import Action
from goat_ai.engine.decks import Decklist
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.protocol import Decision
from goat_ai.evaluation.visibility import audit_decision_visibility
from goat_ai.observations import Observation
from goat_ai.replay.edopro_reconstruct import advance_recorded_response
from goat_ai.replay.trajectory import DecisionRecord


class DecisionAgent(Protocol):
    def select_action(self, observation: Observation,
                      legal_actions: Sequence[Action]) -> Action: ...


class LiveDuelMirror:
    """Fail-closed adapter between raw core responses and the Agent API."""

    def __init__(self, native_root: str | Path, *, historical_patches: bool) -> None:
        self._engine = ExperimentalOcgcoreEngine(native_root)
        self._historical_patches = historical_patches
        self.decision: Decision | None = None
        self.records: list[DecisionRecord] = []
        self.response_count = 0
        self._local_response: tuple[int, bytes] | None = None

    def start(self, seed_words: tuple[int, int, int, int],
              decks: tuple[Decklist, Decklist]) -> Decision:
        if self.decision is not None:
            raise RuntimeError("live mirror already started")
        self.decision = self._engine.reset_recorded(
            seed_words, *decks, historical_patches=self._historical_patches)
        return self.decision

    def verify_prompt(self, team: int, message_type: int) -> None:
        if self.decision is None or self.decision.terminal:
            raise RuntimeError("room prompted after mirror terminal or before startup")
        if self.decision.observation.acting_player != team:
            raise RuntimeError("room prompt actor differs from mirror")
        native = self._engine.probe._pending_message
        if native is None or native[0] != message_type:
            raise RuntimeError("room prompt type differs from mirror")

    def choose(self, team: int, agent: DecisionAgent, *, max_stages: int = 64) -> bytes:
        """Run a policy through staged choices until one native response emits."""
        if self._local_response is not None or self.decision is None:
            raise RuntimeError("mirror is awaiting room confirmation or startup")
        for _ in range(max_stages):
            decision = self.decision
            if decision.terminal or decision.observation.acting_player != team:
                raise RuntimeError("policy seat is not the acting player")
            action = agent.select_action(decision.observation, decision.legal_actions)
            if action not in decision.legal_actions:
                raise ValueError("agent chose an illegal action")
            record = DecisionRecord(decision.observation, decision.legal_actions, action)
            audit_decision_visibility(record)
            self.records.append(record)
            self.decision = self._engine.step(action)
            response = self._engine.last_native_response
            if response is not None:
                self._local_response = (team, response)
                return response
        raise RuntimeError("policy selection exceeded native staging bound")

    def confirm_response(self, team: int, response: bytes) -> None:
        """Advance an opponent response or confirm a policy response already sent."""
        if self.decision is None:
            raise RuntimeError("mirror has not started")
        if self._local_response is not None:
            if self._local_response != (team, response):
                raise RuntimeError("room response differs from policy's native response")
            self._local_response = None
        else:
            next_decision, records = advance_recorded_response(
                self._engine, self.decision, response, self.response_count)
            if not records or records[0].observation.acting_player != team:
                raise RuntimeError("room response actor differs from mirror")
            for record in records:
                audit_decision_visibility(record)
            self.records.extend(records)
            self.decision = next_decision
        self.response_count += 1

    def close(self) -> None:
        self._engine.close()
        self.decision = None
        self._local_response = None

    def asset_manifest(self) -> dict[str, str]:
        """Fingerprint the core assets and effective scripts used by this duel."""
        return self._engine.replay_manifest()
