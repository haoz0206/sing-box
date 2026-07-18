"""Application use case for applying one managed proxy profile."""

from dataclasses import dataclass
from typing import Protocol

from sb_manager.application.configuration_projection import ManagedConfigurationProjector
from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.protocol_compatibility import (
    ActiveCoreProtocolCompatibility,
    CoreVersionUnknown,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    ProtocolKind,
)
from sb_manager.protocols.catalog import MaterializedProfile, ProfileConnectionInfo, ProtocolCatalog
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.configuration_applier import ConfigurationApplier, ConfigurationApplyError
from sb_manager.seams.port_source import PortSource
from sb_manager.seams.state_store import StateStore
from sb_manager.tls.catalog import TlsMaterialError
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    ConfigTargetPrecondition,
)
from sb_manager.transactions.staging import configuration_sha256


class ProfileNotFoundError(LookupError):
    """The requested stable profile identifier is not in desired state."""


class PortUnavailableError(RuntimeError):
    """A fixed listen port is no longer available at apply time."""


class ApplyConfirmationRequiredError(PermissionError):
    """An apply request must carry the operator's explicit confirmation."""


class ProfileMaterializationError(ConfigurationApplyError):
    """A profile cannot be converted into a candidate host configuration."""


@dataclass(frozen=True, slots=True)
class ApplyProfileRequest:
    """Operator authorization to apply a specific desired-state revision."""

    profile_id: str
    expected_revision: int
    confirmed: bool
    expected_core_version: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileApplyPlan:
    """Read-only active-core evidence for one exact draft revision."""

    profile_id: str
    profile_name: str
    expected_revision: int
    observed_core_version: str | None


@dataclass(frozen=True, slots=True)
class ApplyProfileResult:
    """Application outcome, including the desired-state revision if committed."""

    transaction: ApplyTransactionResult
    committed_revision: int | None
    connection_info: ProfileConnectionInfo | None = None


class ProfileApplier(Protocol):
    """Public application seam consumed by the TUI."""

    def plan_profile(self, profile_id: str) -> ProfileApplyPlan: ...

    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult: ...


class ProfileApplyService:
    """Materialize, apply, and commit one managed profile."""

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
        self._protocol_catalog = protocol_catalog
        self._configuration_projector = ManagedConfigurationProjector(
            protocol_catalog=protocol_catalog
        )
        self._port_source = port_source
        self._applier = applier
        self._apply_lock = apply_lock
        self._core_compatibility = core_compatibility or ActiveCoreProtocolCompatibility()

    def plan_profile(self, profile_id: str) -> ProfileApplyPlan:
        installation = self._state_store.load()
        profile = self._find_profile(installation, profile_id)
        observed_core_version = self._core_compatibility.require_protocol(profile.protocol)
        if profile.protocol is ProtocolKind.SNELL_V6 and observed_core_version is None:
            raise CoreVersionUnknown(protocol=profile.protocol)
        return ProfileApplyPlan(
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            expected_revision=installation.revision,
            observed_core_version=observed_core_version,
        )

    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        if not request.confirmed:
            raise ApplyConfirmationRequiredError("Profile apply requires explicit confirmation")
        with self._apply_lock.acquire():
            return self._apply_confirmed_profile(request)

    def _apply_confirmed_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        installation = self._state_store.load()
        if installation.revision != request.expected_revision:
            raise StateRevisionConflictError(
                expected=request.expected_revision,
                actual=installation.revision,
            )
        profile = self._find_profile(installation, request.profile_id)
        if profile.protocol is ProtocolKind.SNELL_V6 and request.expected_core_version is None:
            raise CoreVersionUnknown(protocol=profile.protocol)
        current_version = self._core_compatibility.require_protocol(
            profile.protocol,
            expected_version=request.expected_core_version,
        )
        if profile.protocol is ProtocolKind.SNELL_V6 and current_version is None:
            raise CoreVersionUnknown(protocol=profile.protocol)
        listen_port = profile.listen_port
        if listen_port is None:
            listen_port = self._port_source.choose_available()
        elif not self._port_source.is_available(listen_port):
            raise PortUnavailableError(f"Port {listen_port} is not available")

        candidate = self._materialize_profile(profile, listen_port=listen_port)
        projected_profiles = tuple(
            candidate.profile if existing.profile_id == profile.profile_id else existing
            for existing in installation.profiles
        )
        document = self._configuration_projector.project(projected_profiles)
        precondition = (
            ConfigTargetPrecondition.matching_sha256(installation.expected_config_sha256)
            if installation.expected_config_sha256 is not None
            else ConfigTargetPrecondition.absent()
        )
        transaction = self._applier.apply(document, precondition=precondition)
        if transaction.outcome is not ApplyOutcome.APPLIED:
            return ApplyProfileResult(transaction=transaction, committed_revision=None)

        committed_revision = installation.revision + 1
        self._state_store.save(
            ManagedInstallation(
                schema_version=installation.schema_version,
                revision=committed_revision,
                profiles=projected_profiles,
                expected_config_sha256=configuration_sha256(document),
            )
        )
        return ApplyProfileResult(
            transaction=transaction,
            committed_revision=committed_revision,
            connection_info=candidate.connection_info,
        )

    @staticmethod
    def _find_profile(
        installation: ManagedInstallation,
        profile_id: str,
    ) -> ManagedProfile:
        try:
            return next(
                profile for profile in installation.profiles if profile.profile_id == profile_id
            )
        except StopIteration as error:
            raise ProfileNotFoundError(profile_id) from error

    def _materialize_profile(
        self,
        profile: ManagedProfile,
        *,
        listen_port: int,
    ) -> MaterializedProfile:
        try:
            return self._protocol_catalog.materialize(profile, listen_port=listen_port)
        except TlsMaterialError as error:
            raise ProfileMaterializationError(str(error)) from error
