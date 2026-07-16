"""Review and explicitly confirm recovery of manager-owned desired state."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sb_manager.domain.installation import ManagedInstallation
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.state_recovery import (
    StateFileCondition,
    StateRecoveryCommit,
    StateRecoverySource,
)


class RecoveryAvailability(str, Enum):
    """Operator-facing startup classification for desired-state access."""

    HEALTHY = "healthy"
    RECOVERY_AVAILABLE = "recovery-available"
    RECOVERY_UNAVAILABLE = "recovery-unavailable"
    UNSUPPORTED_SCHEMA = "unsupported-schema"


class StateRecoveryError(RuntimeError):
    """Base error for a rejected desired-state recovery workflow."""


class RecoveryConfirmationRequiredError(StateRecoveryError):
    """Recovery requires a second explicit operator action."""


@dataclass(frozen=True, slots=True)
class StateRecoveryPlan:
    """Exact, reviewable backup recovery intent with no host mutation."""

    primary_sha256: str
    backup_sha256: str
    backup_revision: int
    backup_profile_count: int
    mutates_host: bool = False


@dataclass(frozen=True, slots=True)
class StateRecoveryReport:
    """Safe startup state, optionally carrying a reviewable recovery plan."""

    availability: RecoveryAvailability
    installation: ManagedInstallation | None = None
    plan: StateRecoveryPlan | None = None
    found_schema_version: int | None = None


class StateRecoveryManager(Protocol):
    """TUI-facing interface for startup inspection and confirmed recovery."""

    def inspect(self) -> StateRecoveryReport: ...

    def recover(
        self,
        plan: StateRecoveryPlan,
        *,
        confirmed: bool,
    ) -> StateRecoveryCommit: ...


class StateRecoveryService:
    """Permit restoration only for corrupt primary bytes and a readable backup."""

    def __init__(self, *, source: StateRecoverySource, mutation_lock: ApplyLock) -> None:
        self._source = source
        self._mutation_lock = mutation_lock

    def inspect(self) -> StateRecoveryReport:
        snapshot = self._source.inspect()
        primary = snapshot.primary
        if primary.condition is StateFileCondition.READABLE:
            return StateRecoveryReport(
                availability=RecoveryAvailability.HEALTHY,
                installation=primary.installation,
            )
        if primary.condition is StateFileCondition.MISSING:
            return StateRecoveryReport(
                availability=RecoveryAvailability.HEALTHY,
                installation=ManagedInstallation.empty(),
            )
        if primary.condition is StateFileCondition.UNSUPPORTED_SCHEMA:
            return StateRecoveryReport(
                availability=RecoveryAvailability.UNSUPPORTED_SCHEMA,
                found_schema_version=primary.schema_version,
            )

        backup = snapshot.backup
        if (
            primary.condition is StateFileCondition.CORRUPT
            and primary.sha256 is not None
            and backup.condition is StateFileCondition.READABLE
            and backup.sha256 is not None
            and backup.installation is not None
        ):
            return StateRecoveryReport(
                availability=RecoveryAvailability.RECOVERY_AVAILABLE,
                plan=StateRecoveryPlan(
                    primary_sha256=primary.sha256,
                    backup_sha256=backup.sha256,
                    backup_revision=backup.installation.revision,
                    backup_profile_count=len(backup.installation.profiles),
                ),
            )
        return StateRecoveryReport(availability=RecoveryAvailability.RECOVERY_UNAVAILABLE)

    def recover(
        self,
        plan: StateRecoveryPlan,
        *,
        confirmed: bool,
    ) -> StateRecoveryCommit:
        if not confirmed:
            raise RecoveryConfirmationRequiredError("Desired-state recovery was not confirmed")
        with self._mutation_lock.acquire():
            return self._source.restore(
                expected_primary_sha256=plan.primary_sha256,
                expected_backup_sha256=plan.backup_sha256,
            )
