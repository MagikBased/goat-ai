import os

from goat_ai.replay import fingerprint


def test_pinned_asset_hash_reused_and_invalidated_by_replacement(tmp_path, monkeypatch):
    asset = tmp_path / "cards.cdb"
    asset.write_bytes(b"first")
    calls = []
    original = fingerprint.sha256_file

    def tracked(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(fingerprint, "sha256_file", tracked)
    fingerprint._hash_unchanged_file.cache_clear()
    before = fingerprint.sha256_unchanged_file(asset)
    assert fingerprint.sha256_unchanged_file(asset) == before
    assert len(calls) == 1

    old = asset.stat()
    replacement = tmp_path / "replacement.cdb"
    replacement.write_bytes(b"other")
    os.utime(replacement, ns=(old.st_atime_ns, old.st_mtime_ns))
    replacement.replace(asset)
    assert asset.stat().st_size == old.st_size
    assert asset.stat().st_mtime_ns == old.st_mtime_ns
    assert asset.stat().st_ino != old.st_ino
    assert fingerprint.sha256_unchanged_file(asset) == original(asset)
    assert fingerprint.sha256_unchanged_file(asset) != before
    assert len(calls) == 2

    asset.write_bytes(b"third")
    os.utime(asset, ns=(old.st_atime_ns, old.st_mtime_ns + 1_000_000_000))
    assert fingerprint.sha256_unchanged_file(asset) == original(asset)
    assert len(calls) == 3
