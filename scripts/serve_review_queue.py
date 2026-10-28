"""Serve an existing review queue and save choices immediately on this computer.

The localhost endpoint accepts only shortlisted, legal policy-seat choices.
Saved files use the existing annotation schema; the full native replay and
visibility audit still run when those files are validated for training.
"""

import argparse
import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlsplit

from goat_ai.replay import read_decision_annotations, read_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.validate_review_queue_labels import queue_sources, verify_queue_items

ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


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
        for digest in sorted(self.sources):
            for choice in self.state(digest)["choices"]:
                choices.append({"source": digest, **choice})
        return {"choices": choices,
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


def make_server(queue: Path, output_dir: Path, *, port: int = 8765,
                host: str = "127.0.0.1",
                reviewer_alias: str = "local-reviewer") -> ThreadingHTTPServer:
    queue = queue.resolve()
    if not queue.is_file() or not queue.is_relative_to(ROOT):
        raise ValueError("queue must be an existing file inside this repository")
    if not queue.with_suffix(".html").is_file():
        raise ValueError("queue HTML is missing; refresh the queue first")
    store = ReviewStore(queue, output_dir, reviewer_alias)
    start_path = "/" + queue.with_suffix(".html").relative_to(ROOT).as_posix()

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
            if parsed.path == "/":
                self.send_response(302)
                self.send_header("Location", start_path)
                self.end_headers()
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
            if parsed.path == "/api/review/progress":
                try:
                    self._json(200, store.progress())
                except (ValueError, KeyError, TypeError, OSError) as error:
                    self._json(400, {"error": str(error)})
                return
            target = Path(self.translate_path(self.path)).resolve()
            queue_html = target.is_relative_to(queue.parent) and target.suffix == ".html"
            art = (target.is_relative_to(ROOT / "replays/card_images")
                   and target.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
            if not (queue_html or art):
                self.send_error(404, "Only review pages and card art are served")
                return
            super().do_GET()

        def do_POST(self) -> None:
            endpoint = urlsplit(self.path).path
            if endpoint not in ("/api/review/choice", "/api/review/bookmark"):
                self._json(404, {"error": "unknown endpoint"})
                return
            origin = self.headers.get("Origin")
            host_header = self.headers.get("Host")
            if (origin and origin != f"http://{host_header}") or (
                    self.headers.get_content_type() != "application/json"):
                self._json(403, {"error": "same-origin JSON request required"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 1 <= size <= 4096:
                    raise ValueError("request body size is invalid")
                data = json.loads(self.rfile.read(size))
                expected = ({"source", "decision_index", "action_index"}
                            if endpoint == "/api/review/choice" else
                            {"source", "decision_index", "bookmarked"})
                if not isinstance(data, dict) or set(data) != expected:
                    raise ValueError("invalid review payload")
                if endpoint == "/api/review/choice":
                    result = store.choose(data["source"], data["decision_index"],
                                          data["action_index"])
                else:
                    result = store.bookmark(data["source"], data["decision_index"],
                                            data["bookmarked"])
            except (ValueError, TypeError, KeyError, OSError) as error:
                self._json(400, {"error": str(error)})
                return
            self._json(200, result)

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path, help="existing queue.json inside this repository")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output-dir", type=Path,
                        help="ignored label folder; defaults to a queue-hash-specific cache folder")
    parser.add_argument("--reviewer-alias", default="local-reviewer",
                        help="optional provenance alias when separate people review the same queue")
    args = parser.parse_args()
    digest = sha256_file(args.queue)
    output = args.output_dir or ROOT / ".cache/goat-ai/review_labels" / digest[:12]
    server = make_server(args.queue, output, port=args.port,
                         reviewer_alias=args.reviewer_alias)
    path = args.queue.resolve().with_suffix(".html").relative_to(ROOT).as_posix()
    print(f"Open http://127.0.0.1:{server.server_port}/{path}", flush=True)
    print(f"Choices save in {output.resolve()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
