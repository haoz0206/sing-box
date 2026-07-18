"""Plan and transactionally change whether an applied profile is live."""

from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol

from sb_manager.application.configuration_projection import ManagedConfigurationProjector
from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.protocol_compatibility import (
    ActiveCoreProtocolCompatibility,
    CoreVersionUnknown,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.protocols.catalog import ProtocolCatalog
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.configuration_applier import ConfigurationApplier
from sb_manager.seams.port_source import PortSource
from sb_manager.seams.state_store import StateStore
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    ConfigTargetPrecondition,
)
from sb_manager.transactions.staging import configuration_sha256


class ProfileAvailability(str, Enum):
    """Operator-facing availability of one previously applied profile."""

    ACTIVE = "active"
    PAUSED = "paused"


class ProfileAvailabilityNoChangeError(ValueError):
    """The requested profile already has the target availability."""


class ProfileAvailabilityDraftError(ValueError):
    """Draft profiles use the existing apply workflow, not pause/resume."""


class ProfileAvailabilityNotFoundError(LookupError):
    """The selected stable profile identifier no longer exists."""


class ProfileAvailabilityPlanChangedError(RuntimeError):
    """The confirmed profile no longer matches the reviewed transition plan."""


class ProfileAvailabilityConfirmationRequiredError(PermissionError):
    """Pause and resume require explicit confirmation of the reviewed plan."""


class ProfileResumePortUnavailableError(RuntimeError):
    """A paused fixed-port profile cannot safely resume on its recorded port."""

    def __init__(self, port: int | None) -> None:
        self.port = port
        super().__init__(f"Port {port} is unavailable for profile resume")


@dataclass(frozen=True, slots=True)
class PlanProfileAvailabilityRequest:
    """One requested availability transition before confirmation."""

    profile_id: str
    target: ProfileAvailability


@dataclass(frozen=True, slots=True)
class ProfileAvailabilityPlan:
    """Revision-bound preview of one profile availability transition."""

    profile_id: str
    profile_name: str
    current: ProfileAvailability
    target: ProfileAvailability
    expected_revision: int
    remaining_active_profile_count: int
    port_selection: PortSelection
    recorded_listen_port: int | None
    port_may_change: bool
    requires_live_apply: bool
    observed_core_version: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileAvailabilityResult:
    """Transaction evidence and committed availability, when successful."""

    availability: ProfileAvailability
    listen_port: int | None
    transaction: ApplyTransactionResult
    committed_revision: int | None


class ProfileAvailabilityManager(Protocol):
    """Public application seam consumed by the availability TUI workflow."""

    def plan_change(
        self,
        request: PlanProfileAvailabilityRequest,
    ) -> ProfileAvailabilityPlan: ...

    def apply_change(
        self,
        plan: ProfileAvailabilityPlan,
        *,
        confirmed: bool,
    ) -> ProfileAvailabilityResult: ...


