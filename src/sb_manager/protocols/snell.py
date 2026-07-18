"""Pure Snell v6 configuration and connection artifact serialization."""

from dataclasses import dataclass
from hashlib import sha256

from sb_manager.domain.protocol_material import SnellV6Material


@dataclass(frozen=True, slots=True)
class SnellV6InboundSpec:
    tag: str
    listen_port: int
    psk: str


@dataclass(frozen=True, slots=True)
class SnellV6ConnectionSpec:
    profile_id: str
    server_address: str
    server_port: int
    psk: str


@dataclass(frozen=True, slots=True)
class SnellV6ConnectionInfo:
    server_address: str
    server_port: int
    psk: str
    surge_policy: str


class SnellV6Protocol:
    """Build the managed sing-box inbound and Surge policy for Snell v6."""

    def build_inbound(self, spec: SnellV6InboundSpec) -> dict[str, object]:
        SnellV6Material(psk=spec.psk)
        return {
            "type": "snell",
            "tag": spec.tag,
            "listen": "::",
            "listen_port": spec.listen_port,
            "version": 6,
            "psk": spec.psk,
            "mode": "default",
        }

    def build_connection_info(self, spec: SnellV6ConnectionSpec) -> SnellV6ConnectionInfo:
        SnellV6Material(psk=spec.psk)
        stable_id = sha256(spec.profile_id.encode()).hexdigest()[:12]
        surge_policy = (
            f"Snell-{stable_id} = snell, {spec.server_address}, {spec.server_port}, "
            f"psk={spec.psk}, version=6"
        )
        return SnellV6ConnectionInfo(
            server_address=spec.server_address,
            server_port=spec.server_port,
            psk=spec.psk,
            surge_policy=surge_policy,
        )
