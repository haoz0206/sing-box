from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sb_manager.adapters.json_apply_history import JsonApplyHistoryStore
from sb_manager.seams.apply_history import (
    ApplyHistoryEntry,
    ApplyHistoryStatus,
    ApplyHistoryStoreError,
)

PRIVATE_FILE_MODE = 0o600


def test_json_history_round_trips_completed_attempt_across_process_instances(
    tmp_path: Path,
) -> None:
    history_path = tmp_path / "apply-history.json"
    started_at = datetime(2026, 7, 17, 8, 30, tzinfo=timezone.utc)
    started = ApplyHistoryEntry(
        attempt_id="attempt-001",
        started_at=started_at,
        completed_at=None,
        status=ApplyHistoryStatus.IN_PROGRESS,
        candidate_sha256="a" * 64,
        active_profile_count=2,
        diagnostics="配置应用已开始，最终结果尚未写入。",
    )
    completed = ApplyHistoryEntry(
        attempt_id=started.attempt_id,
        started_at=started.started_at,
        completed_at=started_at + timedelta(seconds=3),
        status=ApplyHistoryStatus.APPLIED,
        candidate_sha256=started.candidate_sha256,
        active_profile_count=started.active_profile_count,
        diagnostics="configuration valid; service active",
    )

    writer = JsonApplyHistoryStore(path=history_path)
    writer.begin(started)
    writer.complete(completed)
    observed = JsonApplyHistoryStore(path=history_path).recent(limit=20)

    assert observed == (completed,)
    assert history_path.stat().st_mode & 0o777 == PRIVATE_FILE_MODE
    assert "inbounds" not in history_path.read_text(encoding="utf-8")


def test_corrupt_history_is_not_silently_overwritten_before_an_apply(
    tmp_path: Path,
) -> None:
    history_path = tmp_path / "apply-history.json"
    corrupt_content = '{"schema_version":1,"entries":['
    history_path.write_text(corrupt_content, encoding="utf-8")
    entry = ApplyHistoryEntry(
        attempt_id="attempt-001",
        started_at=datetime(2026, 7, 17, 8, 30, tzinfo=timezone.utc),
        completed_at=None,
        status=ApplyHistoryStatus.IN_PROGRESS,
        candidate_sha256="a" * 64,
        active_profile_count=1,
        diagnostics="配置应用已开始，最终结果尚未写入。",
    )

    with pytest.raises(ApplyHistoryStoreError, match="not valid JSON"):
        JsonApplyHistoryStore(path=history_path).begin(entry)

    assert history_path.read_text(encoding="utf-8") == corrupt_content


def test_json_history_retention_is_bounded_and_newest_first(tmp_path: Path) -> None:
    history_path = tmp_path / "apply-history.json"
    store = JsonApplyHistoryStore(path=history_path, max_entries=2)
    base_time = datetime(2026, 7, 17, 8, 30, tzinfo=timezone.utc)

    for index in range(3):
        started = ApplyHistoryEntry(
            attempt_id=f"attempt-{index}",
            started_at=base_time + timedelta(minutes=index),
            completed_at=None,
            status=ApplyHistoryStatus.IN_PROGRESS,
            candidate_sha256=str(index) * 64,
            active_profile_count=index,
            diagnostics="配置应用已开始，最终结果尚未写入。",
        )
        store.begin(started)
        store.complete(
            ApplyHistoryEntry(
                attempt_id=started.attempt_id,
                started_at=started.started_at,
                completed_at=started.started_at + timedelta(seconds=1),
                status=ApplyHistoryStatus.APPLIED,
                candidate_sha256=started.candidate_sha256,
                active_profile_count=started.active_profile_count,
                diagnostics="configuration valid; service active",
            )
        )

    observed = JsonApplyHistoryStore(path=history_path, max_entries=2).recent(limit=20)

    assert tuple(entry.attempt_id for entry in observed) == ("attempt-2", "attempt-1")


def test_json_history_refuses_a_symbolic_link_without_touching_its_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "operator-file.json"
    target.write_text("operator-owned", encoding="utf-8")
    history_path = tmp_path / "apply-history.json"
    history_path.symlink_to(target)
    entry = ApplyHistoryEntry(
        attempt_id="attempt-001",
        started_at=datetime(2026, 7, 17, 8, 30, tzinfo=timezone.utc),
        completed_at=None,
        status=ApplyHistoryStatus.IN_PROGRESS,
        candidate_sha256="a" * 64,
        active_profile_count=1,
        diagnostics="配置应用已开始，最终结果尚未写入。",
    )

    with pytest.raises(ApplyHistoryStoreError, match="symbolic link"):
        JsonApplyHistoryStore(path=history_path).begin(entry)

    assert target.read_text(encoding="utf-8") == "operator-owned"
