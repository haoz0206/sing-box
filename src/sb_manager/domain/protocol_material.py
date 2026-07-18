"""Persisted protocol-specific material carried by managed profiles."""

import re
from dataclasses import dataclass
from typing import TypeAlias

SNELL_V6_PSK_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


@dataclass(frozen=True, slots=True)
class RealityMaterial:
    """Generated credentials and camouflage values for one Reality profile."""

    user_uuid: str
    private_key: str
    public_key: str
    short_id: str
    server_name: str


@dataclass(frozen=True, slots=True)
class ShadowsocksMaterial:
    """Generated pre-shared key for one Shadowsocks 2022 profile."""

    password: str


@dataclass(frozen=True, slots=True)
class SnellV6Material:
    """Generated pre-shared key for one managed Snell v6 profile."""

    psk: str

    def __post_init__(self) -> None:
        if SNELL_V6_PSK_PATTERN.fullmatch(self.psk) is None:
            raise ValueError("Managed Snell v6 PSK must be 43 URL-safe characters")


@dataclass(frozen=True, slots=True)
class Hysteria2Material:
    """Generated authentication secret for one Hysteria2 profile."""

    password: str


@dataclass(frozen=True, slots=True)
class TrojanMaterial:
    """Generated authentication secret for one Trojan profile."""

    password: str


@dataclass(frozen=True, slots=True)
class AnyTlsMaterial:
    """Generated authentication secret for one AnyTLS profile."""

    password: str


@dataclass(frozen=True, slots=True)
class TuicMaterial:
    """Generated UUID and password for one TUIC profile."""

    user_uuid: str
    password: str


@dataclass(frozen=True, slots=True)
class VlessMaterial:
    """Generated UUID for one transported VLESS profile."""

    user_uuid: str


@dataclass(frozen=True, slots=True)
class VmessMaterial:
    """Generated UUID for one VMess profile."""

    user_uuid: str


ProtocolMaterial: TypeAlias = (
    RealityMaterial
    | ShadowsocksMaterial
    | SnellV6Material
    | Hysteria2Material
    | TrojanMaterial
    | AnyTlsMaterial
    | TuicMaterial
    | VlessMaterial
    | VmessMaterial
)
