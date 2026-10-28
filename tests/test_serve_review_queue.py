"""Local review saves remain legal, replay-bound, and confined to one queue."""

import json
import re
import shutil
import subprocess
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from goat_ai.actions import Action
from goat_ai.observations import Observation
from goat_ai.replay import DecisionRecord, Trajectory, read_decision_annotations, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts import serve_review_queue
from scripts import launch_review_server
from scripts.launch_review_server import server_healthy
from scripts.render_replay import render_replay
from scripts.shortlist_policy_disagreements import write_review_index


def _queue(tmp_path):
    view = Observation(viewer=0, acting_player=0, turn=1, phase="main1",
                       life_points=(8000, 8000), hand=(), field=(),
                       graveyards=((), ()), banished=((), ()),
                       opponent_hand_count=5, deck_counts=(35, 35),
                       extra_deck_counts=(0, 0))
    legal = (Action("a", "battle_phase", 0), Action("b", "end_phase", 0))
    trajectory = Trajectory("goat", ("a.ydk", "b.ydk"), 42,
                            (DecisionRecord(view, legal, legal[0]),), 0,
                            source="policy_evaluation",
                            skill_metadata={"demonstrator_seat": 0,
                                            "policy_checkpoint_sha256": "b" * 64})
    replay = tmp_path / "replay.json"
    write_trajectory(replay, trajectory)
    digest = sha256_file(replay)
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({
        "schema_version": 1,
        "purpose": "human_review_candidates_not_training_labels",
        "checkpoint_sha256": "b" * 64,
        "selected": [{"trajectory": replay.name, "trajectory_sha256": digest,
                      "decision_index": 0, "viewer_frame": 1, "seat": 0,
                      "turn": 1, "phase": "main1", "legal_action_count": 2,
                      "policy_action": {"kind": "battle_phase", "parameters": {}},
                      "teacher_action": {"kind": "end_phase", "parameters": {}}}],
    }))
    queue.with_suffix(".html").write_text("<html>Review queue</html>")
    return queue, replay, digest, trajectory


def _request(url, payload=None):
    if payload is None:
        request = Request(url)
    else:
        request = Request(url, data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json",
                                   "Origin": url.split("/api/")[0]}, method="POST")
    with urlopen(request, timeout=5) as response:
        return response.status, json.load(response)


def test_launcher_reuses_a_compatible_later_port_before_claiming_a_free_one(
        tmp_path, monkeypatch):
    queue, _, digest, _ = _queue(tmp_path)
    monkeypatch.setattr(launch_review_server, "ROOT", tmp_path)
    monkeypatch.setattr(launch_review_server, "PORTS", range(8765, 8768))
    route = "/queue.html"
    monkeypatch.setattr(launch_review_server, "server_queue",
                        lambda port: route if port == 8767 else None)
    monkeypatch.setattr(launch_review_server, "server_healthy",
                        lambda port, source: port == 8767 and source == digest)
    monkeypatch.setattr(launch_review_server, "port_in_use",
                        lambda port: (_ for _ in ()).throw(AssertionError("must reuse")))
    assert launch_review_server.launch(queue, open_browser=False) == (
        "http://127.0.0.1:8767/queue.html")


