"""Process-wide apply exclusion backed by a Linux flock."""

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sb_manager.seams.apply_lock import ApplyLockUnavailableError


class FileApplyLock:
    """Fail fast when another process is applying manager-owned state."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a+", encoding="utf-8") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ApplyLockUnavailableError(self._path) from error
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
