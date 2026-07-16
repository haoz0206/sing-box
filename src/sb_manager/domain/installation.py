from dataclasses import dataclass
from enum import Enum

from sb_manager.domain.protocol_material import ProtocolMaterial
from sb_manager.tls.catalog import TlsIntent
from sb_manager.transports.catalog import TransportIntent

CURRENT_SCHEMA_VERSION = 1
CONFIG_SHA256_HEX_LENGTH = 64


class ProtocolKind(str, Enum):
    """Protocols represented in manager-owned desired state."""

    VLESS_REALITY = "vless-reality"
    SHADOWSOCKS = "shadowsocks-2022"
    HYSTERIA2 = "hysteria2"
    TROJAN = "trojan"
    ANYTLS = "anytls"
    TUIC = "tuic"
    VLESS_TLS = "vless-tls"
    VMESS_TLS = "vmess-tls"


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
    enabled: bool = True
    profile_id: str = ""
    protocol_material: ProtocolMaterial | None = None
    server_address: str | None = None
    tls_intent: TlsIntent | None = None
    transport_intent: TransportIntent | None = None


@dataclass(frozen=True, slots=True)
class ManagedInstallation:
    """Versioned desired state for one managed host."""

    schema_version: int
    revision: int
    profiles: tuple[ManagedProfile, ...]
    expected_config_sha256: str | None = None

    def __post_init__(self) -> None:
        fingerprint = self.expected_config_sha256
        if fingerprint is not None and (
            len(fingerprint) != CONFIG_SHA256_HEX_LENGTH
            or any(character not in "0123456789abcdef" for character in fingerprint)
        ):
            raise ValueError("Expected configuration SHA-256 must be 64 lowercase hex")

    @classmethod
    def empty(cls) -> "ManagedInstallation":
        return cls(schema_version=CURRENT_SCHEMA_VERSION, revision=0, profiles=())
