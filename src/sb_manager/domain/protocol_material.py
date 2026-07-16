"""Persisted protocol-specific material carried by managed profiles."""

from dataclasses import dataclass
from typing import TypeAlias


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


ProtocolMaterial: TypeAlias = (
    RealityMaterial
    | ShadowsocksMaterial
    | Hysteria2Material
    | TrojanMaterial
    | AnyTlsMaterial
    | TuicMaterial
)
