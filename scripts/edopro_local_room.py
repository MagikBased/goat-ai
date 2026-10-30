"""Launch and inspect one private EDOPro policy room from the local web UI."""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from threading import Lock
from uuid import uuid4

from goat_ai.replay.edopro_live_verify import verify_edopro_live_recording
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
        return self.process is not None and self.process.poll() is None

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
                record["verified"] = True
                record["review_ready"] = True
                record["complete"] = report["complete"]
                viewer = stem.with_suffix(".html")
                if not viewer.is_file() or viewer.stat().st_mtime_ns < review_path.stat().st_mtime_ns:
                    render_replay(review_path, viewer, self.creator.native_root)
                record["viewer"] = "/" + viewer.relative_to(self.root).as_posix()
            except (ValueError, OSError, RuntimeError) as exc:
                record["verification_error"] = str(exc)
            self._verified[directory.name] = (stamp, record)
            return record

    def status(self) -> dict:
        # The room process is independent of the web server and can finish
        # while the page is closed. Recordings remain discoverable afterward.
        ready, reason = self.readiness()
        sessions = []
        for directory in sorted(self.folder.glob("[0-9a-f]" * 16),
                                key=lambda path: path.stat().st_mtime_ns,
                                reverse=True)[:10] if self.folder.is_dir() else []:
            metadata = directory / "session.json"
            if not metadata.is_file():
                continue
            session = json.loads(metadata.read_text(encoding="utf-8"))
            current = directory.name == self.session
            running = current and self._room_running()
            recording = self._recording(directory)
            item = {"id": directory.name, "ai_deck": session["ai_deck"],
                    "running": running, "recording": recording}
            if current and self.process is not None and not running and recording is None:
                log = directory / "room.log"
                item["error"] = (log.read_text(encoding="utf-8", errors="replace")[-500:]
                                 if log.is_file() else "The room exited before saving a duel")
            sessions.append(item)
        listening = False
        if self._room_running():
            with socket.socket() as probe:
                probe.settimeout(0.2)
                listening = probe.connect_ex(("127.0.0.1", self.port)) == 0
        return {"available": ready, "unavailable_reason": reason,
                "room_running": self._room_running(), "host": "127.0.0.1",
                "port": self.port, "listening": listening, "sessions": sessions,
                "training_admitted": False}
