"""AnyTLS configuration and connection behavior."""

from dataclasses import dataclass
from urllib.parse import quote

from sb_manager.tls.catalog import TlsClientPolicy


@dataclass(frozen=True, slots=True)
class AnyTlsInboundSpec:
    """Values required to build one AnyTLS inbound."""

    tag: str
    profile_name: str
    listen_port: int
    password: str
    tls: dict[str, object]


@dataclass(frozen=True, slots=True)
class AnyTlsConnectionSpec:
    """Public endpoint and TLS policy needed by an AnyTLS client."""

    profile_name: str
    server_address: str
    server_port: int
    password: str
    tls: TlsClientPolicy


@dataclass(frozen=True, slots=True)
class AnyTlsConnectionInfo:
    """Structured AnyTLS client settings and share URI."""

    server_address: str
    server_port: int
    password: str
    server_name: str
    share_uri: str


class AnyTlsProtocol:
    """Build consistent sing-box server and AnyTLS client artifacts."""

    def build_inbound(self, spec: AnyTlsInboundSpec) -> dict[str, object]:
        return {
            "type": "anytls",
            "tag": spec.tag,
            "listen": "::",
            "listen_port": spec.listen_port,
            "users": [{"name": spec.profile_name, "password": spec.password}],
            "tls": spec.tls,
        }

    def build_connection_info(self, spec: AnyTlsConnectionSpec) -> AnyTlsConnectionInfo:
        password = quote(spec.password, safe="")
        server_name = quote(spec.tls.server_name, safe="")
        profile_name = quote(spec.profile_name, safe="")
        insecure = int(spec.tls.insecure)
        share_uri = (
            f"anytls://{password}@{spec.server_address}:{spec.server_port}/"
            f"?sni={server_name}&insecure={insecure}#{profile_name}"
        )
        return AnyTlsConnectionInfo(
            server_address=spec.server_address,
            server_port=spec.server_port,
            password=spec.password,
            server_name=spec.tls.server_name,
            share_uri=share_uri,
        )
