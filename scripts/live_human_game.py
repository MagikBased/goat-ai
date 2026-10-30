"""Local, player-visible browser sessions against the native GOAT engine."""

import hashlib
import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path
from threading import Lock
from uuid import uuid4

from goat_ai.agents.card_metadata import load_card_effect_texts, load_card_names
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.create_viewer_game import GameCreator
from scripts.render_replay import render_replay


def _digest(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _automatic_pass(actions, hold_priority: bool):
    passes = [action for action in actions if action.kind == "pass"]
    if len(passes) != 1:
        return None
    if len(actions) == 1 or (not hold_priority and
                             all(action.kind in ("pass", "chain") for action in actions)):
        return passes[0]
    return None


class LiveGame:
    def __init__(self, identifier: str, env: GoatEnvironment, human_seat: int,
                 opponent, opponent_name: str, checkpoint_hash: str | None,
                 deck_names: tuple[str, str], output_dir: Path, root: Path,
                 native_root: Path, checkpoint: Path, names: dict[int, str],
                 max_decisions: int, spec: dict, journal_path: Path,
                 restore: dict | None = None):
        self.id = identifier
        self.env = env
        self.human_seat = human_seat
        self.opponent = opponent
        self.opponent_name = opponent_name
        self.checkpoint_hash = checkpoint_hash
        self.deck_names = deck_names
        self.output_dir = output_dir
        self.root = root
        self.native_root = native_root
        self.checkpoint = checkpoint
        self.names = names
        self.effect_texts: dict[tuple[int, int], str] = {}
        self.effect_codes_loaded: set[int] = set()
        self.max_decisions = max_decisions
        self.spec = spec
        self.journal_path = journal_path
        self.journal_entries: list[dict] = []
        self.explicit_human_decisions: list[int] = []
        self.decisions = 0
        self.viewer: str | None = None
        if restore is None:
            self._advance_opponent()
            self._save_journal()
        else:
            self._restore(restore)

    def _apply(self, action, origin: str) -> None:
        if origin not in ("manual", "automatic", "agent", "unknown"):
            raise ValueError("invalid live decision origin")
        current = self.env._current()
        actions = current.legal_actions
        if action not in actions:
            raise ValueError("action differs from native legal actions")
        if origin == "manual":
            if current.observation.acting_player != self.human_seat:
                raise ValueError("AI decision cannot be a human demonstration")
            self.explicit_human_decisions.append(self.decisions)
        self.journal_entries.append({
            "index": actions.index(action),
            "observation_sha256": _digest(asdict(current.observation)),
            "legal_sha256": _digest([asdict(item) for item in actions]),
            "origin": origin,
        })
        self.env.step(action)
        self.decisions += 1

    def _save_journal(self) -> None:
        if self.env.is_terminal():
            return
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        decks = self.env.decks
        payload = {
            "schema_version": 1, "id": self.id, "spec": self.spec,
            "deck_sha256": [sha256_file(path) for path in decks],
            "checkpoint_sha256": self.checkpoint_hash,
            "asset_sha256": self.env.engine.replay_manifest(),
            "entries": self.journal_entries,
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                                         dir=self.journal_path.parent,
                                         prefix=f".{self.id}.", suffix=".tmp",
                                         delete=False) as temporary:
            pending = Path(temporary.name)
            json.dump(payload, temporary, separators=(",", ":"))
            temporary.write("\n")
        try:
            os.replace(pending, self.journal_path)
        finally:
            pending.unlink(missing_ok=True)

    def _restore(self, journal: dict) -> None:
        if (journal.get("schema_version") != 1 or journal.get("id") != self.id
                or journal.get("spec") != self.spec
                or journal.get("deck_sha256") != [sha256_file(path) for path in self.env.decks]
                or journal.get("checkpoint_sha256") != self.checkpoint_hash
                or not isinstance(journal.get("entries"), list)):
            raise ValueError("unfinished duel journal or its inputs changed")
        for entry in journal["entries"]:
            if self.env.is_terminal() or not isinstance(entry, dict):
                raise ValueError("unfinished duel journal ends before its actions")
            current = self.env._current()
            actions = current.legal_actions
            index = entry.get("index")
            if (type(index) is not int or not 0 <= index < len(actions)
                    or entry.get("observation_sha256") != _digest(asdict(current.observation))
                    or entry.get("legal_sha256") != _digest([asdict(item) for item in actions])):
                raise ValueError(f"unfinished duel differs at decision {self.decisions}")
            action = actions[index]
            origin = entry.get("origin", "unknown")
            if origin not in ("manual", "automatic", "agent", "unknown"):
                raise ValueError(f"invalid decision origin at decision {self.decisions}")
            if origin == "manual":
                if current.observation.acting_player != self.human_seat:
                    raise ValueError("AI decision marked as human demonstration")
                self.explicit_human_decisions.append(self.decisions)
            if (current.observation.acting_player != self.human_seat
                    and self.opponent.select_action(current.observation, actions) != action):
                raise ValueError(f"AI choice differs at decision {self.decisions}")
            self.env.step(action)
            self.decisions += 1
        if self.env.engine.replay_manifest() != journal.get("asset_sha256"):
            raise ValueError("native assets changed since the unfinished duel")
        if not self.env.is_terminal() and self.env._current().observation.acting_player != self.human_seat:
            raise ValueError("unfinished duel journal ends before the human decision")
        self.journal_entries = list(journal["entries"])
        # Older journals may end at a human prompt whose only legal choice is
        # Pass. Resume through those forced windows using the current rules.
        self._advance_opponent()
        self._save_journal()

    def _advance_opponent(self, hold_priority: bool = False) -> None:
        while not self.env.is_terminal():
            if self.decisions >= self.max_decisions:
                raise RuntimeError("duel exceeded the decision limit")
            observation = self.env._current().observation
            actions = self.env.legal_actions()
            if observation.acting_player == self.human_seat:
                # Skip forced passes and, by default, optional chain windows.
                # Keep other prompts (including optional yes/no effects) for
                # the human because declining them can change the play.
                action = _automatic_pass(actions, hold_priority)
                if action is None:
                    break
            else:
                action = self.opponent.select_action(observation, actions)
            self._apply(action, "automatic" if observation.acting_player == self.human_seat
                        else "agent")
        if self.env.is_terminal() and self.viewer is None:
            self._finish()

    def _finish(self) -> None:
        if (self.checkpoint_hash is not None
                and sha256_file(self.checkpoint) != self.checkpoint_hash):
            raise RuntimeError("opponent checkpoint changed during the duel")
        trajectory = replace(self.env.trajectory(), source="human_web",
                             skill_metadata={
                                 "demonstrator_seat": self.human_seat,
                                 "authorization": "self_recorded",
                                 "explicit_human_decision_indices":
                                     self.explicit_human_decisions,
                                 "opponent": type(self.opponent).__name__,
                                 "opponent_version": getattr(self.opponent, "teacher_version", 1),
                                 **({"opponent_checkpoint_sha256": self.checkpoint_hash}
                                    if self.checkpoint_hash else {}),
                             })
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{self.id}.json"
        with tempfile.NamedTemporaryFile(dir=self.output_dir, prefix=f".{self.id}.",
                                         suffix=".json", delete=False) as temporary:
            pending = Path(temporary.name)
        try:
            write_trajectory(pending, trajectory)
            saved = read_trajectory(pending)
            verified = verify_trajectory(saved, ExperimentalOcgcoreEngine(self.native_root))
            audit_trajectory_visibility(saved)
            if verified != self.decisions:
                raise RuntimeError("recorded decision count differs after replay")
            os.replace(pending, path)
        finally:
            pending.unlink(missing_ok=True)
        page = path.with_suffix(".html")
        render_replay(path, page, self.native_root, reviewer_reveal=True,
                      deck_paths=tuple(trajectory.decks))
        self.viewer = "/" + page.relative_to(self.root).as_posix()
        result = {"id": self.id, "deck1": self.deck_names[0], "deck2": self.deck_names[1],
                  "agent1": "human" if self.human_seat == 0 else self.opponent_name,
                  "agent2": "human" if self.human_seat == 1 else self.opponent_name,
                  "seed": trajectory.seed, "winner": trajectory.winner,
                  "decisions": verified, "review_flags": 0,
                  "policy_review_flags": 0, "viewer": self.viewer}
        path.with_suffix(".info.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
        self.journal_path.unlink(missing_ok=True)
        self.env.close()

    def snapshot(self) -> dict:
        if self.env.is_terminal():
            return {"id": self.id, "terminal": True, "winner": self.env.result(),
                    "decisions": self.decisions, "viewer": self.viewer}
        observation = self.env._current().observation
        if observation.acting_player != self.human_seat or observation.viewer != self.human_seat:
            raise RuntimeError("game did not reach the human decision boundary")
        actions = self.env.legal_actions()
        codes = {card.code for card in (*observation.hand, *observation.field,
                 *observation.graveyards[0], *observation.graveyards[1],
                 *observation.banished[0], *observation.banished[1],
                 *observation.own_extra_deck)
                 if card.code is not None}
        codes.update(observation.known_opponent_hand_cards)
        codes.update(card.code for card in observation.known_opponent_field_cards)
        codes.update(code for reveal in observation.public_reveals for code in reveal.codes)
        codes.update(card.code for reveal in observation.private_reveals
                     for card in reveal.cards)
        codes.update(action.parameters["code"] for action in actions
                     if type(action.parameters.get("code")) is int)
        codes.update(link.card_code for link in observation.chain)
        described_codes = {action.parameters["code"] for action in actions
                           if type(action.parameters.get("effect_option")) is int
                           and type(action.parameters.get("code")) is int}
        fresh_codes = described_codes - self.effect_codes_loaded
        if fresh_codes:
            self.effect_texts.update(load_card_effect_texts(self.native_root, fresh_codes))
            self.effect_codes_loaded.update(fresh_codes)
        effect_labels = {}
        for index, action in enumerate(actions):
            option = action.parameters.get("effect_option")
            code = action.parameters.get("code")
            if type(option) is not int or type(code) is not int:
                continue
            native_description = self.env.engine._choices[index].effect_description
            documented = (native_description is not None
                          and native_description >> 20 == code
                          and native_description & 0xfffff == option)
            effect_labels[str(index)] = (self.effect_texts.get((code, option))
                                         if documented else None) or f"Effect option {option + 1}"
        return {"id": self.id, "terminal": False, "decisions": self.decisions,
                "human_seat": self.human_seat, "observation": asdict(observation),
                "legal_actions": [asdict(action) for action in actions],
                "action_effect_texts": effect_labels,
                "card_names": {str(code): self.names.get(code, f"Card #{code}")
                               for code in codes}}

    def choose(self, index: int, expected_decisions: int,
               manual: bool | None = True, hold_priority: bool = False) -> dict:
        if self.env.is_terminal():
            raise ValueError("duel has ended")
        if type(expected_decisions) is not int or expected_decisions != self.decisions:
            raise ValueError("stale live decision; refresh the game before choosing")
        if type(index) is not int or not 0 <= index < len(self.env.legal_actions()):
            raise ValueError("selected action is not legal")
        if self.decisions >= self.max_decisions:
            raise RuntimeError("duel exceeded the decision limit")
        if manual is not None and type(manual) is not bool:
            raise ValueError("manual decision flag must be boolean")
        if type(hold_priority) is not bool:
            raise ValueError("hold priority flag must be boolean")
        self._apply(self.env.legal_actions()[index],
                    "manual" if manual else "automatic" if manual is False else "unknown")
        self._advance_opponent(hold_priority=hold_priority)
        self._save_journal()
        return self.snapshot()

    def terminal(self) -> bool:
        return self.env.is_terminal()

    def close(self) -> None:
        if not self.env.is_terminal():
            self.env.close()

    def discard(self) -> None:
        self.journal_path.unlink(missing_ok=True)


class LiveGameHandle:
    """Run all native operations for one duel on its creating thread."""

    def __init__(self, identifier: str):
        self.executor = ThreadPoolExecutor(max_workers=1,
                                           thread_name_prefix=f"goat-live-{identifier}")
        self.game: LiveGame | None = None

    def create(self, factory) -> dict:
        self.game = self.executor.submit(factory).result()
        return self.call("snapshot")

    def call(self, method: str, *args):
        if self.game is None:
            raise RuntimeError("live game has not started")
        return self.executor.submit(lambda: getattr(self.game, method)(*args)).result()

    def close(self) -> None:
        try:
            if self.game is not None:
                self.call("close")
        finally:
            self.executor.shutdown(wait=True)


class LiveGameManager:
    """Hold a small number of local sessions; no native state is sent to HTTP clients."""

    def __init__(self, creator: GameCreator, max_sessions: int = 8):
        self.creator = creator
        self.max_sessions = max_sessions
        self.sessions: dict[str, LiveGameHandle] = {}
        self.lock = Lock()

    def _validated_decks(self, spec: dict) -> dict[str, Path]:
        if not isinstance(spec, dict) or set(spec) != {
                "deck1", "deck2", "human_seat", "opponent", "seed"}:
            raise ValueError("live game needs two decks, a human seat, opponent, and seed")
        decks = self.creator.decks()
        if any(type(spec[key]) is not str or spec[key] not in decks
               for key in ("deck1", "deck2")):
            raise ValueError("choose deck filenames from the published deck list")
        if type(spec["human_seat"]) is not int or spec["human_seat"] not in (0, 1):
            raise ValueError("human seat must be Player 1 or Player 2")
        if type(spec["opponent"]) is not str or spec["opponent"] not in self.creator.options()["agents"]:
            raise ValueError("choose an available AI opponent")
        seed = spec["seed"]
        if type(seed) is not int or not 0 <= seed < (1 << 32):
            raise ValueError("seed must be an unsigned 32-bit integer")
        if not self.creator.options()["native_ready"]:
            raise FileNotFoundError("native GOAT assets are not installed")
        return decks

    def _create_handle(self, identifier: str, spec: dict,
                       decks: dict[str, Path], restore: dict | None = None) -> tuple[LiveGameHandle, dict]:
        seed = spec["seed"]
        handle = LiveGameHandle(identifier)
        journal_path = self.creator.output_dir / "_in_progress" / f"{identifier}.json"

        def factory():
            opponent = self.creator._agent(spec["opponent"], seed * 2 + 1)
            checkpoint_hash = (sha256_file(self.creator.checkpoint)
                               if spec["opponent"] == "policy" else None)
            env = GoatEnvironment(str(decks[spec["deck1"]]), str(decks[spec["deck2"]]),
                                  seed, ExperimentalOcgcoreEngine(self.creator.native_root))
            try:
                env.reset()
                return LiveGame(identifier, env, spec["human_seat"], opponent,
                                spec["opponent"], checkpoint_hash,
                                (spec["deck1"], spec["deck2"]), self.creator.output_dir,
                                self.creator.root, self.creator.native_root,
                                self.creator.checkpoint,
                                load_card_names(self.creator.native_root), 3000,
                                spec, journal_path, restore)
            except BaseException:
                env.close()
                raise

        try:
            state = handle.create(factory)
            return handle, state
        except BaseException:
            handle.close()
            raise

    def start(self, spec: dict) -> dict:
        decks = self._validated_decks(spec)
        with self.lock:
            for old_id, handle in list(self.sessions.items()):
                if len(self.sessions) < self.max_sessions:
                    break
                if handle.call("terminal"):
                    self.sessions.pop(old_id)
                    handle.close()
            if len(self.sessions) >= self.max_sessions:
                raise RuntimeError("too many live games; finish a game before starting another")
            identifier = uuid4().hex[:16]
            handle, state = self._create_handle(identifier, spec, decks)
            self.sessions[identifier] = handle
            return state

    def _handle(self, identifier: str) -> LiveGameHandle:
        with self.lock:
            if identifier in self.sessions:
                return self.sessions[identifier]
            if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{16}", identifier):
                raise ValueError("unknown live game")
            path = self.creator.output_dir / "_in_progress" / f"{identifier}.json"
            if not path.is_file():
                raise ValueError("unknown live game")
            if len(self.sessions) >= self.max_sessions:
                raise RuntimeError("too many live games; finish a game before resuming another")
            journal = json.loads(path.read_text(encoding="utf-8"))
            spec = journal.get("spec")
            decks = self._validated_decks(spec)
            handle, _state = self._create_handle(identifier, spec, decks, journal)
            self.sessions[identifier] = handle
            return handle

    def get(self, identifier: str) -> dict:
        return self._handle(identifier).call("snapshot")

    def choose(self, identifier: str, action_index: int,
               expected_decisions: int, manual: bool | None = True,
               hold_priority: bool = False) -> dict:
        return self._handle(identifier).call("choose", action_index,
                                            expected_decisions, manual, hold_priority)

    def close(self, identifier: str) -> dict:
        with self.lock:
            handle = self.sessions.pop(identifier, None)
            if handle is None:
                raise ValueError("unknown live game")
            handle.call("discard")
            handle.close()
        return {"closed": True}

    def close_all(self) -> None:
        with self.lock:
            for handle in self.sessions.values():
                handle.close()
            self.sessions.clear()