def test_local_review_saves_and_restores_valid_shortlisted_choices(tmp_path, monkeypatch):
    queue, replay, digest, trajectory = _queue(tmp_path)
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    output = tmp_path / "saved"
    server = serve_review_queue.make_server(queue, output, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert _request(f"{base}/api/review/state?source={digest}")[1] == {
            "choices": [], "offered": [0], "saved": True}
        assert _request(f"{base}/api/review/progress")[1] == {
            "choices": [], "notes": [], "total": 1}
        mark = {"source": digest, "decision_index": 0, "bookmarked": True}
        assert _request(f"{base}/api/review/bookmarks")[1] == {"bookmarks": []}
        assert _request(f"{base}/api/review/bookmark", mark)[1] == {
            "bookmarks": [{"source": digest, "decision_index": 0}]}
        assert _request(f"{base}/api/review/bookmarks")[1]["bookmarks"] == [
            {"source": digest, "decision_index": 0}]
        assert (output / "_review_state/bookmarks.json").is_file()
        assert list(output.glob("*.json")) == []
        for invalid_mark in ({**mark, "decision_index": 1},
                             {**mark, "bookmarked": 1},
                             {**mark, "source": "a" * 64}):
            with pytest.raises(HTTPError) as error:
                _request(f"{base}/api/review/bookmark", invalid_mark)
            assert error.value.code == 400
        payload = {"source": digest, "decision_index": 0, "action_index": 1}
        assert _request(f"{base}/api/review/choice", payload)[1]["choices"] == [
            {"decision_index": 0, "action_index": 1}]
        saved = output / f"{digest}.json"
        labels, records = read_decision_annotations(saved, digest, trajectory)
        assert labels.reviewer == "local-reviewer"
        assert records[0].selected_action == trajectory.decisions[0].legal_actions[1]
        assert _request(f"{base}/api/review/state?source={digest}")[1]["choices"] == [
            {"decision_index": 0, "action_index": 1}]
        assert _request(f"{base}/api/review/state?source={digest}")[1]["offered"] == [0]
        assert _request(f"{base}/api/review/progress")[1] == {
            "choices": [{"source": digest, "decision_index": 0, "action_index": 1}],
            "notes": [],
            "total": 1}
        for invalid in ({**payload, "action_index": 2},
                        {**payload, "decision_index": 1},
                        {**payload, "source": "a" * 64}):
            with pytest.raises(HTTPError) as error:
                _request(f"{base}/api/review/choice", invalid)
            assert error.value.code == 400
        assert saved.is_file()
        assert _request(f"{base}/api/review/choice",
                        {**payload, "action_index": None})[1]["choices"] == []
        assert not saved.exists()
        assert _request(f"{base}/api/review/progress")[1] == {
            "choices": [], "notes": [], "total": 1}
        assert _request(f"{base}/api/review/bookmark",
                        {**mark, "bookmarked": False})[1] == {"bookmarks": []}
        replay.write_text(replay.read_text() + " ")
        with pytest.raises(HTTPError) as error:
            _request(f"{base}/api/review/choice", payload)
        assert error.value.code == 400
        with pytest.raises(HTTPError) as error:
            _request(f"{base}/api/review/bookmark", mark)
        assert error.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_progress_checks_each_source_once_per_refresh(tmp_path, monkeypatch):
    queue, _, digest, _ = _queue(tmp_path)
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    store = serve_review_queue.ReviewStore(queue, tmp_path / "saved")
    store.choose(digest, 0, 1)
    store.save_note(digest, 0, "context", "Review later")
    original = store._trajectory
    checked = []

    def counted(source):
        checked.append(source)
        return original(source)

    monkeypatch.setattr(store, "_trajectory", counted)
    assert store.progress() == {
        "choices": [{"source": digest, "decision_index": 0, "action_index": 1}],
        "notes": [{"source": digest, "decision_index": 0, "kind": "context"}],
        "total": 1,
    }
    assert checked == [digest]


def test_rebuilt_queue_carries_choices_once_without_resurrecting_cleared_label(
        tmp_path, monkeypatch):
    queue, _, digest, _ = _queue(tmp_path)
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    parent = tmp_path / "review_labels"
    first = parent / sha256_file(queue)[:12]
    assert serve_review_queue.prepare_review_labels(queue, first) == 0
    serve_review_queue.ReviewStore(queue, first).choose(digest, 0, 1)
    serve_review_queue.ReviewStore(queue, first).save_note(
        digest, 0, "upstream_mistake", "Do not activate the Spell earlier")

    report = json.loads(queue.read_text())
    report["revision_note"] = "new review prompt wording"
    queue.write_text(json.dumps(report))
    second = parent / sha256_file(queue)[:12]
    assert serve_review_queue.prepare_review_labels(queue, second) == 1
    assert serve_review_queue.ReviewStore(queue, second).state(digest)["choices"] == [
        {"decision_index": 0, "action_index": 1}]
    assert serve_review_queue.ReviewStore(queue, second).note_state(digest)["notes"] == [
        {"decision_index": 0, "kind": "upstream_mistake",
         "text": "Do not activate the Spell earlier"}]
    assert serve_review_queue.prepare_review_labels(queue, second) == 0
    serve_review_queue.ReviewStore(queue, second).choose(digest, 0, None)
    serve_review_queue.ReviewStore(queue, second).save_note(digest, 0, "context", "")

    report["revision_note"] = "second revision"
    queue.write_text(json.dumps(report))
    third = parent / sha256_file(queue)[:12]
    assert serve_review_queue.prepare_review_labels(queue, third) == 0
    assert serve_review_queue.ReviewStore(queue, third).state(digest)["choices"] == []
    assert serve_review_queue.ReviewStore(queue, third).note_state(digest)["notes"] == []
    assert (first / f"{digest}.json").is_file()


def test_rebuilt_queue_does_not_import_untagged_or_other_queue_labels(tmp_path,
                                                                       monkeypatch):
    queue, _, digest, _ = _queue(tmp_path)
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    parent = tmp_path / "review_labels"
    untagged = parent / "old_without_identity"
    serve_review_queue.ReviewStore(queue, untagged).choose(digest, 0, 1)
    current = parent / sha256_file(queue)[:12]
    assert serve_review_queue.prepare_review_labels(queue, current) == 0
    assert serve_review_queue.ReviewStore(queue, current).state(digest)["choices"] == []
    other_queue = tmp_path / "another_queue.json"
    other_queue.write_bytes(queue.read_bytes())
    other_folder = parent / "other_queue"
    assert serve_review_queue.prepare_review_labels(other_queue, other_folder) == 0
    serve_review_queue.ReviewStore(other_queue, other_folder).choose(digest, 0, 1)
    report = json.loads(queue.read_text())
    report["revision_note"] = "new review"
    queue.write_text(json.dumps(report))
    revised = parent / sha256_file(queue)[:12]
    assert serve_review_queue.prepare_review_labels(queue, revised) == 0


def test_local_review_rejects_cross_origin_and_other_repo_files(tmp_path, monkeypatch):
    queue, _, digest, _ = _queue(tmp_path)
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    server = serve_review_queue.make_server(queue, tmp_path / "saved", port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/", timeout=5) as response:
            assert response.read() == b"<html>Review queue</html>"
        with pytest.raises(HTTPError) as error:
            urlopen(base + "/replay.json", timeout=5)
        assert error.value.code == 404
        payload = {"source": digest, "decision_index": 0, "action_index": 1}
        request = Request(base + "/api/review/choice", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json",
                                   "Origin": "https://example.com"}, method="POST")
        with pytest.raises(HTTPError) as error:
            urlopen(request, timeout=5)
        assert error.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_review_note_marks_upstream_mistake_without_training_label(tmp_path, monkeypatch):
    queue, _, digest, _ = _queue(tmp_path)
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    output = tmp_path / "saved"
    server = serve_review_queue.make_server(queue, output, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert server_healthy(server.server_port, digest)
        assert not server_healthy(server.server_port, "a" * 64)
        assert _request(f"{base}/api/review/notes?source={digest}")[1] == {"notes": []}
        note = {"source": digest, "decision_index": 0,
                "kind": "upstream_mistake", "text": "MST should not have activated"}
        assert _request(f"{base}/api/review/note", note)[1]["notes"] == [
            {"decision_index": 0, "kind": "upstream_mistake",
             "text": "MST should not have activated"}]
        assert _request(f"{base}/api/review/progress")[1]["choices"] == []
        assert not list(output.glob("*.json"))
        assert (output / "_review_state/notes" / f"{digest}.json").is_file()
        for invalid in ({**note, "decision_index": 1},
                        {**note, "source": "a" * 64},
                        {**note, "kind": "training_label"},
                        {**note, "text": "x" * 2001}):
            with pytest.raises(HTTPError) as error:
                _request(f"{base}/api/review/note", invalid)
            assert error.value.code == 400
        assert _request(f"{base}/api/review/note",
                        {**note, "kind": "context", "text": ""})[1] == {
            "notes": [], "saved": True}
        assert _request(f"{base}/api/review/notes?source={digest}")[1] == {"notes": []}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_browser_review_choice_autosaves_without_name_or_download(tmp_path, monkeypatch):
    queue, replay, digest, _ = _queue(tmp_path)
    viewer = tmp_path / "game.html"
    render_replay(replay, viewer, tmp_path / "native")
    probe = """<script>
      setTimeout(() => {
        const buttons = document.querySelectorAll('#legal button');
        buttons[1].click();
        setTimeout(() => { document.body.dataset.localReviewProbe = [
          localReviewMode, byId('manual-review-export').hidden,
          byId('annotation-status').textContent.includes('Saved on this computer'),
          byId('annotation-status').textContent.includes('different from AI played'),
          annotations.get(0)].join('|'); }, 250);
      }, 200);
    </script></body>"""
    viewer.write_text(viewer.read_text().replace("</body>", probe))
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    output = tmp_path / "saved"
    server = serve_review_queue.make_server(queue, output, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([
            shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--virtual-time-budget=1000", "--dump-dom",
            f"http://127.0.0.1:{server.server_port}/game.html",
        ], capture_output=True, text=True, timeout=20, check=True)
        match = re.search(r'data-local-review-probe="([^"]+)"', result.stdout)
        assert match, result.stderr[-1000:]
        assert match.group(1) == "true|true|true|true|1"
        raw = json.loads((output / f"{digest}.json").read_text())
        assert raw["choices"] == [{"decision_index": 0, "action_index": 1}]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_browser_upstream_note_saves_without_creating_action_label(tmp_path, monkeypatch):
    queue, replay, digest, _ = _queue(tmp_path)
    viewer = tmp_path / "game.html"
    render_replay(replay, viewer, tmp_path / "native")
    probe = """<script>
      setTimeout(() => {
        byId('review-note-kind').value = 'upstream_mistake';
        byId('review-note-kind').dispatchEvent(new Event('input'));
        byId('review-note').value = 'Do not activate MST earlier';
        byId('review-note').dispatchEvent(new Event('input'));
        byId('save-note').click();
        setTimeout(() => { document.body.dataset.noteProbe = [
          localReviewMode, reviewNotesAvailable,
          byId('review-note-status').textContent.includes('saved on this computer'),
          annotations.size, noteDirty].join('|'); }, 300);
      }, 200);
    </script></body>"""
    viewer.write_text(viewer.read_text().replace("</body>", probe))
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    output = tmp_path / "saved"
    server = serve_review_queue.make_server(queue, output, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([
            shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--virtual-time-budget=900", "--dump-dom",
            f"http://127.0.0.1:{server.server_port}/game.html",
        ], capture_output=True, text=True, timeout=20, check=True)
        match = re.search(r'data-note-probe="([^"]+)"', result.stdout)
        assert match, result.stderr[-1000:]
        assert match.group(1) == "true|true|true|0|false"
        path = output / "_review_state/notes" / f"{digest}.json"
        assert json.loads(path.read_text())["notes"] == [
            {"decision_index": 0, "kind": "upstream_mistake",
             "text": "Do not activate MST earlier"}]
        assert _request(f"http://127.0.0.1:{server.server_port}/api/review/progress")[1] == {
            "choices": [],
            "notes": [{"source": digest, "decision_index": 0,
                       "kind": "upstream_mistake"}],
            "total": 1,
        }
        assert not list(output.glob("*.json"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_queue_waits_for_automatic_save_before_leaving_duel(tmp_path, monkeypatch):
    queue, replay, digest, _ = _queue(tmp_path)
    viewer = tmp_path / "game.html"
    render_replay(replay, viewer, tmp_path / "native")
    selected = json.loads(queue.read_text())["selected"]
    selected[0]["viewer"] = str(viewer) + "#decision=1"
    selected[0]["audit_flags"] = []
    write_review_index(selected, queue, tmp_path / "native")
    probe = """<script>
      let warnings = 0;
      window.confirm = () => { warnings++; return false; };
      setTimeout(() => {
        frame.contentDocument.querySelector('#legal button:not(.recorded)').click();
        document.getElementById('back-to-queue').click();
        setTimeout(() => { document.body.dataset.saveBeforeLeave = [
          warnings, stage.hidden, labels.size, pendingLabels].join('|'); }, 600);
      }, 300);
    </script></html>"""
    page = queue.with_suffix(".html")
    page.write_text(page.read_text().replace("</html>", probe))
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    output = tmp_path / "saved"
    server = serve_review_queue.make_server(queue, output, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([
            shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--virtual-time-budget=1300", "--dump-dom",
            f"http://127.0.0.1:{server.server_port}/queue.html#item=1&mode=visible",
        ], capture_output=True, text=True, timeout=20, check=True)
        match = re.search(r'data-save-before-leave="([^"]+)"', result.stdout)
        assert match, result.stderr[-1000:]
        warning_count, hidden, _, pending = match.group(1).split("|")
        assert (warning_count, hidden, pending) == ("0", "true", "false")
        assert json.loads((output / f"{digest}.json").read_text())["choices"] == [
            {"decision_index": 0, "action_index": 1}]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_queue_bookmark_button_saves_without_creating_training_label(tmp_path, monkeypatch):
    queue, replay, digest, _ = _queue(tmp_path)
    viewer = tmp_path / "game.html"
    render_replay(replay, viewer, tmp_path / "native")
    selected = json.loads(queue.read_text())["selected"]
    selected[0]["viewer"] = str(viewer) + "#decision=1"
    selected[0]["audit_flags"] = []
    write_review_index(selected, queue, tmp_path / "native")
    probe = """<script>
      setTimeout(() => {
        const button = document.querySelector('.bookmark-item');
        button.click();
        setTimeout(() => { document.body.dataset.bookmarkProbe = [
          button.hidden, button.getAttribute('aria-pressed'),
          button.textContent.includes('Bookmarked')].join('|'); }, 200);
      }, 200);
    </script></html>"""
    page = queue.with_suffix(".html")
    page.write_text(page.read_text().replace("</html>", probe))
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    output = tmp_path / "saved"
    server = serve_review_queue.make_server(queue, output, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([
            shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--virtual-time-budget=700", "--dump-dom",
            f"http://127.0.0.1:{server.server_port}/queue.html",
        ], capture_output=True, text=True, timeout=20, check=True)
        match = re.search(r'data-bookmark-probe="([^"]+)"', result.stdout)
        assert match, result.stderr[-1000:]
        assert match.group(1) == "false|true|true"
        assert not list(output.glob("*.json"))
        assert json.loads((output / "_review_state/bookmarks.json").read_text())[
            "bookmarks"] == [{"source": digest, "decision_index": 0}]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(not shutil.which("chromium"), reason="Chromium unavailable")
def test_queue_hides_saved_labels_and_can_show_them_again(tmp_path, monkeypatch):
    queue, replay, digest, _ = _queue(tmp_path)
    viewer = tmp_path / "game.html"
    render_replay(replay, viewer, tmp_path / "native")
    selected = json.loads(queue.read_text())["selected"]
    selected[0]["viewer"] = str(viewer) + "#decision=1"
    selected[0]["audit_flags"] = []
    write_review_index(selected, queue, tmp_path / "native")
    probe = """<script>
      setTimeout(() => {
        const card = document.querySelector('.review-card');
        const before = document.getElementById('review-progress').textContent;
        card.querySelector('.primary').click();
        setTimeout(() => {
          document.getElementById('stage-frame').contentDocument
            .getElementById('label-recorded').click();
          setTimeout(() => {
            document.getElementById('back-to-queue').click();
            setTimeout(() => {
              const hidden = card.hidden;
              const progress = document.getElementById('review-progress').textContent;
              document.getElementById('show-labeled').click();
              document.body.dataset.progressProbe = [
                before.includes('0 of 1 review items labeled'), hidden,
                progress.includes('1 of 1 review items labeled'), !card.hidden,
                !card.querySelector('.label-status').hidden].join('|');
            }, 200);
          }, 300);
        }, 200);
      }, 200);
    </script></html>"""
    page = queue.with_suffix(".html")
    page.write_text(page.read_text().replace("</html>", probe))
    monkeypatch.setattr(serve_review_queue, "ROOT", tmp_path)
    output = tmp_path / "saved"
    server = serve_review_queue.make_server(queue, output, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run([
            shutil.which("chromium"), "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--virtual-time-budget=1800", "--dump-dom",
            f"http://127.0.0.1:{server.server_port}/queue.html",
        ], capture_output=True, text=True, timeout=20, check=True)
        match = re.search(r'data-progress-probe="([^"]+)"', result.stdout)
        assert match, result.stderr[-1000:]
        assert match.group(1) == "true|true|true|true|true"
        assert json.loads((output / f"{digest}.json").read_text())["choices"] == [
            {"decision_index": 0, "action_index": 0}]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
