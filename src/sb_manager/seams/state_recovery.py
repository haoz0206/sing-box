"""System boundary for inspecting and restoring manager-owned state files."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from sb_manager.domain.installation import ManagedInstallation


class StateFileCondition(str, Enum):
    """A storage-level classification that does not prescribe recovery policy."""

    MISSING = "missing"
    READABLE = "readable"
    CORRUPT = "corrupt"
    UNSUPPORTED_SCHEMA = "unsupported-schema"
    INACCESSIBLE = "inaccessible"


@dataclass(frozen=True, slots=True)
class StateFileSnapshot:
    """One exact state-file observation and its parsed value when trustworthy."""

    condition: StateFileCondition
    sha256: str | None = None
    installation: ManagedInstallation | None = None
    schema_version: int | None = None


@dataclass(frozen=True, slots=True)
class StateRecoverySnapshot:
    """Primary and backup observations captured for one recovery review."""

    primary: StateFileSnapshot
    backup: StateFileSnapshot


@dataclass(frozen=True, slots=True)
class StateRecoveryCommit:
    """Evidence returned after an exact backup has replaced a corrupt primary."""

    installation: ManagedInstallation
    corrupt_archive_path: Path


class StateRecoverySourceError(RuntimeError):
    """The storage boundary could not establish a trustworthy recovery result."""


class StateRecoveryPreconditionError(StateRecoverySourceError):
    """Primary or backup bytes no longer match the reviewed recovery plan."""


class StateRecoverySource(Protocol):
    """Hide state-file parsing and crash-safe replacement behind one boundary."""

    def inspect(self) -> StateRecoverySnapshot: ...

    def restore(
        self,
        *,
        expected_primary_sha256: str,
        expected_backup_sha256: str,
    ) -> StateRecoveryCommit: ...
