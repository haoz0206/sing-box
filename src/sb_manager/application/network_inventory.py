"""Derive operator-facing network intent from one desired-state snapshot."""

from dataclasses import dataclass
from enum import Enum

from sb_manager.domain.installation import (
    ManagedInstallation,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.listener_source import ListenerEndpoint, ListenerTransport


class NetworkProfileState(str, Enum):
    """Lifecycle meaning of one profile's network intent."""

    ENABLED = "enabled"
    PAUSED = "paused"
    DRAFT = "draft"


_TRANSPORTS_BY_PROTOCOL: dict[ProtocolKind, tuple[ListenerTransport, ...]] = {
    ProtocolKind.VLESS_REALITY: (ListenerTransport.TCP,),
    ProtocolKind.SHADOWSOCKS: (ListenerTransport.TCP,),
    ProtocolKind.SNELL_V6: (ListenerTransport.TCP,),
    ProtocolKind.HYSTERIA2: (ListenerTransport.UDP,),
    ProtocolKind.TROJAN: (ListenerTransport.TCP,),
    ProtocolKind.ANYTLS: (ListenerTransport.TCP,),
    ProtocolKind.TUIC: (ListenerTransport.UDP,),
    ProtocolKind.VLESS_TLS: (ListenerTransport.TCP,),
    ProtocolKind.VMESS_TLS: (ListenerTransport.TCP,),
}


@dataclass(frozen=True, slots=True)
class NetworkProfileIntent:
    """Network-relevant intent for one managed profile."""

    profile_id: str
    profile_name: str
    state: NetworkProfileState
    transports: tuple[ListenerTransport, ...]
    listen_port: int | None
    public_address: str | None


@dataclass(frozen=True, slots=True)
class NetworkInventory:
    """Complete read-only network intent for one desired-state revision."""

    revision: int
    profiles: tuple[NetworkProfileIntent, ...]

    @property
    def enabled_count(self) -> int:
        return sum(profile.state is NetworkProfileState.ENABLED for profile in self.profiles)

    @property
    def paused_count(self) -> int:
        return sum(profile.state is NetworkProfileState.PAUSED for profile in self.profiles)

    @property
    def draft_count(self) -> int:
        return sum(profile.state is NetworkProfileState.DRAFT for profile in self.profiles)

    @property
    def active_listener_endpoints(self) -> tuple[ListenerEndpoint, ...]:
        endpoints = {
            ListenerEndpoint(port=profile.listen_port, transport=transport)
            for profile in self.profiles
            if profile.state is NetworkProfileState.ENABLED and profile.listen_port is not None
            for transport in profile.transports
        }
        return tuple(sorted(endpoints, key=lambda item: (item.port, item.transport.value)))


def build_network_inventory(installation: ManagedInstallation) -> NetworkInventory:
    """Project network intent without probing or changing the host."""

    profiles = tuple(
        NetworkProfileIntent(
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            state=(
                NetworkProfileState.DRAFT
                if profile.status is ProfileStatus.DRAFT
                else (
                    NetworkProfileState.ENABLED if profile.enabled else NetworkProfileState.PAUSED
                )
            ),
            transports=_TRANSPORTS_BY_PROTOCOL[profile.protocol],
            listen_port=profile.listen_port,
            public_address=profile.server_address,
        )
        for profile in installation.profiles
    )
    return NetworkInventory(revision=installation.revision, profiles=profiles)
