"""Serve local review queues and verified AI game creation on this computer.

The localhost endpoint accepts only shortlisted, legal policy-seat choices.
Saved review files use the existing annotation schema. Generated AI matches
run through full native replay and visibility checks before being displayed.
"""

import argparse
import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

from goat_ai.agents.card_metadata import load_card_names
from goat_ai.replay import read_decision_annotations, read_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.create_viewer_game import GameCreator
from scripts.launch_review_server import launch
from scripts.live_human_game import LiveGameManager
from scripts.setup_card_images import cache_card_image, setup_card_backs
from scripts.setup_local_duel_sounds import HASHES as LOCAL_SOUND_HASHES
from scripts.validate_review_queue_labels import queue_sources, verify_queue_items

ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REVIEW_API_VERSION = 5
LIVE_API_VERSION = 6


def prepare_review_labels(queue: Path, output_dir: Path,
                          reviewer_alias: str = "local-reviewer") -> int:
    """Carry still-offered choices forward when this queue file is rebuilt.

    Only earlier folders explicitly tagged with this exact queue path and
    reviewer alias are considered. The earlier files remain untouched.
    """
    store = ReviewStore(queue, output_dir, reviewer_alias)
    identity_path = store.output_dir / "_review_state" / "queue_identity.json"
    identity = {"schema_version": 1,
                "queue_path": str(store.queue_path.relative_to(ROOT.resolve())),
                "queue_sha256": store.queue_sha256,
                "reviewer": store.reviewer_alias}
    if identity_path.is_file():
        if json.loads(identity_path.read_text(encoding="utf-8")) != identity:
            raise ValueError("review label folder belongs to another queue or reviewer")
        return 0
    # A preexisting untagged folder may contain hand-edited or older labels.
    # Never infer its origin or silently merge it with other queue revisions.
    if store.output_dir.exists() and any(store.output_dir.iterdir()):
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity_path.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
        return 0
    prior_folders = []
    for prior in sorted(store.output_dir.parent.iterdir()) if store.output_dir.parent.exists() else []:
        if not prior.is_dir() or prior == store.output_dir:
            continue
        metadata = prior / "_review_state" / "queue_identity.json"
        if not metadata.is_file():
            continue
        previous = json.loads(metadata.read_text(encoding="utf-8"))
        if (previous.get("schema_version") != 1
                or previous.get("queue_path") != identity["queue_path"]
                or previous.get("reviewer") != store.reviewer_alias):
            continue
        prior_folders.append((metadata.stat().st_mtime_ns, prior))
    # Use only the latest revision. A reviewer may deliberately clear a choice
    # there; consulting older revisions would resurrect that rejected label.
    previous_dir = max(prior_folders, default=(0, None))[1]
    candidates: dict[tuple[str, int], int] = {}
    for path in previous_dir.glob("*.json") if previous_dir else []:
        digest = path.stem
        if digest not in store.sources:
            continue
        trajectory, offered = store._trajectory(digest)
        labels, _ = read_decision_annotations(path, digest, trajectory)
        if labels.reviewer != store.reviewer_alias:
            raise ValueError(f"{path}: reviewer differs from queue identity")
        for decision, action in labels.choices:
            if decision in offered:
                candidates[(digest, decision)] = action
    carried = 0
    for (digest, decision), action in sorted(candidates.items()):
        store.choose(digest, decision, action)
        carried += 1
    if previous_dir:
        for path in (previous_dir / "_review_state" / "notes").glob("*.json"):
            digest = path.stem
            if digest not in store.sources:
                continue
            _, offered = store._trajectory(digest)
            for note in store._read_notes(path, digest, None):
                if note["decision_index"] in offered:
                    store.save_note(digest, note["decision_index"], note["kind"],
                                    note["text"])
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    identity_path.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    return carried