class ProfileAvailabilityService:
    """Own revision-bound pause/resume semantics behind one small interface."""

    def __init__(  # noqa: PLR0913 - explicit mutation boundary dependencies
        self,
        *,
        state_store: StateStore,
        protocol_catalog: ProtocolCatalog,
        port_source: PortSource,
        applier: ConfigurationApplier,
        apply_lock: ApplyLock,
        core_compatibility: ActiveCoreProtocolCompatibility | None = None,
    ) -> None:
        self._state_store = state_store
        self._configuration_projector = ManagedConfigurationProjector(
            protocol_catalog=protocol_catalog
        )
        self._port_source = port_source
        self._applier = applier
        self._apply_lock = apply_lock
        self._core_compatibility = core_compatibility or ActiveCoreProtocolCompatibility()

    def plan_change(
        self,
        request: PlanProfileAvailabilityRequest,
    ) -> ProfileAvailabilityPlan:
        installation = self._state_store.load()
        try:
            profile = next(
                profile
                for profile in installation.profiles
                if profile.profile_id == request.profile_id
            )
        except StopIteration as error:
            raise ProfileAvailabilityNotFoundError(request.profile_id) from error
        if profile.status is ProfileStatus.DRAFT:
            raise ProfileAvailabilityDraftError(
                f"Profile {profile.profile_id} is a draft; apply the draft instead"
            )
        current = ProfileAvailability.ACTIVE if profile.enabled else ProfileAvailability.PAUSED
        if current is request.target:
            raise ProfileAvailabilityNoChangeError(
                f"Profile {profile.profile_id} is already {request.target.value}"
            )
        compatibility_profiles = tuple(
            replace(
                existing,
                enabled=request.target is ProfileAvailability.ACTIVE,
            )
            if existing.profile_id == profile.profile_id
            else existing
            for existing in installation.profiles
        )
        observed_core_version = self._core_compatibility.require_profiles(compatibility_profiles)
        if (
            request.target is ProfileAvailability.ACTIVE
            and profile.port_selection is PortSelection.FIXED
            and (
                profile.listen_port is None
                or not self._port_source.is_available(profile.listen_port)
            )
        ):
            raise ProfileResumePortUnavailableError(profile.listen_port)
        active_count = sum(
            existing.status is ProfileStatus.APPLIED and existing.enabled
            for existing in installation.profiles
        )
        return ProfileAvailabilityPlan(
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            current=current,
            target=request.target,
            expected_revision=installation.revision,
            remaining_active_profile_count=(
                active_count - 1
                if request.target is ProfileAvailability.PAUSED
                else active_count + 1
            ),
            port_selection=profile.port_selection,
            recorded_listen_port=profile.listen_port,
            port_may_change=(
                request.target is ProfileAvailability.ACTIVE
                and profile.port_selection is PortSelection.AUTOMATIC
            ),
            requires_live_apply=True,
            observed_core_version=observed_core_version,
        )

    def apply_change(
        self,
        plan: ProfileAvailabilityPlan,
        *,
        confirmed: bool,
    ) -> ProfileAvailabilityResult:
        if not confirmed:
            raise ProfileAvailabilityConfirmationRequiredError(
                "Profile availability change requires explicit confirmation"
            )
        with self._apply_lock.acquire():
            installation = self._state_store.load()
            if installation.revision != plan.expected_revision:
                raise StateRevisionConflictError(
                    expected=plan.expected_revision,
                    actual=installation.revision,
                )
            try:
                current_profile = next(
                    profile
                    for profile in installation.profiles
                    if profile.profile_id == plan.profile_id
                )
            except StopIteration as error:
                raise ProfileAvailabilityNotFoundError(plan.profile_id) from error
            current_availability = (
                ProfileAvailability.ACTIVE
                if current_profile.enabled
                else ProfileAvailability.PAUSED
            )
            if (
                current_profile.status is not ProfileStatus.APPLIED
                or current_availability is not plan.current
                or current_profile.profile_name != plan.profile_name
                or current_profile.port_selection is not plan.port_selection
                or current_profile.listen_port != plan.recorded_listen_port
            ):
                raise ProfileAvailabilityPlanChangedError(
                    "Profile availability plan no longer matches desired state"
                )
            compatibility_profiles = tuple(
                replace(
                    profile,
                    enabled=plan.target is ProfileAvailability.ACTIVE,
                )
                if profile.profile_id == plan.profile_id
                else profile
                for profile in installation.profiles
            )
            current_core_version = self._core_compatibility.require_profiles(
                compatibility_profiles,
                expected_version=plan.observed_core_version,
            )
            if current_core_version is not None and plan.observed_core_version is None:
                raise CoreVersionUnknown(protocol=ProtocolKind.SNELL_V6)
            if (
                plan.target is ProfileAvailability.ACTIVE
                and current_profile.port_selection is PortSelection.FIXED
                and (
                    current_profile.listen_port is None
                    or not self._port_source.is_available(current_profile.listen_port)
                )
            ):
                raise ProfileResumePortUnavailableError(current_profile.listen_port)
            listen_port = current_profile.listen_port
            if (
                plan.target is ProfileAvailability.ACTIVE
                and current_profile.port_selection is PortSelection.AUTOMATIC
                and (listen_port is None or not self._port_source.is_available(listen_port))
            ):
                reserved_ports = frozenset(
                    profile.listen_port
                    for profile in installation.profiles
                    if profile.profile_id != plan.profile_id and profile.listen_port is not None
                )
                listen_port = self._port_source.choose_available(excluded_ports=reserved_ports)
            profiles = tuple(
                replace(
                    profile,
                    enabled=plan.target is ProfileAvailability.ACTIVE,
                    listen_port=listen_port,
                )
                if profile.profile_id == plan.profile_id
                else profile
                for profile in installation.profiles
            )
            document = self._configuration_projector.project(profiles)
            precondition = (
                ConfigTargetPrecondition.matching_sha256(installation.expected_config_sha256)
                if installation.expected_config_sha256 is not None
                else ConfigTargetPrecondition.absent()
            )
            transaction = self._applier.apply(document, precondition=precondition)
            profile = next(profile for profile in profiles if profile.profile_id == plan.profile_id)
            if transaction.outcome is not ApplyOutcome.APPLIED:
                return ProfileAvailabilityResult(
                    availability=current_availability,
                    listen_port=current_profile.listen_port,
                    transaction=transaction,
                    committed_revision=None,
                )
            committed_revision = installation.revision + 1
            self._state_store.save(
                ManagedInstallation(
                    schema_version=installation.schema_version,
                    revision=committed_revision,
                    profiles=profiles,
                    expected_config_sha256=configuration_sha256(document),
                )
            )
            return ProfileAvailabilityResult(
                availability=plan.target,
                listen_port=profile.listen_port,
                transaction=transaction,
                committed_revision=committed_revision,
            )
