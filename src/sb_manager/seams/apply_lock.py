"""Public seam for serializing host apply operations."""

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol


class ApplyLockUnavailableError(RuntimeError):
    """Another manager process currently owns the apply lock."""

    def __init__(self, lock_path: Path) -> None:
        super().__init__(f"Apply lock is already held: {lock_path}")
        self.lock_path = lock_path


class ApplyLock(Protocol):
    """Provide an exclusive scope around revision check and host mutation."""

    def acquire(self) -> AbstractContextManager[None]: ...