class ReviewStore:
    """Keep one validated annotation file per source replay."""

    def __init__(self, queue: Path, output_dir: Path,
                 reviewer_alias: str = "local-reviewer"):
        if not reviewer_alias.strip():
            raise ValueError("reviewer alias must be nonempty")
        self.queue_path = queue.resolve()
        self.queue_sha256 = sha256_file(queue)
        self.queue = json.loads(queue.read_text(encoding="utf-8"))
        self.sources = queue_sources(self.queue, self.queue_path)
        self.output_dir = output_dir.resolve()
        self.reviewer_alias = reviewer_alias.strip()
        self.lock = Lock()

    @property
    def bookmark_path(self) -> Path:
        # Keep review reminders outside the annotation glob used by training.
        return self.output_dir / "_review_state" / "bookmarks.json"

    def _bookmarks(self) -> set[tuple[str, int]]:
        path = self.bookmark_path
        if not path.is_file():
            return set()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (payload.get("schema_version") != 1
                or payload.get("queue_sha256") != self.queue_sha256
                or not isinstance(payload.get("bookmarks"), list)):
            raise ValueError("saved bookmarks do not match this queue")
        marks = set()
        for mark in payload["bookmarks"]:
            if (not isinstance(mark, dict) or set(mark) != {"source", "decision_index"}
                    or mark["source"] not in self.sources
                    or type(mark["decision_index"]) is not int
                    or mark["decision_index"] not in self.sources[mark["source"]][1]):
                raise ValueError("saved bookmark is outside this queue")
            marks.add((mark["source"], mark["decision_index"]))
        return marks

    def bookmark_state(self) -> dict:
        with self.lock:
            if sha256_file(self.queue_path) != self.queue_sha256:
                raise ValueError("review queue changed while serving")
            return {"bookmarks": [{"source": source, "decision_index": index}
                                  for source, index in sorted(self._bookmarks())]}

    def bookmark(self, digest: str, decision_index: int, bookmarked: bool) -> dict:
        with self.lock:
            if type(bookmarked) is not bool or type(decision_index) is not int:
                raise ValueError("invalid bookmark payload")
            self.label_path(digest)
            _, offered = self._trajectory(digest)
            if decision_index not in offered:
                raise ValueError("decision is absent from this queue")
            marks = self._bookmarks()
            key = (digest, decision_index)
            if bookmarked:
                marks.add(key)
            else:
                marks.discard(key)
            path = self.bookmark_path
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"schema_version": 1, "queue_sha256": self.queue_sha256,
                       "bookmarks": [{"source": source, "decision_index": index}
                                     for source, index in sorted(marks)]}
            temporary = path.with_suffix(".json.tmp")
            try:
                temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            return {"bookmarks": payload["bookmarks"]}

    def label_path(self, digest: str) -> Path:
        if not SHA256.fullmatch(digest) or digest not in self.sources:
            raise ValueError("source replay is absent from this queue")
        return self.output_dir / f"{digest}.json"

    def note_path(self, digest: str) -> Path:
        self.label_path(digest)
        return self.output_dir / "_review_state" / "notes" / f"{digest}.json"

    def _read_notes(self, path: Path, digest: str,
                    offered: set[int] | None) -> list[dict]:
        if not path.is_file():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(payload, dict) or payload.get("schema_version") != 1
                or payload.get("source_trajectory_sha256") != digest
                or payload.get("reviewer") != self.reviewer_alias
                or not isinstance(payload.get("notes"), list)):
            raise ValueError("review notes do not match this replay or reviewer")
        seen = set()
        for note in payload["notes"]:
            if (not isinstance(note, dict)
                    or set(note) != {"decision_index", "kind", "text"}
                    or type(note["decision_index"]) is not int
                    or note["decision_index"] < 0
                    or offered is not None and note["decision_index"] not in offered
                    or note["decision_index"] in seen
                    or note["kind"] not in ("context", "upstream_mistake",
                                            "reject_recorded")
                    or not isinstance(note["text"], str)
                    or len(note["text"]) > 2000):
                raise ValueError("invalid review note or decision outside this queue")
            seen.add(note["decision_index"])
        return payload["notes"]

    def note_state(self, digest: str) -> dict:
        path = self.note_path(digest)
        with self.lock:
            _, offered = self._trajectory(digest)
            return {"notes": self._read_notes(path, digest, offered)}

    def save_note(self, digest: str, decision_index: int,
                  kind: str, content: str) -> dict:
        path = self.note_path(digest)
        with self.lock:
            trajectory, offered = self._trajectory(digest)
            if (type(decision_index) is not int or decision_index not in offered
                    or kind not in ("context", "upstream_mistake",
                                    "reject_recorded")
                    or not isinstance(content, str) or len(content) > 2000):
                raise ValueError("invalid review note or decision outside this queue")
            if kind == "reject_recorded":
                label_path = self.label_path(digest)
                if label_path.is_file():
                    labels, _ = read_decision_annotations(label_path, digest, trajectory)
                    if any(index == decision_index for index, _ in labels.choices):
                        raise ValueError("clear the saved action choice before rejecting the recorded action")
            notes = {note["decision_index"]: note for note in
                     self._read_notes(path, digest, offered)}
            text = content.strip()
            if kind == "context" and not text:
                notes.pop(decision_index, None)
            else:
                notes[decision_index] = {"decision_index": decision_index,
                                         "kind": kind, "text": text}
            if not notes:
                path.unlink(missing_ok=True)
                return {"notes": [], "saved": True}
            payload = {"schema_version": 1, "source_trajectory_sha256": digest,
                       "reviewer": self.reviewer_alias,
                       "notes": [notes[index] for index in sorted(notes)]}
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            try:
                temporary.write_text(json.dumps(payload, indent=2) + "\n",
                                     encoding="utf-8")
                self._read_notes(temporary, digest, offered)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            return {"notes": payload["notes"], "saved": True}

    def _trajectory(self, digest: str):
        if sha256_file(self.queue_path) != self.queue_sha256:
            raise ValueError("review queue changed while serving")
        replay_path, offered = self.sources[digest]
        if sha256_file(replay_path) != digest:
            raise ValueError("source replay SHA-256 changed")
        trajectory = read_trajectory(replay_path)
        verify_queue_items(trajectory, offered, self.queue["checkpoint_sha256"])
        return trajectory, offered

    def state(self, digest: str) -> dict:
        path = self.label_path(digest)
        with self.lock:
            trajectory, offered = self._trajectory(digest)
            if not path.is_file():
                return {"choices": [], "offered": sorted(offered), "saved": True}
            labels, _ = read_decision_annotations(path, digest, trajectory)
            if labels.reviewer != self.reviewer_alias:
                raise ValueError("saved labels belong to another reviewer alias")
            if any(index not in offered for index, _ in labels.choices):
                raise ValueError("saved label is outside this queue")
            return {"choices": [{"decision_index": index, "action_index": action}
                                for index, action in labels.choices],
                    "offered": sorted(offered), "saved": True}

    def progress(self) -> dict:
        """Report saved choices for this queue without exposing replay hidden state."""
        choices = []
        notes = []
        with self.lock:
            for digest in sorted(self.sources):
                trajectory, offered = self._trajectory(digest)
                path = self.label_path(digest)
                if path.is_file():
                    labels, _ = read_decision_annotations(path, digest, trajectory)
                    if labels.reviewer != self.reviewer_alias:
                        raise ValueError("saved labels belong to another reviewer alias")
                    for decision, action in labels.choices:
                        if decision not in offered:
                            raise ValueError("saved label is outside this queue")
                        choices.append({"source": digest, "decision_index": decision,
                                        "action_index": action})
                for note in self._read_notes(self.note_path(digest), digest, offered):
                    notes.append({"source": digest,
                                  "decision_index": note["decision_index"],
                                  "kind": note["kind"]})
        return {"choices": choices,
                "notes": notes,
                "total": sum(len(offered) for _, offered in self.sources.values())}

    def choose(self, digest: str, decision_index: int, action_index: int | None) -> dict:
        path = self.label_path(digest)
        with self.lock:
            trajectory, offered = self._trajectory(digest)
            if type(decision_index) is not int or decision_index not in offered:
                raise ValueError("decision is absent from this queue")
            legal = trajectory.decisions[decision_index].legal_actions
            if action_index is not None and (type(action_index) is not int
                                             or not 0 <= action_index < len(legal)):
                raise ValueError("action index is not legal at this decision")
            choices = {}
            if path.is_file():
                old, _ = read_decision_annotations(path, digest, trajectory)
                if old.reviewer != self.reviewer_alias:
                    raise ValueError("saved labels belong to another reviewer alias")
                choices.update(old.choices)
                if any(index not in offered for index in choices):
                    raise ValueError("saved label is outside this queue")
            if action_index is None:
                choices.pop(decision_index, None)
            else:
                if any(note["decision_index"] == decision_index
                       and note["kind"] == "reject_recorded"
                       for note in self._read_notes(self.note_path(digest), digest, offered)):
                    raise ValueError("clear the recorded-action rejection before choosing an action")
                choices[decision_index] = action_index
            if not choices:
                path.unlink(missing_ok=True)
                return {"choices": [], "saved": True}
            payload = {"schema_version": 1,
                       "source_trajectory_sha256": digest,
                       "authorization": "policy_review",
                       "reviewer": self.reviewer_alias,
                       "choices": [{"decision_index": index, "action_index": choice}
                                   for index, choice in sorted(choices.items())]}
            self.output_dir.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            try:
                temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                read_decision_annotations(temporary, digest, trajectory)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            return {"choices": payload["choices"], "saved": True}


