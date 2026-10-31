"""Open a local review queue or AI game creator with its save-enabled server."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_API_VERSION = 5  # Keep in sync with serve_review_queue.py.
LIVE_API_VERSION = 16  # Increment when live-server behavior changes.
SEARCH_DIRS = (ROOT / "replays", ROOT / ".cache/goat-ai")
LOG = ROOT / ".cache/goat-ai/review_server.log"
PORTS = range(8765, 8865)


def latest_queue() -> Path | None:
    queues = (path for directory in SEARCH_DIRS if directory.exists()
              for name in ("queue.json", "recheck.json")
              for path in directory.glob(f"*/{name}")
              if path.with_suffix(".html").is_file())
    return max(queues, key=lambda path: (path.stat().st_mtime_ns, str(path)),
               default=None)


def server_queue(port: int) -> str | None:
    try:
        # The review server deliberately rejects HEAD; use GET without following
        # its redirect so the root Location identifies the served queue.
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(urllib.request.Request(f"http://127.0.0.1:{port}/"),
                         timeout=0.4) as response:
            return response.headers.get("Location")
    except urllib.error.HTTPError as error:
        return error.headers.get("Location") if error.code == 302 else None
    except (OSError, ValueError):
        return None


def port_in_use(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def server_healthy(port: int, source: str | None,
                   reviewer_alias: str = "local-reviewer",
                   queue_hash: str | None = None) -> bool:
    try:
        # A running process keeps its imported code after the files change.
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/review/version",
                                    timeout=5) as response:
            if response.status != 200 or json.load(response).get("api_version") != REVIEW_API_VERSION:
                return False
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/live/version",
                                    timeout=5) as response:
            if response.status != 200 or json.load(response).get("api_version") != LIVE_API_VERSION:
                return False
        # Older processes can report the same review API version while lacking
        # the game-audit route added afterward. Probe the route's validation.
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/games/audit?id=invalid",
                                   timeout=5)
            return False
        except urllib.error.HTTPError as error:
            if error.code != 400:
                return False
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/games/review",
                                   timeout=5)
            return False
        except urllib.error.HTTPError as error:
            if error.code != 405:
                return False
        if source is None:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/games/options", timeout=5) as response:
                return response.status == 200 and isinstance(
                    json.load(response).get("decks"), list)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/review/progress",
                                    timeout=5) as response:
            if response.status != 200 or not isinstance(
                    json.load(response).get("notes"), list):
                return False
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/review/state?source={source}",
                timeout=5) as response:
            if response.status != 200 or not isinstance(
                    json.load(response).get("offered"), list):
                return False
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/review/notes?source={source}",
                timeout=5) as response:
            if response.status != 200:
                return False
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/review/identity",
                timeout=5) as response:
            identity = json.load(response)
            return (response.status == 200
                    and identity.get("reviewer") == reviewer_alias
                    and (queue_hash is None or identity.get("queue_sha256") == queue_hash))
    except (urllib.error.URLError, ValueError, OSError):
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def launch(queue: Path | None, *, open_browser: bool = True,
           page: str = "queue", reviewer_alias: str = "local-reviewer") -> str:
    if page not in ("queue", "games"):
        raise ValueError("unknown server page")
    if queue is None and page != "games":
        raise ValueError("a review page requires a queue")
    if not reviewer_alias.strip():
        raise ValueError("reviewer alias must be nonempty")
    if queue is not None:
        queue = queue.resolve()
        if not queue.is_file() or not queue.is_relative_to(ROOT):
            raise ValueError("queue must be an existing file inside the goat-ai repository")
        if not queue.with_suffix(".html").is_file():
            raise ValueError(f"{queue.stem}.html is missing; refresh this queue first")
        selected = json.loads(queue.read_text(encoding="utf-8")).get("selected")
        if not isinstance(selected, list) or not selected:
            raise ValueError("review queue has no selected decisions")
        source = selected[0]["trajectory_sha256"]
        queue_hash = hashlib.sha256(queue.read_bytes()).hexdigest()
        route = "/" + queue.with_suffix(".html").relative_to(ROOT).as_posix()
    else:
        source = None
        queue_hash = None
        route = "/games/new"
    open_route = "/games/new" if page == "games" else route
    # Reuse a compatible server before claiming a free lower port. Reviewers
    # may still have older queue tabs open on several local ports.
    for port in reversed(PORTS):
        existing = server_queue(port)
        if (existing == route or (queue is None and existing is not None)) and server_healthy(
                port, source, reviewer_alias, queue_hash):
            url = f"http://127.0.0.1:{port}{open_route}"
            if open_browser:
                webbrowser.open(url)
            return url
    for port in PORTS:
        if port_in_use(port):
            continue
        LOG.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT),
                                             env.get("PYTHONPATH", "")))
        with LOG.open("ab") as log:
            alias_args = ([] if reviewer_alias == "local-reviewer" or queue is None else [
                "--reviewer-alias", reviewer_alias,
                "--output-dir", str(ROOT / ".cache/goat-ai/review_labels" /
                                    (queue_hash[:12] + "_" +
                                     hashlib.sha256(reviewer_alias.encode()).hexdigest()[:8]))])
            child = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts/serve_review_queue.py"),
                 *([str(queue)] if queue is not None else []), "--port", str(port),
                 *alias_args],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(40):
            if server_queue(port) == route:
                url = f"http://127.0.0.1:{port}{open_route}"
                if open_browser:
                    webbrowser.open(url)
                return url
            if child.poll() is not None:
                break
            time.sleep(0.1)
        if child.poll() is None:
            child.terminate()
        raise RuntimeError(f"review server did not start; see {LOG}")
    raise RuntimeError(f"no free review server port between {PORTS.start} and "
                       f"{PORTS.stop - 1}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", nargs="?", type=Path,
                        help="queue or recheck JSON to open; defaults to the newest local queue")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--game-creator", action="store_true",
                        help="open AI game creation instead of the review queue")
    args = parser.parse_args()
    queue = args.queue or latest_queue()
    if queue is None and not args.game_creator:
        parser.error("no review queue found; generate a queue first")
    print(launch(queue, open_browser=not args.no_browser,
                 page="games" if args.game_creator else "queue"), flush=True)


if __name__ == "__main__":
    main()
