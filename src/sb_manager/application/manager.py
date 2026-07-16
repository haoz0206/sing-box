from contextlib import nullcontext
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.state_store import StateStore
from sb_manager.tls.catalog import AcmeTlsIntent, TlsIntent

MAX_LISTEN_PORT = 65_535


class GeneratedValue(str, Enum):
    """Values the manager promises to generate during a later apply."""

    UUID = "uuid"
    REALITY_KEY_PAIR = "reality-key-pair"
    SERVER_NAME = "server-name"
    SHADOWSOCKS_KEY = "shadowsocks-key"
    HYSTERIA2_PASSWORD = "hysteria2-password"
    TROJAN_PASSWORD = "trojan-password"
    ANYTLS_PASSWORD = "anytls-password"
    TUIC_UUID = "tuic-uuid"
    TUIC_PASSWORD = "tuic-password"
    TLS_CERTIFICATE = "tls-certificate"


GENERATED_VALUES_BY_PROTOCOL: dict[ProtocolKind, tuple[GeneratedValue, ...]] = {
    ProtocolKind.VLESS_REALITY: (
        GeneratedValue.UUID,
        GeneratedValue.REALITY_KEY_PAIR,
        GeneratedValue.SERVER_NAME,
    ),
    ProtocolKind.SHADOWSOCKS: (GeneratedValue.SHADOWSOCKS_KEY,),
    ProtocolKind.HYSTERIA2: (
        GeneratedValue.HYSTERIA2_PASSWORD,
        GeneratedValue.TLS_CERTIFICATE,
    ),
    ProtocolKind.TROJAN: (
        GeneratedValue.TROJAN_PASSWORD,
        GeneratedValue.TLS_CERTIFICATE,
    ),
    ProtocolKind.ANYTLS: (
        GeneratedValue.ANYTLS_PASSWORD,
        GeneratedValue.TLS_CERTIFICATE,
    ),
    ProtocolKind.TUIC: (
        GeneratedValue.TUIC_UUID,
        GeneratedValue.TUIC_PASSWORD,
        GeneratedValue.TLS_CERTIFICATE,
    ),
}

TLS_REQUIRED_PROTOCOLS = frozenset(
    (ProtocolKind.HYSTERIA2, ProtocolKind.TROJAN, ProtocolKind.ANYTLS, ProtocolKind.TUIC)
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One user-correctable issue tied to a public request field."""

    field: str
    message: str


class PlanValidationError(ValueError):
    """A profile plan could not be built from the operator's input."""

    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        super().__init__("Profile plan input is invalid")
        self.issues = issues


class StateRevisionConflictError(RuntimeError):
    """A plan is based on desired state that has since changed."""

    def __init__(self, *, expected: int, actual: int) -> None:
        super().__init__(f"State revision changed from {expected} to {actual}")
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True, slots=True)
class AcmeTlsRequest:
    """User-facing ACME inputs without internal storage policy."""

    server_name: str
    email: str


@dataclass(frozen=True, slots=True)
class PlanProfileRequest:
    """Validated operator intent needed to preview a profile."""

    profile_name: str
    protocol: ProtocolKind
    listen_port: int | None
    server_address: str | None = None
    tls: AcmeTlsRequest | None = None


@dataclass(frozen=True, slots=True)
class ProfilePlan:
    """A side-effect-free profile plan suitable for presentation."""

    profile_name: str
    protocol: ProtocolKind
    listen_port: int | None
    port_selection: PortSelection
    base_revision: int
    generated_values: tuple[GeneratedValue, ...]
    mutates_host: bool
    server_address: str | None = None
    tls_intent: TlsIntent | None = None


class Manager:
    """Public application seam for manager use cases."""

    def __init__(
        self,
        state_store: StateStore | None = None,
        mutation_lock: ApplyLock | None = None,
        acme_data_directory: Path = Path("/var/lib/sing-box-manager/acme"),
    ) -> None:
        self._state_store = state_store
        self._mutation_lock = mutation_lock
        self._acme_data_directory = acme_data_directory

    def plan_profile(self, request: PlanProfileRequest) -> ProfilePlan:
        issues: list[ValidationIssue] = []
        if not request.profile_name.strip():
            issues.append(ValidationIssue(field="profile_name", message="请输入配置名称"))
        if request.listen_port is not None and not 1 <= request.listen_port <= MAX_LISTEN_PORT:
            issues.append(
                ValidationIssue(
                    field="listen_port",
                    message="端口必须在 1 到 65535 之间",
                )
            )
        if request.protocol in TLS_REQUIRED_PROTOCOLS:
            if request.tls is None:
                issues.append(ValidationIssue(field="tls", message="请选择 TLS 证书方式"))
            else:
                if not request.tls.server_name.strip():
                    issues.append(
                        ValidationIssue(field="tls_server_name", message="请输入证书域名")
                    )
                if not request.tls.email.strip():
                    issues.append(
                        ValidationIssue(field="tls_email", message="请输入 ACME 联系邮箱")
                    )
        if issues:
            raise PlanValidationError(tuple(issues))

        base_revision = self._state_store.load().revision if self._state_store is not None else 0
        return ProfilePlan(
            profile_name=request.profile_name,
            protocol=request.protocol,
            listen_port=request.listen_port,
            port_selection=(
                PortSelection.AUTOMATIC if request.listen_port is None else PortSelection.FIXED
            ),
            base_revision=base_revision,
            generated_values=GENERATED_VALUES_BY_PROTOCOL[request.protocol],
            mutates_host=False,
            server_address=(
                request.server_address.strip() if request.server_address is not None else None
            )
            or None,
            tls_intent=(
                AcmeTlsIntent(
                    server_name=request.tls.server_name.strip(),
                    email=request.tls.email.strip(),
                    data_directory=self._acme_data_directory,
                )
                if request.tls is not None
                else None
            ),
        )

    def save_profile_draft(self, plan: ProfilePlan) -> None:
        lock = self._mutation_lock.acquire() if self._mutation_lock is not None else nullcontext()
        with lock:
            self._save_profile_draft(plan)

    def _save_profile_draft(self, plan: ProfilePlan) -> None:
        state_store = self._require_state_store()
        installation = state_store.load()
        if installation.revision != plan.base_revision:
            raise StateRevisionConflictError(
                expected=plan.base_revision,
                actual=installation.revision,
            )
        profile = ManagedProfile(
            profile_name=plan.profile_name,
            protocol=plan.protocol,
            listen_port=plan.listen_port,
            port_selection=plan.port_selection,
            status=ProfileStatus.DRAFT,
            profile_id=f"profile-{installation.revision + 1}",
            server_address=plan.server_address,
            tls_intent=plan.tls_intent,
        )
        state_store.save(
            ManagedInstallation(
                schema_version=installation.schema_version,
                revision=installation.revision + 1,
                profiles=(*installation.profiles, profile),
            )
        )

    def get_installation(self) -> ManagedInstallation:
        return self._require_state_store().load()

    def _require_state_store(self) -> StateStore:
        if self._state_store is None:
            raise RuntimeError("This manager has no state store")
        return self._state_store
