"""Plan and execute safe removal of one managed proxy profile."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sb_manager.application.configuration_projection import ManagedConfigurationProjector
from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.protocol_compatibility import ActiveCoreProtocolCompatibility
from sb_manager.domain.installation import ManagedInstallation, ProfileStatus, ProtocolKind
from sb_manager.protocols.catalog import ProtocolCatalog
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.configuration_applier import ConfigurationApplier
from sb_manager.seams.state_store import StateStore
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    ConfigTargetPrecondition,
)
from sb_manager.transactions.staging import configuration_sha256


class ProfileRemovalNotFoundError(LookupError):
    """The selected stable profile identifier is no longer in desired state."""


class ProfileRemovalConfirmationRequiredError(PermissionError):
    """Removing a profile always requires an explicit second action."""


class ProfileRemovalScope(str, Enum):
    """Whether confirmed removal must also replace the live configuration."""

    DESIRED_STATE_ONLY = "desired-state-only"
    LIVE_CONFIGURATION = "live-configuration"


@dataclass(frozen=True, slots=True)
class ProfileRemovalPlan:
    """Read-only impact preview for removing one exact desired-state revision."""

    profile_id: str
    profile_name: str
    protocol: ProtocolKind
    status: ProfileStatus
    expected_revision: int
    scope: ProfileRemovalScope
    remaining_profile_count: int
    remaining_applied_count: int
    mutates_host: bool = False
    observed_core_version: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileRemovalResult:
    """Desired-state revision and optional host transaction after removal."""

    scope: ProfileRemovalScope
    committed_revision: int | None
    remaining_profile_count: int
    transaction: ApplyTransactionResult | None


class ProfileRemover(Protocol):
    """Public application seam consumed by the profile-removal TUI workflow."""

    def plan_removal(self, profile_id: str) -> ProfileRemovalPlan: ...

    def remove_profile(
        self,
        plan: ProfileRemovalPlan,
        *,
        confirmed: bool,
    ) -> ProfileRemovalResult: ...


class ProfileRemovalService:
    """Own profile-removal planning and its desired/live-state invariants."""

    def __init__(
        self,
        *,
        state_store: StateStore,
        protocol_catalog: ProtocolCatalog,
        applier: ConfigurationApplier,
        apply_lock: ApplyLock,
        core_compatibility: ActiveCoreProtocolCompatibility | None = None,
    ) -> None:
        self._state_store = state_store
        self._configuration_projector = ManagedConfigurationProjector(
            protocol_catalog=protocol_catalog
        )
        self._applier = applier
        self._apply_lock = apply_lock
        self._core_compatibility = core_compatibility or ActiveCoreProtocolCompatibility()

    def plan_removal(self, profile_id: str) -> ProfileRemovalPlan:
        """Describe profile removal without acquiring the mutation lock or applying."""
        return self._plan_removal(profile_id)

    def _plan_removal(
        self,
        profile_id: str,
        *,
        expected_core_version: str | None = None,
    ) -> ProfileRemovalPlan:
        installation = self._state_store.load()
        try:
            profile = next(
                profile for profile in installation.profiles if profile.profile_id == profile_id
            )
        except StopIteration as error:
            raise ProfileRemovalNotFoundError(profile_id) from error
        remaining = tuple(
            existing for existing in installation.profiles if existing.profile_id != profile_id
        )
        observed_core_version = self._core_compatibility.require_profiles(
            remaining,
            expected_version=expected_core_version,
        )
        return ProfileRemovalPlan(
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            protocol=profile.protocol,
            status=profile.status,
            expected_revision=installation.revision,
            scope=(
                ProfileRemovalScope.LIVE_CONFIGURATION
                if profile.status is ProfileStatus.APPLIED and profile.enabled
                else ProfileRemovalScope.DESIRED_STATE_ONLY
            ),
            remaining_profile_count=len(remaining),
            remaining_applied_count=sum(
                profile.status is ProfileStatus.APPLIED for profile in remaining
            ),
            observed_core_version=observed_core_version,
        )

    def remove_profile(
        self,
        plan: ProfileRemovalPlan,
        *,
        confirmed: bool,
    ) -> ProfileRemovalResult:
        if not confirmed:
            raise ProfileRemovalConfirmationRequiredError(
                "Profile removal requires explicit confirmation"
            )
        with self._apply_lock.acquire():
            current_plan = self._plan_removal(
                plan.profile_id,
                expected_core_version=plan.observed_core_version,
            )
            if current_plan.expected_revision != plan.expected_revision:
                raise StateRevisionConflictError(
                    expected=plan.expected_revision,
                    actual=current_plan.expected_revision,
                )
            if current_plan != plan:
                raise RuntimeError("Profile removal plan no longer matches desired state")
            installation = self._state_store.load()
            remaining = tuple(
                profile
                for profile in installation.profiles
                if profile.profile_id != plan.profile_id
            )
            transaction: ApplyTransactionResult | None = None
            expected_config_sha256 = installation.expected_config_sha256
            if plan.scope is ProfileRemovalScope.LIVE_CONFIGURATION:
                document = self._configuration_projector.project(remaining)
                precondition = (
                    ConfigTargetPrecondition.matching_sha256(installation.expected_config_sha256)
                    if installation.expected_config_sha256 is not None
                    else ConfigTargetPrecondition.absent()
                )
                transaction = self._applier.apply(document, precondition=precondition)
                if transaction.outcome is not ApplyOutcome.APPLIED:
                    return ProfileRemovalResult(
                        scope=plan.scope,
                        committed_revision=None,
                        remaining_profile_count=len(remaining),
                        transaction=transaction,
                    )
                expected_config_sha256 = configuration_sha256(document)
            committed_revision = installation.revision + 1
            self._state_store.save(
                ManagedInstallation(
                    schema_version=installation.schema_version,
                    revision=committed_revision,
                    profiles=remaining,
                    expected_config_sha256=expected_config_sha256,
                )
            )
            return ProfileRemovalResult(
                scope=plan.scope,
                committed_revision=committed_revision,
                remaining_profile_count=len(remaining),
                transaction=transaction,
            )
