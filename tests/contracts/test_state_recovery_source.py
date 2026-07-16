from hashlib import sha256
from pathlib import Path

import pytest

from sb_manager.adapters.json_file_state import JsonFileStateStore
from sb_manager.adapters.json_state_recovery import JsonStateRecoverySource
from sb_manager.domain.installation import ManagedInstallation
from sb_manager.seams.state_recovery import (
    StateFileCondition,
    StateRecoveryPreconditionError,
    StateRecoverySourceError,
)

UNSUPPORTED_SCHEMA_VERSION = 2


def test_json_recovery_source_restores_exact_backup_and_preserves_corrupt_bytes(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    store = JsonFileStateStore(state_path)
    backup = ManagedInstallation(schema_version=1, revision=1, profiles=())
    current = ManagedInstallation(schema_version=1, revision=2, profiles=())
    store.save(backup)
    store.save(current)
    corrupt_bytes = b'{"schema_version": 1, definitely-not-json'
    state_path.write_bytes(corrupt_bytes)
    source = JsonStateRecoverySource(state_path)

    snapshot = source.inspect()

    assert snapshot.primary.condition is StateFileCondition.CORRUPT
    assert snapshot.primary.sha256 == sha256(corrupt_bytes).hexdigest()
    assert snapshot.backup.condition is StateFileCondition.READABLE
    assert snapshot.backup.installation == backup
    assert snapshot.backup.sha256 is not None

    result = source.restore(
        expected_primary_sha256=snapshot.primary.sha256,
        expected_backup_sha256=snapshot.backup.sha256,
    )

    assert store.load() == backup
    assert JsonFileStateStore(store.backup_path).load() == backup
    assert result.installation == backup
    assert result.corrupt_archive_path.read_bytes() == corrupt_bytes


def test_json_recovery_source_rejects_files_changed_after_review(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    store = JsonFileStateStore(state_path)
    store.save(ManagedInstallation(schema_version=1, revision=1, profiles=()))
    store.save(ManagedInstallation(schema_version=1, revision=2, profiles=()))
    state_path.write_text("not-json", encoding="utf-8")
    source = JsonStateRecoverySource(state_path)
    snapshot = source.inspect()
    assert snapshot.primary.sha256 is not None
    assert snapshot.backup.sha256 is not None
    state_path.write_text("changed-after-review", encoding="utf-8")

    with pytest.raises(StateRecoveryPreconditionError):
        source.restore(
            expected_primary_sha256=snapshot.primary.sha256,
            expected_backup_sha256=snapshot.backup.sha256,
        )


def test_json_recovery_source_distinguishes_unsupported_schema_from_corruption(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        f'{{"schema_version": {UNSUPPORTED_SCHEMA_VERSION}, "revision": 7, "profiles": []}}',
        encoding="utf-8",
    )

    snapshot = JsonStateRecoverySource(state_path).inspect()

    assert snapshot.primary.condition is StateFileCondition.UNSUPPORTED_SCHEMA
    assert snapshot.primary.schema_version == UNSUPPORTED_SCHEMA_VERSION


def test_json_recovery_source_types_an_unconfirmed_durability_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / "state.json"
    store = JsonFileStateStore(state_path)
    store.save(ManagedInstallation(schema_version=1, revision=1, profiles=()))
    store.save(ManagedInstallation(schema_version=1, revision=2, profiles=()))
    state_path.write_text("corrupt", encoding="utf-8")
    source = JsonStateRecoverySource(state_path)
    snapshot = source.inspect()
    assert snapshot.primary.sha256 is not None
    assert snapshot.backup.sha256 is not None

    def fail_sync(_: int) -> None:
        raise OSError("simulated storage failure")

    monkeypatch.setattr("sb_manager.adapters.json_state_recovery.os.fsync", fail_sync)

    with pytest.raises(StateRecoverySourceError, match="durable result"):
        source.restore(
            expected_primary_sha256=snapshot.primary.sha256,
            expected_backup_sha256=snapshot.backup.sha256,
        )
