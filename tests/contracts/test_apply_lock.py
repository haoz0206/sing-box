from pathlib import Path

import pytest

from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.seams.apply_lock import ApplyLockUnavailableError


def test_file_apply_lock_excludes_a_second_manager(tmp_path: Path) -> None:
    lock_path = tmp_path / "state/apply.lock"
    first = FileApplyLock(lock_path)
    second = FileApplyLock(lock_path)

    with (
        first.acquire(),
        pytest.raises(ApplyLockUnavailableError) as caught,
        second.acquire(),
    ):
        raise AssertionError("the second manager must not enter the lock")

    assert caught.value.lock_path == lock_path
    with second.acquire():
        assert lock_path.exists()
