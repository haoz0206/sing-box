"""VLESS Reality configuration behavior."""

from dataclasses import dataclass
from urllib.parse import quote, urlencode

from sb_manager.domain.protocol_material import RealityMaterial

REALITY_FLOW = "xtls-rprx-vision"

__all__ = [
    "RealityConnectionInfo",
    "RealityConnectionSpec",
    "RealityInboundSpec",
    "RealityMaterial",
    "RealityProtocol",
]


@dataclass(frozen=True)
class RealityInboundSpec:
    """Values required to build one VLESS Reality inbound."""

    tag: str
    profile_name: str
    listen_port: int
    user_uuid: str
    server_name: str
    private_key: str
    short_id: str


@dataclass(frozen=True, slots=True)
class RealityConnectionSpec:
    """Server endpoint and public material needed by a Reality client."""

    profile_name: str
    server_address: str
    server_port: int
    user_uuid: str
    server_name: str
    public_key: str
    short_id: str


@dataclass(frozen=True, slots=True)
class RealityConnectionInfo:
    """Structured client settings and their standard VLESS share URI."""

    server_address: str
    server_port: int
    user_uuid: str
    server_name: str
    public_key: str
    short_id: str
    flow: str
    share_uri: str


class RealityProtocol:
    """Build sing-box configuration fragments for VLESS Reality."""

    def build_inbound(self, spec: RealityInboundSpec) -> dict[str, object]:
        """Return the inbound represented by ``spec`` without side effects."""
        return {
            "type": "vless",
            "tag": spec.tag,
            "listen": "::",
            "listen_port": spec.listen_port,
            "users": [
                {
                    "name": spec.profile_name,
                    "uuid": spec.user_uuid,
                    "flow": REALITY_FLOW,
                }
            ],
            "tls": {
                "enabled": True,
                "server_name": spec.server_name,
                "reality": {
                    "enabled": True,
                    "handshake": {
                        "server": spec.server_name,
                        "server_port": 443,
                    },
                    "private_key": spec.private_key,
                    "short_id": [spec.short_id],
                },
            },
        }

    def build_connection_info(self, spec: RealityConnectionSpec) -> RealityConnectionInfo:
        """Return public client settings without exposing the Reality private key."""
        query = urlencode(
            (
                ("encryption", "none"),
                ("flow", REALITY_FLOW),
                ("security", "reality"),
                ("sni", spec.server_name),
                ("fp", "chrome"),
                ("pbk", spec.public_key),
                ("sid", spec.short_id),
                ("type", "tcp"),
            )
        )
        share_uri = (
            f"vless://{spec.user_uuid}@{spec.server_address}:{spec.server_port}"
            f"?{query}#{quote(spec.profile_name, safe='')}"
        )
        return RealityConnectionInfo(
            server_address=spec.server_address,
            server_port=spec.server_port,
            user_uuid=spec.user_uuid,
            server_name=spec.server_name,
            public_key=spec.public_key,
            short_id=spec.short_id,
            flow=REALITY_FLOW,
            share_uri=share_uri,
        )
