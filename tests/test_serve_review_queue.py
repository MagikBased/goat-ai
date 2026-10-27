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
from scripts.render_replay import render_replay


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
            "choices": [], "saved": True}
        payload = {"source": digest, "decision_index": 0, "action_index": 1}
        assert _request(f"{base}/api/review/choice", payload)[1]["choices"] == [
            {"decision_index": 0, "action_index": 1}]
        saved = output / f"{digest}.json"
        labels, records = read_decision_annotations(saved, digest, trajectory)
        assert labels.reviewer == "local-reviewer"
        assert records[0].selected_action == trajectory.decisions[0].legal_actions[1]
        assert _request(f"{base}/api/review/state?source={digest}")[1]["choices"] == [
            {"decision_index": 0, "action_index": 1}]
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
        replay.write_text(replay.read_text() + " ")
        with pytest.raises(HTTPError) as error:
            _request(f"{base}/api/review/choice", payload)
        assert error.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


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
        assert match.group(1) == "true|true|true|1"
        raw = json.loads((output / f"{digest}.json").read_text())
        assert raw["choices"] == [{"decision_index": 0, "action_index": 1}]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
