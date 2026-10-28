"""Create a verified native AI-versus-AI duel for the local replay viewer."""

import json
import re
from dataclasses import replace
from pathlib import Path
from threading import Lock
from uuid import uuid4

from goat_ai.agents import (
    RandomAgent,
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.agents.card_metadata import load_weak_flip_monster_attack
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.replay_review import review_candidates
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION
from scripts.render_replay import render_replay
from scripts.shortlist_policy_disagreements import write_review_index
from scripts.validate_review_queue_labels import verify_queue_items

ROOT = Path(__file__).resolve().parents[1]
AGENTS = {"random": "Random", "tactical": "Tactical heuristic",
          "policy": "Neural policy v23"}


class GameCreator:
    """Restrict requests to local published decklists and the selected policy."""

    def __init__(self, root: Path = ROOT, native_root: Path | None = None,
                 output_dir: Path | None = None, checkpoint: Path | None = None):
        self.root = root.resolve()
        self.native_root = (native_root or self.root / ".cache/goat-ai").resolve()
        self.output_dir = (output_dir or self.root / ".cache/goat-ai/user_games").resolve()
        self.checkpoint = (checkpoint or self.native_root /
                           "fv23_current_tactical_broader_33000_33031.pt").resolve()
        self.lock = Lock()

    def decks(self) -> dict[str, Path]:
        folder = self.root / "examples/decks"
        return {path.name: path for path in sorted(folder.glob("*.ydk"))
                if "probe" not in path.stem}

    def options(self) -> dict:
        agents = {key: label for key, label in AGENTS.items()
                  if key != "policy" or self.checkpoint.is_file()}
        return {"decks": list(self.decks()), "agents": agents,
                "native_ready": (self.native_root / "banlist/GOAT.lflist.conf").is_file(),
                "recent": self.recent()}

    def recent(self) -> list[dict]:
        records = sorted(self.output_dir.glob("*.info.json"),
                         key=lambda path: path.stat().st_mtime_ns, reverse=True)[:20]
        return [json.loads(path.read_text(encoding="utf-8")) for path in records]

    def audit(self, identifier: str) -> dict:
        if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{16}", identifier):
            raise ValueError("invalid local game ID")
        path = self.output_dir / f"{identifier}.audit.json"
        if not path.is_file():
            raise FileNotFoundError("local game audit is unavailable")
        return json.loads(path.read_text(encoding="utf-8"))

    def review_queue(self, identifier: str) -> Path:
        """Build a separate, player-visible queue for flagged policy decisions."""
        report = self.audit(identifier)
        source = self.output_dir / f"{identifier}.json"
        trajectory = read_trajectory(source)
        metadata = trajectory.skill_metadata or {}
        seat = metadata.get("demonstrator_seat")
        checkpoint_hash = metadata.get("policy_checkpoint_sha256")
        if (trajectory.source != "policy_evaluation" or seat not in (0, 1)
                or checkpoint_hash != sha256_file(self.checkpoint)
                or metadata.get("policy_inference") != "greedy"
                or metadata.get("policy_inference_version") != POLICY_INFERENCE_VERSION):
            raise ValueError("game is not attributed to the selected policy checkpoint")
        flags = [flag for flag in report["flags"] if flag["acting_player"] == seat]
        if not flags:
            raise ValueError("this game has no flagged policy decisions to review")
        queue_dir = self.output_dir / f"{identifier}_review"
        queue = queue_dir / "queue.json"
        source_hash = sha256_file(source)
        verify_trajectory(trajectory, ExperimentalOcgcoreEngine(self.native_root))
        audit_trajectory_visibility(trajectory)
        policy = load_policy_agent(self.checkpoint)
        if metadata.get("policy_feature_version") != policy.model.feature_version:
            raise ValueError("recorded policy feature version differs from the checkpoint")
        for index, record in enumerate(trajectory.decisions):
            if record.observation.acting_player != seat:
                continue
            if policy.select_action(record.observation,
                                    record.legal_actions) != record.selected_action:
                raise ValueError(f"recorded policy choice differs at decision {index}")
        if queue.is_file():
            saved = json.loads(queue.read_text(encoding="utf-8"))
            if (saved.get("checkpoint_sha256") != checkpoint_hash
                    or any(item.get("trajectory_sha256") != source_hash
                           for item in saved.get("selected", []))):
                raise ValueError("existing game review queue differs from its replay")
            return queue
        queue_dir.mkdir(parents=True, exist_ok=True)
        visible = queue_dir / "visible.html"
        render_replay(source, visible, self.native_root)
        render_replay(source, visible.with_suffix(".review.html"),
                      self.native_root, reviewer_reveal=True,
                      deck_paths=tuple(trajectory.decks))
        selected = []
        for flag in flags:
            index = flag["decision_index"]
            record = trajectory.decisions[index]
            suggested = self._agent("tactical", trajectory.seed).select_action(
                record.observation, record.legal_actions)
            selected.append({
                "trajectory": str(source), "trajectory_sha256": source_hash,
                "decision_index": index, "viewer_frame": index + 1,
                "viewer": f"{visible}#decision={index + 1}",
                "seat": seat, "turn": record.observation.turn,
                "phase": record.observation.phase,
                "legal_action_count": len(record.legal_actions),
                "policy_action": {"kind": record.selected_action.kind,
                                  "parameters": record.selected_action.parameters},
                "teacher_action": {"kind": suggested.kind,
                                   "parameters": suggested.parameters},
                "audit_flags": [flag["category"]],
            })
        payload = {"schema_version": 1,
                   "purpose": "human_review_candidates_not_training_labels",
                   "checkpoint_sha256": checkpoint_hash,
                   "selected": selected}
        verify_queue_items(trajectory, {item["decision_index"]: item
                                        for item in selected}, checkpoint_hash)
        queue.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        write_review_index(selected, queue, self.native_root,
                           comparison_label="Tactical heuristic")
        return queue

    def _agent(self, name: str, seed: int):
        if name == "random":
            return RandomAgent(seed)
        if name == "tactical":
            return TacticalHeuristicAgent(
                load_flip_monster_codes(self.native_root),
                load_card_races(self.native_root),
                card_facts=load_card_facts(self.native_root))
        if name == "policy" and self.checkpoint.is_file():
            return load_policy_agent(self.checkpoint)
        raise ValueError("unknown or unavailable AI agent")

    def create(self, spec: dict, *, max_decisions: int = 3000) -> dict:
        if not isinstance(spec, dict) or set(spec) != {
                "deck1", "deck2", "agent1", "agent2", "seed"}:
            raise ValueError("game request needs two decks, two agents, and a seed")
        decks = self.decks()
        if (not isinstance(spec["deck1"], str) or spec["deck1"] not in decks
                or not isinstance(spec["deck2"], str) or spec["deck2"] not in decks):
            raise ValueError("choose deck filenames from the published deck list")
        available = self.options()["agents"]
        if (not isinstance(spec["agent1"], str) or spec["agent1"] not in available
                or not isinstance(spec["agent2"], str)
                or spec["agent2"] not in available):
            raise ValueError("choose an available AI for each seat")
        seed = spec["seed"]
        if type(seed) is not int or not 0 <= seed < (1 << 32):
            raise ValueError("seed must be an unsigned 32-bit integer")
        if max_decisions < 1 or max_decisions > 10000:
            raise ValueError("decision limit must be between 1 and 10000")
        if not self.options()["native_ready"]:
            raise FileNotFoundError("native GOAT assets are not installed")
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("another game is being generated; try again shortly")
        identifier = uuid4().hex[:16]
        base = self.output_dir / identifier
        try:
            agents = (self._agent(spec["agent1"], seed * 2 + 1),
                      self._agent(spec["agent2"], seed * 2 + 2))
            checkpoint_hash = (sha256_file(self.checkpoint)
                               if "policy" in (spec["agent1"], spec["agent2"]) else None)
            policy_seat = next((seat for seat, name in enumerate(
                (spec["agent1"], spec["agent2"])) if name == "policy"), None)
            with GoatEnvironment(str(decks[spec["deck1"]]), str(decks[spec["deck2"]]),
                                 seed, ExperimentalOcgcoreEngine(self.native_root)) as env:
                observation = env.reset()
                for _ in range(max_decisions):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        break
                if not env.is_terminal():
                    raise RuntimeError(f"duel exceeded {max_decisions} decisions")
                metadata = {"agents": [AGENTS[spec["agent1"]],
                                       AGENTS[spec["agent2"]]]}
                if policy_seat is not None:
                    opponent = agents[1 - policy_seat]
                    metadata.update({
                        "demonstrator_seat": policy_seat,
                        "policy_checkpoint_sha256": checkpoint_hash,
                        "policy_inference": "greedy",
                        "policy_inference_version": POLICY_INFERENCE_VERSION,
                        "policy_feature_version": agents[policy_seat].model.feature_version,
                        "opponent": type(opponent).__name__,
                        "opponent_version": getattr(opponent, "teacher_version", 1),
                    })
                    if spec["agent1"] == spec["agent2"] == "policy":
                        metadata["opponent_checkpoint_sha256"] = checkpoint_hash
                trajectory = replace(env.trajectory(),
                                     source=("policy_evaluation" if policy_seat is not None
                                             else "local_ai_match"),
                                     skill_metadata=metadata)
            if checkpoint_hash and sha256_file(self.checkpoint) != checkpoint_hash:
                raise RuntimeError("policy checkpoint changed during the duel")
            verified = verify_trajectory(trajectory,
                                         ExperimentalOcgcoreEngine(self.native_root))
            audit_trajectory_visibility(trajectory)
            races = load_card_races(self.native_root)
            weak_flips = load_weak_flip_monster_attack(self.native_root)
            card_facts = load_card_facts(self.native_root)
            review_flags = sorted((flag.to_dict()
                                   for seat in (0, 1)
                                   for flag in review_candidates(
                                       trajectory, races, weak_flips, review_seat=seat,
                                       card_facts=card_facts)),
                                  key=lambda flag: (flag["decision_index"],
                                                    flag["acting_player"]))
            self.output_dir.mkdir(parents=True, exist_ok=True)
            write_trajectory(base.with_suffix(".json"), trajectory)
            render_replay(base.with_suffix(".json"), base.with_suffix(".html"),
                          self.native_root, reviewer_reveal=True,
                          deck_paths=(decks[spec["deck1"]], decks[spec["deck2"]]))
            result = {"id": identifier, "deck1": spec["deck1"],
                      "deck2": spec["deck2"], "agent1": spec["agent1"],
                      "agent2": spec["agent2"], "seed": seed,
                      "winner": trajectory.winner, "decisions": verified,
                      "review_flags": len(review_flags),
                      "policy_review_flags": sum(
                          flag["acting_player"] == policy_seat for flag in review_flags)
                      if policy_seat is not None else 0,
                      "viewer": "/" + base.with_suffix(".html").relative_to(
                          self.root).as_posix()}
            base.with_suffix(".audit.json").write_text(json.dumps({
                "schema_version": 1, "game_id": identifier,
                "purpose": "heuristic_review_candidates_not_training_labels",
                "flags": review_flags}, indent=2) + "\n", encoding="utf-8")
            base.with_suffix(".info.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return result
        except Exception:
            for suffix in (".json", ".html", ".review.json", ".audit.json",
                           ".info.json"):
                base.with_suffix(suffix).unlink(missing_ok=True)
            raise
        finally:
            self.lock.release()
