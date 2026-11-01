"""Advisory local-filesystem locks and atomic replacement; no external dependencies."""

import errno
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(path: Path, timeout: float = 10):
    """Hold an OS lock; the persistent sidecar is safe to leave after a crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"lock file must not be a symlink: {path}")
    with path.open("a+b") as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise ValueError(f"timed out waiting for locked file: {path}") from exc
                time.sleep(0.025)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_write(path: Path, content: bytes) -> None:
    """Publish complete bytes or retain the prior file if replacement fails."""
    if path.is_symlink():
        raise ValueError(f"destination must not be a symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            temp.chmod(path.stat().st_mode & 0o777)
        deadline = time.monotonic() + 2
        while True:
            try:
                os.replace(temp, path)
                break
            except PermissionError as exc:
                # Windows readers/scanners may briefly deny delete sharing.
                if getattr(exc, "winerror", None) not in (32, 33) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.025)
    finally:
        temp.unlink(missing_ok=True)


def strict_json(text: str):
    """Reject duplicate keys and nonstandard NaN/Infinity constants."""

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"invalid JSON constant: {value}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
