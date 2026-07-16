from dataclasses import dataclass
from enum import Enum

from sb_manager.domain.protocol_material import ProtocolMaterial
from sb_manager.tls.catalog import TlsIntent

CURRENT_SCHEMA_VERSION = 1


class ProtocolKind(str, Enum):
    """Protocols represented in manager-owned desired state."""

    VLESS_REALITY = "vless-reality"
    SHADOWSOCKS = "shadowsocks-2022"
    HYSTERIA2 = "hysteria2"
    TROJAN = "trojan"
    ANYTLS = "anytls"
    TUIC = "tuic"


class PortSelection(str, Enum):
    """Whether apply should honor a fixed port or choose an available one."""

    FIXED = "fixed"
    AUTOMATIC = "automatic"


class ProfileStatus(str, Enum):
    """Lifecycle state visible to the operator."""

    DRAFT = "draft"
    APPLIED = "applied"


@dataclass(frozen=True, slots=True)
class ManagedProfile:
    """One profile in manager-owned desired state."""

    profile_name: str
    protocol: ProtocolKind
    listen_port: int | None
    port_selection: PortSelection
    status: ProfileStatus
    profile_id: str = ""
    protocol_material: ProtocolMaterial | None = None
    server_address: str | None = None
    tls_intent: TlsIntent | None = None


@dataclass(frozen=True, slots=True)
class ManagedInstallation:
    """Versioned desired state for one managed host."""

    schema_version: int
    revision: int
    profiles: tuple[ManagedProfile, ...]

    @classmethod
    def empty(cls) -> "ManagedInstallation":
        return cls(schema_version=CURRENT_SCHEMA_VERSION, revision=0, profiles=())
