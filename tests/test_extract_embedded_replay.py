"""Standalone viewers must restore the replay bytes bound to their hash."""

import hashlib
import json

import pytest

from scripts.extract_embedded_replay import extract_embedded_replay


def test_extract_embedded_replay_preserves_hash_and_rejects_tampering(tmp_path):
    payload = '{"schema_version":1,"decisions":[]}\n'
    digest = hashlib.sha256(payload.encode()).hexdigest()
    html = (
        '<script id="embedded-replay" type="application/json">'
        + payload[:-1] + '</script>'
        + '<script id="embedded-sha256" type="application/json">'
        + json.dumps(digest) + '</script>'
    )
    viewer = tmp_path / "viewer.html"
    output = tmp_path / "game.json"
    viewer.write_text(html, encoding="utf-8")
    assert extract_embedded_replay(viewer, output) == digest
    assert output.read_bytes() == payload.encode()
    with pytest.raises(FileExistsError):
        extract_embedded_replay(viewer, output)

    viewer.write_text(html.replace('"decisions":[]', '"decisions":[1]'),
                      encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        extract_embedded_replay(viewer, tmp_path / "tampered.json")
    assert not (tmp_path / "tampered.json").exists()
