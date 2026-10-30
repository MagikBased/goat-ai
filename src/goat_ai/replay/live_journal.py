"""Read human choices from an unfinished local duel without inventing an outcome."""

import hashlib
import json
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_decision_visibility
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.replay.trajectory import DecisionRecord


@dataclass(frozen=True)
class VerifiedLivePrefix:
    journal_sha256: str
    seed: int
    decks: tuple[str, str]
    deck_sha256: tuple[str, str]
    asset_sha256: dict
    human_seat: int
    opponent_checkpoint_sha256: str | None
    verified_decisions: int
    manual_indices: tuple[int, ...]
    records: tuple[DecisionRecord, ...]


def _digest(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshot_live_journal(path: str | Path, directory: str | Path) -> Path:
    """Freeze a mutable private journal under its content hash for provenance."""
    path = Path(path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if sha256_file(path) != digest:
        raise ValueError("unfinished duel journal changed while copying")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / f"{digest}.json"
    if target.exists():
        if sha256_file(target) != digest:
            raise ValueError("human journal snapshot hash collision or corruption")
        return target
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".journal-", suffix=".tmp",
                                     delete=False) as temporary:
        pending = Path(temporary.name)
        temporary.write(raw)
    try:
        pending.chmod(0o600)
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)
    return target


def read_live_journal_prefix(path: str | Path, deck_root: str | Path,
                             native_root: str | Path) -> VerifiedLivePrefix:
    """Replay every saved action and retain only explicit human decisions.

    The live journal is local, mutable, and has no terminal outcome. A caller
    must keep its SHA-256 in training provenance; the returned decisions are
    not a completed human duel or an evaluation result.
    """
    path = Path(path)
    raw = path.read_bytes()
    journal_hash = hashlib.sha256(raw).hexdigest()
    journal = json.loads(raw)
    if (not isinstance(journal, dict) or journal.get("schema_version") != 1
            or not isinstance(journal.get("id"), str)
            or not re.fullmatch(r"[0-9a-f]{16}", journal["id"])
            or not isinstance(journal.get("spec"), dict)
            or not isinstance(journal.get("entries"), list)
            or not journal["entries"]):
        raise ValueError("invalid unfinished duel journal")
    spec = journal["spec"]
    checkpoint_hash = journal.get("checkpoint_sha256")
    if checkpoint_hash is not None and (not isinstance(checkpoint_hash, str)
                                        or not re.fullmatch(r"[0-9a-f]{64}", checkpoint_hash)):
        raise ValueError("unfinished duel has invalid opponent checkpoint hash")
    seed = spec.get("seed")
    seat = spec.get("human_seat")
    if (type(seed) is not int or not 0 <= seed < 1 << 32
            or type(seat) is not int or seat not in (0, 1)):
        raise ValueError("unfinished duel has invalid seed or human seat")
    root = Path(deck_root).resolve()
    names = (spec.get("deck1"), spec.get("deck2"))
    if any(not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+\.ydk", name)
           for name in names):
        raise ValueError("unfinished duel has invalid deck names")
    decks = tuple(str((root / name).resolve()) for name in names)
    if any(not Path(deck).is_relative_to(root) or not Path(deck).is_file()
           for deck in decks):
        raise ValueError("unfinished duel deck is missing or outside the deck root")
    deck_hashes = tuple(sha256_file(deck) for deck in decks)
    if journal.get("deck_sha256") != list(deck_hashes):
        raise ValueError("unfinished duel deck fingerprint changed")
    records = []
    manual_indices = []
    with GoatEnvironment(*decks, seed=seed,
                         engine=ExperimentalOcgcoreEngine(native_root)) as env:
        env.reset()
        manifest = env.engine.replay_manifest()
        if journal.get("asset_sha256") != manifest:
            raise ValueError("unfinished duel native assets changed")
        for decision_index, entry in enumerate(journal["entries"]):
            if env.is_terminal() or not isinstance(entry, dict):
                raise ValueError(f"unfinished duel ends before decision {decision_index}")
            decision = env._current()
            index = entry.get("index")
            if (type(index) is not int or not 0 <= index < len(decision.legal_actions)
                    or entry.get("observation_sha256") != _digest(
                        asdict(decision.observation))
                    or entry.get("legal_sha256") != _digest(
                        [asdict(action) for action in decision.legal_actions])):
                raise ValueError(f"unfinished duel differs at decision {decision_index}")
            origin = entry.get("origin")
            acting = decision.observation.acting_player
            if (origin not in ("manual", "automatic", "agent", "unknown")
                    or origin == "manual" and acting != seat
                    or origin == "automatic" and acting != seat
                    or origin == "agent" and acting == seat):
                raise ValueError(f"invalid decision origin at decision {decision_index}")
            action = decision.legal_actions[index]
            if origin == "manual" and len(decision.legal_actions) > 1:
                record = DecisionRecord(decision.observation,
                                        decision.legal_actions, action)
                audit_decision_visibility(record)
                records.append(record)
                manual_indices.append(decision_index)
            env.step(action)
    if not records:
        raise ValueError("unfinished duel has no non-forced human decisions")
    if sha256_file(path) != journal_hash:
        raise ValueError("unfinished duel journal changed during verification")
    return VerifiedLivePrefix(journal_hash, seed, decks, deck_hashes, manifest,
                              seat, checkpoint_hash, len(journal["entries"]), tuple(manual_indices),
                              tuple(records))
