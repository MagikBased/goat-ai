"""Content hashes for reproducible trajectory inputs."""

import hashlib
from functools import lru_cache
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_signature(path: Path) -> tuple[int, int, int, int, int]:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns,
            stat.st_ctime_ns)


@lru_cache(maxsize=128)
def _hash_unchanged_file(path: Path, signature: tuple[int, int, int, int, int]) -> str:
    digest = sha256_file(path)
    if _file_signature(path) != signature:
        raise RuntimeError(f"file changed while hashing: {path}")
    return digest


def sha256_unchanged_file(path: str | Path) -> str:
    """Reuse an asset digest while its filesystem identity and timestamps hold.

    Only use this for pinned native assets. Trajectory/deck inputs retain direct
    content hashing; the native manifest checks metadata again each duel.
    """
    source = Path(path).resolve(strict=True)
    return _hash_unchanged_file(source, _file_signature(source))