def make_server(queue: Path | None, output_dir: Path | None, *, port: int = 8765,
                host: str = "127.0.0.1",
                reviewer_alias: str = "local-reviewer") -> ThreadingHTTPServer:
    if queue is not None:
        queue = queue.resolve()
        if not queue.is_file() or not queue.is_relative_to(ROOT):
            raise ValueError("queue must be an existing file inside this repository")
        if not queue.with_suffix(".html").is_file():
            raise ValueError("queue HTML is missing; refresh the queue first")
        if output_dir is None:
            raise ValueError("review queue requires a label output directory")
    store = ReviewStore(queue, output_dir, reviewer_alias) if queue is not None else None
    creator = GameCreator(root=ROOT)
    live = LiveGameManager(creator)
    image_locks_lock = Lock()
    image_locks: dict[int, Lock] = {}
    try:
        allowed_image_codes = set(load_card_names(creator.native_root))
    except FileNotFoundError:
        allowed_image_codes = set()
    start_path = ("/" + queue.with_suffix(".html").relative_to(ROOT).as_posix()
                  if queue is not None else "/games/new")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT), **kwargs)

        def end_headers(self) -> None:
            if urlsplit(self.path).path.endswith(".html"):
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_HEAD(self) -> None:
            self.send_error(405, "HEAD is not used by the review viewer")

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            sound = re.fullmatch(r"/local-duel-sounds/([a-z]+\.wav)", parsed.path)
            if sound:
                name = sound.group(1)
                target = ROOT / ".cache/goat-ai/duel_sounds" / name
                if name not in LOCAL_SOUND_HASHES or not target.is_file():
                    self.send_error(404, "local duel sound unavailable")
                    return
                data = target.read_bytes()
                if len(data) > 2_000_000:
                    self.send_error(404, "local duel sound invalid")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "private, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path in ("/replays/card_images/cover.png",
                               "/replays/card_images/cover2.png"):
                with image_locks_lock:
                    back_lock = image_locks.setdefault(0, Lock())
                with back_lock:
                    try:
                        target = ROOT / parsed.path.lstrip("/")
                        if not target.is_file():
                            setup_card_backs(target.parent)
                    except (ValueError, OSError, URLError):
                        self.send_error(503, "card back source unavailable")
                        return
            art_match = re.fullmatch(r"/replays/card_images/([0-9]{1,10})\.jpg", parsed.path)
            if art_match:
                code = int(art_match.group(1))
                if code not in allowed_image_codes:
                    self.send_error(404, "unknown card image")
                    return
                with image_locks_lock:
                    image_lock = image_locks.setdefault(code, Lock())
                with image_lock:
                    try:
                        target = ROOT / "replays/card_images" / f"{code}.jpg"
                        if not target.is_file() and not cache_card_image(
                                code, target.parent, creator.native_root):
                            self.send_error(404, "card image unavailable")
                            return
                    except (ValueError, OSError, URLError):
                        self.send_error(503, "card image source unavailable")
                        return
            if parsed.path == "/":
                self.send_response(302)
                self.send_header("Location", start_path)
                self.end_headers()
                return
            if parsed.path == "/games/new":
                self.send_response(302)
                self.send_header("Location", "/examples/create_game.html")
                self.end_headers()
                return
            if parsed.path == "/games/play":
                self.send_response(302)
                self.send_header("Location", "/examples/play_game.html")
                self.end_headers()
                return
            if parsed.path == "/api/live/state":
                try:
                    self._json(200, live.get(parse_qs(parsed.query).get("id", [""])[0]))
                except (ValueError, OSError) as error:
                    self._json(400, {"error": str(error)})
                return
            if parsed.path == "/api/live/version":
                self._json(200, {"api_version": LIVE_API_VERSION})
                return
            if parsed.path == "/api/games/options":
                self._json(200, creator.options())
                return
            if parsed.path == "/api/games/audit":
                identifier = parse_qs(parsed.query).get("id", [""])[0]
                try:
                    self._json(200, creator.audit(identifier))
                except (ValueError, OSError) as error:
                    self._json(400, {"error": str(error)})
                return
            if parsed.path == "/api/games/review":
                self._json(405, {"error": "POST required"})
                return
            if parsed.path == "/api/review/version":
                self._json(200, {"api_version": REVIEW_API_VERSION})
                return
            if parsed.path.startswith("/api/review/") and store is None:
                self._json(404, {"error": "no review queue is open"})
                return
            if parsed.path == "/api/review/state":
                digest = parse_qs(parsed.query).get("source", [""])[0]
                try:
                    self._json(200, store.state(digest))
                except (ValueError, KeyError, OSError) as error:
                    self._json(400, {"error": str(error)})
                return
            if parsed.path == "/api/review/bookmarks":
                try:
                    self._json(200, store.bookmark_state())
                except (ValueError, KeyError, TypeError, OSError) as error:
                    self._json(400, {"error": str(error)})
                return
            if parsed.path == "/api/review/notes":
                digest = parse_qs(parsed.query).get("source", [""])[0]
                try:
                    self._json(200, store.note_state(digest))
                except (ValueError, KeyError, TypeError, OSError) as error:
                    self._json(400, {"error": str(error)})
                return
            if parsed.path == "/api/review/progress":
                try:
                    self._json(200, store.progress())
                except (ValueError, KeyError, TypeError, OSError) as error:
                    self._json(400, {"error": str(error)})
                return
            if parsed.path == "/api/review/identity":
                self._json(200, {"queue_sha256": store.queue_sha256,
                                 "reviewer": store.reviewer_alias})
                return
            target = Path(self.translate_path(self.path)).resolve()
            queue_html = (queue is not None and target.is_relative_to(queue.parent)
                          and target.suffix == ".html")
            art = (target.is_relative_to(ROOT / "replays/card_images")
                   and target.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
            creator_html = target in (ROOT / "examples/create_game.html",
                                      ROOT / "examples/play_game.html")
            duel_audio = target == ROOT / "examples/duel_audio.js"
            game_html = (target.is_relative_to(creator.output_dir)
                         and target.suffix == ".html")
            if not (queue_html or art or creator_html or duel_audio or game_html):
                self.send_error(404, "Only review, game, and card-art pages are served")
                return
            super().do_GET()

        def do_POST(self) -> None:
            endpoint = urlsplit(self.path).path
            if endpoint not in ("/api/review/choice", "/api/review/bookmark",
                                "/api/review/note", "/api/review/upstream",
                                "/api/games", "/api/games/review",
                                "/api/live/start", "/api/live/choice",
                                "/api/live/close"):
                self._json(404, {"error": "unknown endpoint"})
                return
            if endpoint not in ("/api/games", "/api/games/review",
                                "/api/live/start", "/api/live/choice",
                                "/api/live/close") and store is None:
                self._json(404, {"error": "no review queue is open"})
                return
            origin = self.headers.get("Origin")
            host_header = self.headers.get("Host")
            if (origin and origin != f"http://{host_header}") or (
                    self.headers.get_content_type() != "application/json"):
                self._json(403, {"error": "same-origin JSON request required"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 1 <= size <= (16384 if endpoint == "/api/review/note" else 4096):
                    raise ValueError("request body size is invalid")
                data = json.loads(self.rfile.read(size))
                expected = ({"id"} if endpoint in ("/api/games/review",
                                                 "/api/live/close") else
                            {"deck1", "deck2", "human_seat", "opponent", "seed"}
                            if endpoint == "/api/live/start" else
                            {"id", "action_index", "expected_decisions"}
                            if endpoint == "/api/live/choice" else
                            {"deck1", "deck2", "agent1", "agent2", "seed"}
                            if endpoint == "/api/games" else
                            {"source", "decision_index", "action_index"}
                            if endpoint == "/api/review/choice" else
                            {"source", "decision_index", "bookmarked"}
                            if endpoint == "/api/review/bookmark" else
                            {"source", "decision_index"}
                            if endpoint == "/api/review/upstream" else
                            {"source", "decision_index", "kind", "text"})
                valid = isinstance(data, dict) and (
                    set(data) == expected or
                    (endpoint == "/api/live/choice" and
                     set(data) in (expected | {"manual"},
                                   expected | {"hold_priority"},
                                   expected | {"manual", "hold_priority"})))
                if not valid:
                    raise ValueError("invalid review payload")
                if endpoint == "/api/games/review":
                    result = {"url": launch(creator.review_queue(data["id"]),
                                            open_browser=False)}
                elif endpoint == "/api/live/start":
                    result = live.start(data)
                elif endpoint == "/api/live/choice":
                    result = live.choose(data["id"], data["action_index"],
                                         data["expected_decisions"],
                                         data.get("manual"),
                                         data.get("hold_priority", False))
                elif endpoint == "/api/live/close":
                    result = live.close(data["id"])
                elif endpoint == "/api/games":
                    result = creator.create(data)
                elif endpoint == "/api/review/choice":
                    result = store.choose(data["source"], data["decision_index"],
                                          data["action_index"])
                elif endpoint == "/api/review/bookmark":
                    result = store.bookmark(data["source"], data["decision_index"],
                                            data["bookmarked"])
                elif endpoint == "/api/review/upstream":
                    from scripts.create_upstream_review import create_upstream_review
                    digest, index = data["source"], data["decision_index"]
                    store.label_path(digest)
                    if type(index) is not int:
                        raise ValueError("invalid upstream decision index")
                    item_number = next((number for number, item in
                                        enumerate(store.queue["selected"], 1)
                                        if item["trajectory_sha256"] == digest
                                        and item["decision_index"] == index), None)
                    if item_number is None:
                        raise ValueError("decision is absent from this queue")
                    upstream = queue.parent / f"upstream_{item_number}.json"
                    create_upstream_review(queue, item_number, None, upstream,
                                           creator.native_root)
                    result = {"url": launch(upstream, open_browser=False,
                                            reviewer_alias=store.reviewer_alias)}
                else:
                    result = store.save_note(data["source"], data["decision_index"],
                                             data["kind"], data["text"])
            except (ValueError, TypeError, KeyError, OSError, RuntimeError) as error:
                self._json(400, {"error": str(error)})
                return
            self._json(200, result)

    class LiveServer(ThreadingHTTPServer):
        def server_close(self) -> None:
            live.close_all()
            super().server_close()

    return LiveServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", nargs="?", type=Path,
                        help="existing queue.json; omit for game creator only")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output-dir", type=Path,
                        help="ignored label folder; defaults to a queue-hash-specific cache folder")
    parser.add_argument("--reviewer-alias", default="local-reviewer",
                        help="optional provenance alias when separate people review the same queue")
    args = parser.parse_args()
    digest = sha256_file(args.queue) if args.queue else None
    output = (args.output_dir or ROOT / ".cache/goat-ai/review_labels" / digest[:12]
              if digest else None)
    carried = (prepare_review_labels(args.queue, output, args.reviewer_alias)
               if args.queue else 0)
    server = make_server(args.queue, output, port=args.port,
                         reviewer_alias=args.reviewer_alias)
    path = (args.queue.resolve().with_suffix(".html").relative_to(ROOT).as_posix()
            if args.queue else "games/new")
    print(f"Open http://127.0.0.1:{server.server_port}/{path}", flush=True)
    if output:
        print(f"Choices save in {output.resolve()}", flush=True)
    if carried:
        print(f"Carried {carried} matching choices from an earlier queue revision", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
