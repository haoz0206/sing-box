"""Hysteria2 configuration and connection behavior."""

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from sb_manager.tls.catalog import TlsClientPolicy


@dataclass(frozen=True, slots=True)
class Hysteria2InboundSpec:
    """Values required to build one Hysteria2 inbound."""

    tag: str
    profile_name: str
    listen_port: int
    password: str
    tls: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class Hysteria2ConnectionSpec:
    """Public endpoint, authentication, and TLS policy for a client."""

    profile_name: str
    server_address: str
    server_port: int
    password: str
    tls: TlsClientPolicy


@dataclass(frozen=True, slots=True)
class Hysteria2ConnectionInfo:
    """Structured client settings and their official Hysteria2 URI."""

    server_address: str
    server_port: int
    password: str
    server_name: str
    insecure: bool
    share_uri: str


class Hysteria2Protocol:
    """Build sing-box and client artifacts for Hysteria2."""

    def build_inbound(self, spec: Hysteria2InboundSpec) -> dict[str, object]:
        return {
            "type": "hysteria2",
            "tag": spec.tag,
            "listen": "::",
            "listen_port": spec.listen_port,
            "users": [{"name": spec.profile_name, "password": spec.password}],
            "ignore_client_bandwidth": True,
            "tls": dict(spec.tls),
        }

    def build_connection_info(self, spec: Hysteria2ConnectionSpec) -> Hysteria2ConnectionInfo:
        query = urlencode(
            (
                ("sni", spec.tls.server_name),
                ("insecure", "1" if spec.tls.insecure else "0"),
            )
        )
        share_uri = (
            f"hysteria2://{quote(spec.password, safe='')}@"
            f"{spec.server_address}:{spec.server_port}/?{query}"
            f"#{quote(spec.profile_name, safe='')}"
        )
        return Hysteria2ConnectionInfo(
            server_address=spec.server_address,
            server_port=spec.server_port,
            password=spec.password,
            server_name=spec.tls.server_name,
            insecure=spec.tls.insecure,
            share_uri=share_uri,
        )
