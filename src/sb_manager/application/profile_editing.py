"""Plan revision-bound edits to operator-facing profile metadata."""

from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol

from sb_manager.application.configuration_projection import ManagedConfigurationProjector
from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.domain.installation import ManagedInstallation, ProfileStatus
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


class ProfileEditNotFoundError(LookupError):
    """The selected stable profile identifier is no longer in desired state."""


class ProfileEditValidationError(ValueError):
    """One editable profile field cannot produce valid desired state."""

    def __init__(self, *, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class ProfileEditNoChangesError(ValueError):
    """Normalized editable fields match the current desired state."""


class ProfileEditConfirmationRequiredError(PermissionError):
    """Editing a profile always requires an explicit second action."""


class ProfileEditPlanChangedError(RuntimeError):
    """Desired-state content no longer matches the operator-reviewed plan."""


class ProfileEditScope(str, Enum):
    """Whether a confirmed edit must also replace the live configuration."""

    DESIRED_STATE_ONLY = "desired-state-only"
    LIVE_CONFIGURATION = "live-configuration"


@dataclass(frozen=True, slots=True)
class PlanProfileEditRequest:
    """Operator-entered mutable profile metadata before normalization."""

    profile_id: str
    profile_name: str
    server_address: str | None


@dataclass(frozen=True, slots=True)
class ProfileEditPlan:
    """Read-only impact preview for editing one exact desired-state revision."""

    profile_id: str
    previous_profile_name: str
    profile_name: str
    previous_server_address: str | None
    server_address: str | None
    status: ProfileStatus
    expected_revision: int
    scope: ProfileEditScope
    changed_fields: tuple[str, ...]
    mutates_host: bool = False


@dataclass(frozen=True, slots=True)
class ProfileEditResult:
    """Desired-state revision and optional host transaction after editing."""

    scope: ProfileEditScope
    committed_revision: int | None
    transaction: ApplyTransactionResult | None


class ProfileEditor(Protocol):
    """Public application seam consumed by the profile-editing TUI workflow."""

    def plan_edit(self, request: PlanProfileEditRequest) -> ProfileEditPlan: ...

    def apply_edit(
        self,
        plan: ProfileEditPlan,
        *,
        confirmed: bool,
    ) -> ProfileEditResult: ...


class ProfileEditingService:
    """Own profile-edit planning and its desired/live-state invariants."""

    def __init__(
        self,
        *,
        state_store: StateStore,
        protocol_catalog: ProtocolCatalog,
        applier: ConfigurationApplier,
        apply_lock: ApplyLock,
    ) -> None:
        self._state_store = state_store
        self._configuration_projector = ManagedConfigurationProjector(
            protocol_catalog=protocol_catalog
        )
        self._applier = applier
        self._apply_lock = apply_lock

    def plan_edit(self, request: PlanProfileEditRequest) -> ProfileEditPlan:
        installation = self._state_store.load()
        try:
            profile = next(
                profile
                for profile in installation.profiles
                if profile.profile_id == request.profile_id
            )
        except StopIteration as error:
            raise ProfileEditNotFoundError(request.profile_id) from error

        profile_name = request.profile_name.strip()
        if not profile_name:
            raise ProfileEditValidationError(
                field="profile_name",
                message="请输入配置名称",
            )
        server_address = (request.server_address or "").strip() or None
        changed_fields = tuple(
            field
            for field, changed in (
                ("profile_name", profile_name != profile.profile_name),
                ("server_address", server_address != profile.server_address),
            )
            if changed
        )
        if not changed_fields:
            raise ProfileEditNoChangesError("No profile fields changed")
        return ProfileEditPlan(
            profile_id=profile.profile_id,
            previous_profile_name=profile.profile_name,
            profile_name=profile_name,
            previous_server_address=profile.server_address,
            server_address=server_address,
            status=profile.status,
            expected_revision=installation.revision,
            scope=(
                ProfileEditScope.LIVE_CONFIGURATION
                if profile.status is ProfileStatus.APPLIED and "profile_name" in changed_fields
                else ProfileEditScope.DESIRED_STATE_ONLY
            ),
            changed_fields=changed_fields,
        )

    def apply_edit(
        self,
        plan: ProfileEditPlan,
        *,
        confirmed: bool,
    ) -> ProfileEditResult:
        if not confirmed:
            raise ProfileEditConfirmationRequiredError(
                "Profile editing requires explicit confirmation"
            )
        with self._apply_lock.acquire():
            installation = self._state_store.load()
            if installation.revision != plan.expected_revision:
                raise StateRevisionConflictError(
                    expected=plan.expected_revision,
                    actual=installation.revision,
                )
            current_plan = self.plan_edit(
                PlanProfileEditRequest(
                    profile_id=plan.profile_id,
                    profile_name=plan.profile_name,
                    server_address=plan.server_address,
                )
            )
            if current_plan != plan:
                raise ProfileEditPlanChangedError(
                    "Profile edit plan no longer matches desired state"
                )

            profiles = tuple(
                replace(
                    profile,
                    profile_name=plan.profile_name,
                    server_address=plan.server_address,
                )
                if profile.profile_id == plan.profile_id
                else profile
                for profile in installation.profiles
            )
            transaction: ApplyTransactionResult | None = None
            expected_config_sha256 = installation.expected_config_sha256
            if plan.scope is ProfileEditScope.LIVE_CONFIGURATION:
                document = self._configuration_projector.project(profiles)
                precondition = (
                    ConfigTargetPrecondition.matching_sha256(installation.expected_config_sha256)
                    if installation.expected_config_sha256 is not None
                    else ConfigTargetPrecondition.absent()
                )
                transaction = self._applier.apply(document, precondition=precondition)
                if transaction.outcome is not ApplyOutcome.APPLIED:
                    return ProfileEditResult(
                        scope=plan.scope,
                        committed_revision=None,
                        transaction=transaction,
                    )
                expected_config_sha256 = configuration_sha256(document)
            committed_revision = installation.revision + 1
            self._state_store.save(
                ManagedInstallation(
                    schema_version=installation.schema_version,
                    revision=committed_revision,
                    profiles=profiles,
                    expected_config_sha256=expected_config_sha256,
                )
            )
            return ProfileEditResult(
                scope=plan.scope,
                committed_revision=committed_revision,
                transaction=transaction,
            )
