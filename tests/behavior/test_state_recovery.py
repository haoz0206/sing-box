from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from sb_manager.application.state_recovery import (
    RecoveryAvailability,
    RecoveryConfirmationRequiredError,
    StateRecoveryService,
)
from sb_manager.domain.installation import ManagedInstallation
from sb_manager.seams.state_recovery import (
    StateFileCondition,
    StateFileSnapshot,
    StateRecoveryCommit,
    StateRecoverySnapshot,
)

BACKUP_REVISION = 4
UNSUPPORTED_SCHEMA_VERSION = 2


class MutableRecoverySource:
    def __init__(self, snapshot: StateRecoverySnapshot) -> None:
        self.snapshot = snapshot
        self.restore_calls: list[tuple[str, str]] = []

    def inspect(self) -> StateRecoverySnapshot:
        return self.snapshot

    def restore(
        self, *, expected_primary_sha256: str, expected_backup_sha256: str
    ) -> StateRecoveryCommit:
        self.restore_calls.append((expected_primary_sha256, expected_backup_sha256))
        assert self.snapshot.backup.installation is not None
        return StateRecoveryCommit(
            installation=self.snapshot.backup.installation,
            corrupt_archive_path=Path("/state/state.json.corrupt-primary"),
        )


class TrackingApplyLock:
    def __init__(self) -> None:
        self.acquisitions = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self.acquisitions += 1
        yield


def test_recovery_inspection_exposes_a_reviewable_backup_without_mutation() -> None:
    backup = ManagedInstallation(schema_version=1, revision=BACKUP_REVISION, profiles=())
    source = MutableRecoverySource(
        StateRecoverySnapshot(
            primary=StateFileSnapshot(
                condition=StateFileCondition.CORRUPT,
                sha256="a" * 64,
            ),
            backup=StateFileSnapshot(
                condition=StateFileCondition.READABLE,
                sha256="b" * 64,
                installation=backup,
            ),
        )
    )
    service = StateRecoveryService(source=source, mutation_lock=TrackingApplyLock())

    report = service.inspect()

    assert report.availability is RecoveryAvailability.RECOVERY_AVAILABLE
    assert report.installation is None
    assert report.plan is not None
    assert report.plan.backup_revision == BACKUP_REVISION
    assert report.plan.backup_profile_count == 0
    assert report.plan.mutates_host is False
    assert source.restore_calls == []


def test_recovery_never_overwrites_a_state_from_a_newer_schema() -> None:
    source = MutableRecoverySource(
        StateRecoverySnapshot(
            primary=StateFileSnapshot(
                condition=StateFileCondition.UNSUPPORTED_SCHEMA,
                sha256="c" * 64,
                schema_version=UNSUPPORTED_SCHEMA_VERSION,
            ),
            backup=StateFileSnapshot(
                condition=StateFileCondition.READABLE,
                sha256="d" * 64,
                installation=ManagedInstallation.empty(),
            ),
        )
    )
    service = StateRecoveryService(source=source, mutation_lock=TrackingApplyLock())

    report = service.inspect()

    assert report.availability is RecoveryAvailability.UNSUPPORTED_SCHEMA
    assert report.plan is None
    assert report.found_schema_version == UNSUPPORTED_SCHEMA_VERSION


def test_recovery_requires_confirmation_and_commits_under_the_mutation_lock() -> None:
    backup = ManagedInstallation(schema_version=1, revision=5, profiles=())
    source = MutableRecoverySource(
        StateRecoverySnapshot(
            primary=StateFileSnapshot(
                condition=StateFileCondition.CORRUPT,
                sha256="e" * 64,
            ),
            backup=StateFileSnapshot(
                condition=StateFileCondition.READABLE,
                sha256="f" * 64,
                installation=backup,
            ),
        )
    )
    lock = TrackingApplyLock()
    service = StateRecoveryService(source=source, mutation_lock=lock)
    report = service.inspect()
    assert report.plan is not None

    with pytest.raises(RecoveryConfirmationRequiredError):
        service.recover(report.plan, confirmed=False)

    result = service.recover(report.plan, confirmed=True)

    assert result.installation == backup
    assert source.restore_calls == [("e" * 64, "f" * 64)]
    assert lock.acquisitions == 1
