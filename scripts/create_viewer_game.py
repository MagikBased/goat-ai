"""Create a verified native AI-versus-AI duel for the local replay viewer."""

import json
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
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from scripts.render_replay import render_replay

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
                trajectory = replace(env.trajectory(), source="local_ai_match",
                                     skill_metadata={
                                         "agents": [AGENTS[spec["agent1"]],
                                                    AGENTS[spec["agent2"]]],
                                         "policy_checkpoint_sha256": checkpoint_hash,
                                     })
            if checkpoint_hash and sha256_file(self.checkpoint) != checkpoint_hash:
                raise RuntimeError("policy checkpoint changed during the duel")
            verified = verify_trajectory(trajectory,
                                         ExperimentalOcgcoreEngine(self.native_root))
            audit_trajectory_visibility(trajectory)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            write_trajectory(base.with_suffix(".json"), trajectory)
            render_replay(base.with_suffix(".json"), base.with_suffix(".html"),
                          self.native_root, reviewer_reveal=True,
                          deck_paths=(decks[spec["deck1"]], decks[spec["deck2"]]))
            result = {"id": identifier, "deck1": spec["deck1"],
                      "deck2": spec["deck2"], "agent1": spec["agent1"],
                      "agent2": spec["agent2"], "seed": seed,
                      "winner": trajectory.winner, "decisions": verified,
                      "viewer": "/" + base.with_suffix(".html").relative_to(
                          self.root).as_posix()}
            base.with_suffix(".info.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return result
        except Exception:
            for suffix in (".json", ".html", ".review.json", ".info.json"):
                base.with_suffix(suffix).unlink(missing_ok=True)
            raise
        finally:
            self.lock.release()
