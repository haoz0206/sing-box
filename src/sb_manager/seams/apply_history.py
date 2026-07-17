"""System seam for bounded durable configuration-apply evidence."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

SHA256_HEX_LENGTH = 64
MAX_APPLY_HISTORY_DIAGNOSTICS = 4096


class ApplyHistoryStatus(str, Enum):
    """Durable state of one configuration-apply attempt."""

    IN_PROGRESS = "in-progress"
    APPLIED = "applied"
    VALIDATION_FAILED = "validation-failed"
    PRECONDITION_FAILED = "precondition-failed"
    COMMIT_FAILED = "commit-failed"
    ROLLED_BACK = "rolled-back"
    ROLLBACK_FAILED = "rollback-failed"
    EXECUTION_ERROR = "execution-error"


@dataclass(frozen=True, slots=True)
class ApplyHistoryEntry:
    """Secret-free evidence retained for one exact candidate fingerprint."""

    attempt_id: str
    started_at: datetime
    completed_at: datetime | None
    status: ApplyHistoryStatus
    candidate_sha256: str
    active_profile_count: int
    diagnostics: str
    redacted_occurrences: int = 0

    def __post_init__(self) -> None:
        if not self.attempt_id:
            raise ValueError("Apply history attempt ID must not be empty")
        if self.started_at.utcoffset() is None:
            raise ValueError("Apply history start time must be timezone-aware")
        if self.status is ApplyHistoryStatus.IN_PROGRESS:
            if self.completed_at is not None:
                raise ValueError("In-progress apply history must not have a completion time")
        elif self.completed_at is None:
            raise ValueError("Completed apply history requires a completion time")
        elif self.completed_at.utcoffset() is None:
            raise ValueError("Apply history completion time must be timezone-aware")
        elif self.completed_at < self.started_at:
            raise ValueError("Apply history completion cannot precede its start")
        if len(self.candidate_sha256) != SHA256_HEX_LENGTH or any(
            character not in "0123456789abcdef" for character in self.candidate_sha256
        ):
            raise ValueError("Apply history candidate SHA-256 must be lowercase hexadecimal")
        if self.active_profile_count < 0:
            raise ValueError("Apply history active profile count must not be negative")
        if self.redacted_occurrences < 0:
            raise ValueError("Apply history redaction count must not be negative")
        if len(self.diagnostics) > MAX_APPLY_HISTORY_DIAGNOSTICS:
            raise ValueError(
                f"Apply history diagnostics exceed {MAX_APPLY_HISTORY_DIAGNOSTICS} characters"
            )


class ApplyHistoryStoreError(RuntimeError):
    """Durable apply history could not be read or updated safely."""


class ApplyHistoryStore(Protocol):
    """Persist starts before host mutation and complete exact attempts afterward."""

    def begin(self, entry: ApplyHistoryEntry) -> None: ...

    def complete(self, entry: ApplyHistoryEntry) -> None: ...

    def recent(self, *, limit: int) -> tuple[ApplyHistoryEntry, ...]: ...
