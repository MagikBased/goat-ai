"""Open the newest local GOAT AI review queue with its save-enabled server."""

import argparse
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
SEARCH_DIRS = (ROOT / "replays", ROOT / ".cache/goat-ai")
LOG = ROOT / ".cache/goat-ai/review_server.log"


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


def server_healthy(port: int) -> bool:
    try:
        # A server from an earlier launch may still serve the same queue but
        # lack the progress endpoint needed by the current queue page.
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/review/progress",
                                    timeout=0.4) as response:
            return response.status == 200
    except (urllib.error.URLError, ValueError, OSError):
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def launch(queue: Path, *, open_browser: bool = True) -> str:
    queue = queue.resolve()
    if not queue.is_file() or not queue.is_relative_to(ROOT):
        raise ValueError("queue must be an existing file inside the goat-ai repository")
    if not queue.with_suffix(".html").is_file():
        raise ValueError(f"{queue.stem}.html is missing; refresh this queue first")
    route = "/" + queue.with_suffix(".html").relative_to(ROOT).as_posix()
    for port in range(8765, 8785):
        existing = server_queue(port)
        if existing == route and server_healthy(port):
            url = f"http://127.0.0.1:{port}{route}"
            if open_browser:
                webbrowser.open(url)
            return url
        if existing is not None or port_in_use(port):
            continue
        LOG.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT),
                                             env.get("PYTHONPATH", "")))
        with LOG.open("ab") as log:
            child = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts/serve_review_queue.py"),
                 str(queue), "--port", str(port)],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(40):
            if server_queue(port) == route:
                url = f"http://127.0.0.1:{port}{route}"
                if open_browser:
                    webbrowser.open(url)
                return url
            if child.poll() is not None:
                break
            time.sleep(0.1)
        if child.poll() is None:
            child.terminate()
        raise RuntimeError(f"review server did not start; see {LOG}")
    raise RuntimeError("no free review server port between 8765 and 8784")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", nargs="?", type=Path,
                        help="queue or recheck JSON to open; defaults to the newest local queue")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    queue = args.queue or latest_queue()
    if queue is None:
        parser.error("no review queue found; generate a queue first")
    print(launch(queue, open_browser=not args.no_browser), flush=True)


if __name__ == "__main__":
    main()
