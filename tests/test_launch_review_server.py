"""The desktop launcher opens the newest generated review page."""

import os

from scripts import launch_review_server


def test_latest_queue_includes_recheck_and_skips_missing_pages(tmp_path, monkeypatch):
    regular = tmp_path / "replays" / "regular"
    recheck = tmp_path / "cache" / "recheck"
    incomplete = tmp_path / "cache" / "incomplete"
    for folder in (regular, recheck, incomplete):
        folder.mkdir(parents=True)
    old = regular / "queue.json"
    newest = recheck / "recheck.json"
    unusable = incomplete / "queue.json"
    for path in (old, newest, unusable):
        path.write_text("{}")
    old.with_suffix(".html").write_text("old")
    newest.with_suffix(".html").write_text("new")
    os.utime(old, (100, 100))
    os.utime(newest, (200, 200))
    os.utime(unusable, (300, 300))
    monkeypatch.setattr(launch_review_server, "SEARCH_DIRS",
                        (tmp_path / "replays", tmp_path / "cache"))

    assert launch_review_server.latest_queue() == newest
    newest.with_suffix(".html").unlink()
    assert launch_review_server.latest_queue() == old
