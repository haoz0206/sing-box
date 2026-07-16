"""Create a safe draft from reusable profile intent without copying secrets."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.state_store import StateStore
from sb_manager.tls.catalog import TlsIntent
from sb_manager.transports.catalog import TransportIntent


class ProfileCloneError(RuntimeError):
    """Base error for a rejected profile-template workflow."""


class ProfileCloneNotFoundError(ProfileCloneError):
    """The selected source profile no longer exists."""


class ProfileCloneNameError(ProfileCloneError):
    """The requested draft name is blank or already in use."""


class ProfileCloneConfirmationRequiredError(ProfileCloneError):
    """Creating the desired-state draft requires explicit confirmation."""


class ProfileCloneSourceChangedError(ProfileCloneError):
    """Reusable source intent no longer matches the reviewed template."""


class ProfileCloneFacet(str, Enum):
    """One profile aspect shown as copied or intentionally reset."""

    PROTOCOL = "protocol"
    SERVER_ADDRESS = "server-address"
    TLS_STRATEGY = "tls-strategy"
    TRANSPORT = "transport"
    CREDENTIALS = "credentials"
    LISTEN_PORT = "listen-port"
    RUNTIME_STATUS = "runtime-status"


@dataclass(frozen=True, slots=True)
class PlanProfileCloneRequest:
    """Operator input for a read-only profile-template plan."""

    source_profile_id: str
    profile_name: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileCloneSourceIntent:
    """Only the non-secret source fields a clone is allowed to consume."""

    profile_name: str
    protocol: ProtocolKind
    server_address: str | None
    tls_intent: TlsIntent | None
    transport_intent: TransportIntent | None


@dataclass(frozen=True, slots=True)
class ProfileClonePlan:
    """Reviewable intent for one new secret-free automatic-port draft."""

    source_profile_id: str
    source_profile_name: str
    profile_name: str
    protocol: ProtocolKind
    base_revision: int
    source_intent: ProfileCloneSourceIntent
    copied_facets: tuple[ProfileCloneFacet, ...]
    reset_facets: tuple[ProfileCloneFacet, ...]
    mutates_host: bool = False


@dataclass(frozen=True, slots=True)
class ProfileCloneResult:
    """Desired-state identity committed for the newly created draft."""

    profile_id: str
    profile_name: str
    committed_revision: int


class ProfileCloner(Protocol):
    """TUI-facing interface for planning and confirming a safe template clone."""

    def plan(self, request: PlanProfileCloneRequest) -> ProfileClonePlan: ...

    def clone(
        self,
        plan: ProfileClonePlan,
        *,
        confirmed: bool,
    ) -> ProfileCloneResult: ...


class ProfileCloningService:
    """Copy reusable intent while forcing new material and port allocation."""

    def __init__(self, *, state_store: StateStore, mutation_lock: ApplyLock) -> None:
        self._state_store = state_store
        self._mutation_lock = mutation_lock

    def plan(self, request: PlanProfileCloneRequest) -> ProfileClonePlan:
        installation = self._state_store.load()
        source = self._find_profile(installation, request.source_profile_id)
        profile_name = self._resolve_name(
            installation,
            source=source,
            requested_name=request.profile_name,
        )
        copied_facets = [ProfileCloneFacet.PROTOCOL]
        if source.server_address is not None:
            copied_facets.append(ProfileCloneFacet.SERVER_ADDRESS)
        if source.tls_intent is not None:
            copied_facets.append(ProfileCloneFacet.TLS_STRATEGY)
        if source.transport_intent is not None:
            copied_facets.append(ProfileCloneFacet.TRANSPORT)
        return ProfileClonePlan(
            source_profile_id=source.profile_id,
            source_profile_name=source.profile_name,
            profile_name=profile_name,
            protocol=source.protocol,
            base_revision=installation.revision,
            source_intent=self._source_intent(source),
            copied_facets=tuple(copied_facets),
            reset_facets=(
                ProfileCloneFacet.CREDENTIALS,
                ProfileCloneFacet.LISTEN_PORT,
                ProfileCloneFacet.RUNTIME_STATUS,
            ),
        )

    def clone(
        self,
        plan: ProfileClonePlan,
        *,
        confirmed: bool,
    ) -> ProfileCloneResult:
        if not confirmed:
            raise ProfileCloneConfirmationRequiredError(
                "Profile template creation requires explicit confirmation"
            )
        with self._mutation_lock.acquire():
            return self._clone(plan)

    def _clone(self, plan: ProfileClonePlan) -> ProfileCloneResult:
        installation = self._state_store.load()
        if installation.revision != plan.base_revision:
            raise StateRevisionConflictError(
                expected=plan.base_revision,
                actual=installation.revision,
            )
        source = self._find_profile(installation, plan.source_profile_id)
        if self._source_intent(source) != plan.source_intent:
            raise ProfileCloneSourceChangedError("模板配置内容已变化，请重新审阅后再创建草案")
        self._require_available_name(installation, plan.profile_name)
        committed_revision = installation.revision + 1
        profile_id = f"profile-{committed_revision}"
        clone = ManagedProfile(
            profile_id=profile_id,
            profile_name=plan.profile_name,
            protocol=source.protocol,
            listen_port=None,
            port_selection=PortSelection.AUTOMATIC,
            status=ProfileStatus.DRAFT,
            enabled=True,
            protocol_material=None,
            server_address=source.server_address,
            tls_intent=source.tls_intent,
            transport_intent=source.transport_intent,
        )
        self._state_store.save(
            ManagedInstallation(
                schema_version=installation.schema_version,
                revision=committed_revision,
                profiles=(*installation.profiles, clone),
                expected_config_sha256=installation.expected_config_sha256,
            )
        )
        return ProfileCloneResult(
            profile_id=profile_id,
            profile_name=clone.profile_name,
            committed_revision=committed_revision,
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
            raise ProfileCloneNotFoundError(profile_id) from error

    @staticmethod
    def _source_intent(source: ManagedProfile) -> ProfileCloneSourceIntent:
        return ProfileCloneSourceIntent(
            profile_name=source.profile_name,
            protocol=source.protocol,
            server_address=source.server_address,
            tls_intent=source.tls_intent,
            transport_intent=source.transport_intent,
        )

    @classmethod
    def _resolve_name(
        cls,
        installation: ManagedInstallation,
        *,
        source: ManagedProfile,
        requested_name: str | None,
    ) -> str:
        if requested_name is not None:
            profile_name = requested_name.strip()
            if not profile_name:
                raise ProfileCloneNameError("配置名称不能为空")
            cls._require_available_name(installation, profile_name)
            return profile_name

        existing_names = {profile.profile_name for profile in installation.profiles}
        source_name = source.profile_name.strip() or "配置"
        base_name = f"{source_name} 副本"
        if base_name not in existing_names:
            return base_name
        suffix = 2
        while f"{base_name} {suffix}" in existing_names:
            suffix += 1
        return f"{base_name} {suffix}"

    @staticmethod
    def _require_available_name(
        installation: ManagedInstallation,
        profile_name: str,
    ) -> None:
        if any(profile.profile_name == profile_name for profile in installation.profiles):
            raise ProfileCloneNameError(f"配置名称已存在：{profile_name}")
