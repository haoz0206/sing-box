"""VLESS over TLS and V2Ray transport behavior."""

from dataclasses import dataclass
from urllib.parse import quote, urlencode

from sb_manager.tls.catalog import TlsClientPolicy


@dataclass(frozen=True, slots=True)
class VlessTlsInboundSpec:
    """Values required to build one transported VLESS TLS inbound."""

    tag: str
    profile_name: str
    listen_port: int
    user_uuid: str
    tls: dict[str, object]
    transport: dict[str, object]


@dataclass(frozen=True, slots=True)
class VlessTlsConnectionSpec:
    """Public endpoint, TLS policy, and transport needed by a VLESS client."""

    profile_name: str
    server_address: str
    server_port: int
    user_uuid: str
    tls: TlsClientPolicy
    transport: dict[str, object]


@dataclass(frozen=True, slots=True)
class VlessTlsConnectionInfo:
    """Structured VLESS TLS client settings and share URI."""

    server_address: str
    server_port: int
    user_uuid: str
    server_name: str
    share_uri: str


class VlessTlsProtocol:
    """Build consistent sing-box server and VLESS client artifacts."""

    def build_inbound(self, spec: VlessTlsInboundSpec) -> dict[str, object]:
        return {
            "type": "vless",
            "tag": spec.tag,
            "listen": "::",
            "listen_port": spec.listen_port,
            "users": [{"name": spec.profile_name, "uuid": spec.user_uuid}],
            "tls": spec.tls,
            "transport": spec.transport,
        }

    def build_connection_info(
        self,
        spec: VlessTlsConnectionSpec,
    ) -> VlessTlsConnectionInfo:
        query: list[tuple[str, str]] = [
            ("encryption", "none"),
            ("security", "tls"),
            ("sni", spec.tls.server_name),
            ("type", str(spec.transport["type"])),
        ]
        headers = spec.transport.get("headers")
        if isinstance(headers, dict) and isinstance(host := headers.get("Host"), str):
            query.append(("host", host))
        if isinstance(path := spec.transport.get("path"), str):
            query.append(("path", path))
        share_uri = (
            f"vless://{spec.user_uuid}@{spec.server_address}:{spec.server_port}"
            f"?{urlencode(query)}#{quote(spec.profile_name, safe='')}"
        )
        return VlessTlsConnectionInfo(
            server_address=spec.server_address,
            server_port=spec.server_port,
            user_uuid=spec.user_uuid,
            server_name=spec.tls.server_name,
            share_uri=share_uri,
        )
