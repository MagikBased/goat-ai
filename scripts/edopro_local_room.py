"""Launch and inspect one private EDOPro policy room from the local web UI."""

import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import Lock
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import torch

from goat_ai.agents.card_metadata import load_card_names
from goat_ai.replay import read_decision_annotations, read_trajectory
from goat_ai.replay.edopro_live_verify import (
    verify_edopro_human_annotations,
    verify_edopro_live_recording,
)
from goat_ai.replay.fingerprint import sha256_file
from scripts.confirm_edopro_human_actions import confirm_frames
from scripts.create_viewer_game import GameCreator
from scripts.render_replay import render_replay


class EdoRoomManager:
    def __init__(self, creator: GameCreator, *, port: int = 7911):
        self.creator = creator
        self.port = port
        self.root = creator.root
        self.folder = creator.native_root / "edopro_games"
        self.host_root = creator.native_root / "edopro_pinned_host"
        self.host_package = creator.native_root / "edopro_probe/ygo_agent_host"
        self.lock = Lock()
        self.verify_lock = Lock()
        self.process: subprocess.Popen | None = None
        self.session: str | None = None
        self._verified: dict[str, tuple[int, dict]] = {}
        self.names: dict[int, str] | None = None
        self._recover_session()

    def _owned_pid_running(self, directory: Path, pid: object) -> bool:
        """Recognize only this session's room process after a server restart.

        On Linux, /proc lets us reject a recycled PID or an unrelated process.
        Other platforms still retain the port-in-use guard in start().
        """
        if type(pid) is not int or pid <= 1:
            return False
        try:
            argv = (Path("/proc") / str(pid) / "cmdline").read_bytes().split(b"\0")
            args = [os.fsdecode(arg) for arg in argv if arg]
            script = str(self.root / "scripts/serve_edopro_policy.py")
            return (len(args) >= 2 and args[1] == script
                    and args[args.index("--out") + 1] == str(directory)
                    and args[args.index("--port") + 1] == str(self.port))
        except (OSError, ValueError, IndexError):
            return False

    def _recover_session(self) -> None:
        if not self.folder.is_dir():
            return
        for directory in sorted(self.folder.glob("[0-9a-f]" * 16),
                                key=lambda path: path.stat().st_mtime_ns,
                                reverse=True):
            metadata = directory / "session.json"
            if not metadata.is_file():
                continue
            try:
                pid = json.loads(metadata.read_text(encoding="utf-8")).get("pid")
            except (OSError, ValueError):
                continue
            if self._owned_pid_running(directory, pid):
                self.session = directory.name
                return

    def _session_directory(self, identifier: str) -> Path:
        if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{16}", identifier):
            raise ValueError("invalid EDOPro session ID")
        directory = self.folder / identifier
        if not (directory / "session.json").is_file():
            raise ValueError("EDOPro session is unavailable")
        return directory

    def _verified_game(self, identifier: str) -> tuple[Path, Path, Path]:
        directory = self._session_directory(identifier)
        record = self._recording(directory)
        if not record or not record.get("experimental_confirmed_eligible"):
            raise ValueError("EDOPro recording is not a complete, fingerprinted pinned duel")
        replay = self.root / record["native_replay"]
        stem = replay.with_suffix("")
        metadata = stem.with_suffix(".meta.json")
        if json.loads(metadata.read_text(encoding="utf-8")).get(
                "human_authorization") != "self_recorded":
            raise ValueError("recording lacks self-recording authorization")
        return replay, stem.with_suffix(".review.json"), metadata

    def native_replay(self, identifier: str) -> Path:
        """Return only a recording inside a known local room session."""
        directory = self._session_directory(identifier)
        replays = sorted(directory.glob("game-*.yrpX"))
        if not replays:
            raise ValueError("EDOPro session has no saved native replay")
        replay = replays[-1]
        if not replay.is_file() or replay.is_symlink() or replay.stat().st_size == 0:
            raise ValueError("EDOPro native replay is unavailable")
        return replay

    def confirmed_bundle(self, identifier: str) -> bytes:
        """Export a verified local human game and its replay-bound confirmations."""
        with self.lock:
            replay, review, metadata = self._verified_game(identifier)
            labels = replay.with_suffix(".human_labels.json")
            if not labels.is_file():
                raise ValueError("Confirm human choices before exporting a training bundle")
            report = verify_edopro_human_annotations(
                replay, review, metadata, labels, self.creator.native_root)
            if not (report["complete"] and report["historical_patches"]
                    and report["asset_identity_verified"]
                    and report["deck_identity_verified"]
                    and report["confirmed_human_choices"] > 0):
                raise ValueError("Only complete, fingerprinted games with confirmed choices qualify")
            files = (replay, review, metadata, labels)
            if sum(path.stat().st_size for path in files) > 64_000_000:
                raise ValueError("EDOPro training bundle exceeds the local size limit")
            contents = {path.name: path.read_bytes() for path in files}
        hashes = {name: sha256(data).hexdigest() for name, data in contents.items()}
        payload = BytesIO()
        with ZipFile(payload, "w", compression=ZIP_DEFLATED) as archive:
            for name, data in contents.items():
                archive.writestr(name, data)
            archive.writestr("bundle_manifest.json", json.dumps({
                "schema_version": 1, "source": "edopro_human_confirmed_experimental",
                "historical_goat_certified": False,
                "confirmed_human_choices": report["confirmed_human_choices"],
                "sha256": hashes,
                "note": "Training requires the same pinned native assets; unzip all files "
                        "into one directory before using --experimental-edopro-confirmed.",
            }, indent=2) + "\n")
        return payload.getvalue()

    def choices(self, identifier: str) -> dict:
        replay, review, metadata = self._verified_game(identifier)
        trajectory = read_trajectory(review)
        recording_metadata = json.loads(metadata.read_text(encoding="utf-8"))
        seat = recording_metadata["human_client_seat"]
        labels = replay.with_suffix(".human_labels.json")
        confirmed = set()
        if labels.is_file():
            verify_edopro_human_annotations(
                replay, review, metadata, labels, self.creator.native_root)
            annotations, _ = read_decision_annotations(
                labels, sha256_file(review), trajectory)
            confirmed = {index + 1 for index, _ in annotations.choices}
        if self.names is None:
            self.names = load_card_names(self.creator.native_root)
        candidates = []
        for index, record in enumerate(trajectory.decisions):
            if record.observation.acting_player != seat or len(record.legal_actions) < 2:
                continue
            action = record.selected_action
            code = action.parameters.get("code")
            card = self.names.get(code, f"Card #{code}") if type(code) is int else None
            candidates.append({"frame": index + 1, "turn": record.observation.turn,
                               "phase": record.observation.phase,
                               "action": action.kind.replace("_", " "),
                               "card": card,
                               "confirmed": index + 1 in confirmed})
        recording = self._recording(replay.parent)
        command = [str(self.root / ".venv/bin/python"),
                   "scripts/train_behavioral_clone.py",
                   "--experimental-edopro-confirmed", str(replay),
                   "--native-root", str(self.creator.native_root)]
        continuation = False
        if (self.creator.checkpoint.is_file()
                and recording_metadata.get("checkpoint_sha256") == sha256_file(
                    self.creator.checkpoint)):
            checkpoint = torch.load(self.creator.checkpoint, map_location="cpu",
                                    weights_only=True)
            command += ["--init-checkpoint", str(self.creator.checkpoint),
                        "--feature-version", str(checkpoint["feature_version"]),
                        "--width", str(checkpoint["width"]),
                        "--learning-rate", "0.0001"]
            continuation = True
        command += ["--output", str(replay.parent / (
            "confirmed_child.pt" if continuation else "confirmed_pilot.pt"))]
        return {"id": identifier, "viewer": recording["viewer"],
                "native_replay": recording["native_replay"],
                "experimental_confirmed_eligible": recording.get(
                    "experimental_confirmed_eligible", False),
                "candidates": candidates, "confirmed": len(confirmed),
                "training_command": "PYTHONPATH=src:. " + shlex.join(command),
                "continues_recorded_policy": continuation,
                "training_admitted": False}

    def save_choices(self, identifier: str, frames: list[int]) -> dict:
        if (not isinstance(frames, list) or len(frames) > 1000
                or any(type(frame) is not int or frame < 1 for frame in frames)
                or len(set(frames)) != len(frames)):
            raise ValueError("invalid EDOPro decision numbers")
        with self.lock:
            replay, review, metadata = self._verified_game(identifier)
            trajectory = read_trajectory(review)
            seat = json.loads(metadata.read_text(encoding="utf-8"))["human_client_seat"]
            offered = {index + 1 for index, record in enumerate(trajectory.decisions)
                       if record.observation.acting_player == seat
                       and len(record.legal_actions) > 1}
            if not set(frames) <= offered:
                raise ValueError("a selected decision is not an optional human-seat choice")
            output = replay.with_suffix(".human_labels.json")
            if output.is_file():
                verify_edopro_human_annotations(
                    replay, review, metadata, output, self.creator.native_root)
            if not frames:
                output.unlink(missing_ok=True)
            else:
                with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
                    pending = Path(temporary) / output.name
                    confirm_frames(replay, frames, self.creator.native_root,
                                   pending)
                    pending.replace(output)
            return {"id": identifier, "confirmed": len(frames),
                    "experimental_confirmed_eligible": self._recording(
                        replay.parent).get("experimental_confirmed_eligible", False),
                    "training_admitted": False}

    def readiness(self) -> tuple[bool, str]:
        if not (self.host_package / "ygo_agent/arena/server.py").is_file():
            return False, "The optional EDOPro host package is missing. See README.md."
        for path in (self.host_root / "libocgcore.so",
                     self.host_root / "script",
                     self.host_root / "lflists/GOAT.lflist.conf",
                     self.creator.checkpoint):
            if not path.exists():
                return False, f"Required local asset is missing: {path.name}"
        return True, ""

    def _room_running(self) -> bool:
        if self.process is not None:
            return self.process.poll() is None
        if self.session is None:
            return False
        directory = self.folder / self.session
        try:
            pid = json.loads((directory / "session.json").read_text(
                encoding="utf-8")).get("pid")
        except (OSError, ValueError):
            return False
        return self._owned_pid_running(directory, pid)

    def start(self, deck_name: str) -> dict:
        with self.lock:
            ready, reason = self.readiness()
            if not ready:
                raise ValueError(reason)
            decks = self.creator.decks()
            if deck_name not in decks:
                raise ValueError("Choose a published AI deck from this page")
            if self._room_running():
                raise ValueError("An EDOPro room is already running")
            with socket.socket() as probe:
                probe.settimeout(0.3)
                if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                    raise ValueError(f"Port {self.port} is already in use")
            identifier = uuid4().hex[:16]
            output = self.folder / identifier
            output.mkdir(parents=True)
            log_path = output / "room.log"
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join((
                str(self.root / "src"), str(self.root), str(self.host_package),
                env.get("PYTHONPATH", "")))
            argv = [sys.executable, str(self.root / "scripts/serve_edopro_policy.py"),
                    "--host-root", str(self.host_root),
                    "--mirror-root", str(self.creator.native_root),
                    "--historical-pinned", "--checkpoint", str(self.creator.checkpoint),
                    "--ai-deck", str(decks[deck_name]), "--out", str(output),
                    "--bind", "127.0.0.1", "--port", str(self.port),
                    "--human-authorization", "self_recorded"]
            with log_path.open("ab") as log:
                self.process = subprocess.Popen(
                    argv, cwd=self.root, env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            self.session = identifier
            (output / "session.json").write_text(json.dumps({
                "schema_version": 1, "ai_deck": deck_name,
                "checkpoint": self.creator.checkpoint.name,
                "pid": getattr(self.process, "pid", None),
                "training_admitted": False,
            }, indent=2) + "\n", encoding="utf-8")
            return self.status()

    def _recording(self, directory: Path) -> dict | None:
        replays = sorted(directory.glob("game-*.yrpX"))
        if not replays:
            return None
        replay = replays[-1]
        stem = replay.with_suffix("")
        metadata_path = stem.with_suffix(".meta.json")
        review_path = stem.with_suffix(".review.json")
        record = {"native_replay": str(replay.relative_to(self.root)),
                  "review_ready": False, "viewer": None,
                  "verified": False, "training_admitted": False}
        if not metadata_path.is_file() or not review_path.is_file():
            return record
        stamp = max(replay.stat().st_mtime_ns, metadata_path.stat().st_mtime_ns,
                    review_path.stat().st_mtime_ns)
        with self.verify_lock:
            cached = self._verified.get(directory.name)
            if cached and cached[0] == stamp:
                return cached[1]
            try:
                report = verify_edopro_live_recording(
                    replay, review_path, metadata_path, self.creator.native_root)
                record["complete"] = report["complete"]
                viewer = stem.with_suffix(".html")
                if not viewer.is_file() or viewer.stat().st_mtime_ns < review_path.stat().st_mtime_ns:
                    render_replay(review_path, viewer, self.creator.native_root)
                record["viewer"] = "/" + viewer.relative_to(self.root).as_posix()
                record["verified"] = True
                record["review_ready"] = True
                record["experimental_confirmed_eligible"] = bool(
                    report.get("complete") and report.get("historical_patches")
                    and report.get("asset_identity_verified")
                    and report.get("deck_identity_verified"))
            except (ValueError, OSError, RuntimeError) as exc:
                record["verification_error"] = str(exc)
            self._verified[directory.name] = (stamp, record)
            return record

    def status(self, *, offset: int = 0, limit: int = 10) -> dict:
        # The room process is independent of the web server and can finish
        # while the page is closed. Recordings remain discoverable afterward.
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("invalid EDOPro session page")
        ready, reason = self.readiness()
        directories = (sorted(self.folder.glob("[0-9a-f]" * 16),
                              key=lambda path: path.stat().st_mtime_ns,
                              reverse=True) if self.folder.is_dir() else [])
        directories = [directory for directory in directories
                       if (directory / "session.json").is_file()]
        sessions = []
        for directory in directories[offset:offset + limit]:
            session = json.loads((directory / "session.json").read_text(encoding="utf-8"))
            current = directory.name == self.session
            running = current and self._room_running()
            recording = self._recording(directory)
            item = {"id": directory.name, "ai_deck": session["ai_deck"],
                    "running": running, "recording": recording}
            # A web-server restart loses the Popen handle. Keep the launch
            # failure visible for sessions that were started by this manager.
            if type(session.get("pid")) is int and not running and recording is None:
                log = directory / "room.log"
                detail = (log.read_text(encoding="utf-8", errors="replace")[-500:].strip()
                          if log.is_file() else "")
                item["error"] = detail or "The room exited before saving a duel"
            sessions.append(item)
        listening = False
        if self._room_running():
            with socket.socket() as probe:
                probe.settimeout(0.2)
                listening = probe.connect_ex(("127.0.0.1", self.port)) == 0
        return {"available": ready, "unavailable_reason": reason,
                "room_running": self._room_running(), "host": "127.0.0.1",
                "port": self.port, "listening": listening, "sessions": sessions,
                "session_offset": offset, "session_limit": limit,
                "session_count": len(directories),
                "training_admitted": False}
