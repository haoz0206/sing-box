"""TUIC configuration and connection behavior."""

from dataclasses import dataclass
from urllib.parse import quote

from sb_manager.tls.catalog import TlsClientPolicy


@dataclass(frozen=True, slots=True)
class TuicInboundSpec:
    """Values required to build one TUIC inbound."""

    tag: str
    profile_name: str
    listen_port: int
    user_uuid: str
    password: str
    tls: dict[str, object]


@dataclass(frozen=True, slots=True)
class TuicConnectionSpec:
    """Public endpoint and TLS policy needed by a TUIC client."""

    profile_name: str
    server_address: str
    server_port: int
    user_uuid: str
    password: str
    tls: TlsClientPolicy


@dataclass(frozen=True, slots=True)
class TuicConnectionInfo:
    """Structured TUIC client settings and compatibility URI."""

    server_address: str
    server_port: int
    user_uuid: str
    password: str
    server_name: str
    share_uri: str


class TuicProtocol:
    """Build consistent sing-box server and TUIC client artifacts."""

    def build_inbound(self, spec: TuicInboundSpec) -> dict[str, object]:
        return {
            "type": "tuic",
            "tag": spec.tag,
            "listen": "::",
            "listen_port": spec.listen_port,
            "users": [
                {
                    "name": spec.profile_name,
                    "uuid": spec.user_uuid,
                    "password": spec.password,
                }
            ],
            "congestion_control": "cubic",
            "zero_rtt_handshake": False,
            "tls": spec.tls,
        }

    def build_connection_info(self, spec: TuicConnectionSpec) -> TuicConnectionInfo:
        user_uuid = quote(spec.user_uuid, safe="")
        password = quote(spec.password, safe="")
        server_name = quote(spec.tls.server_name, safe="")
        profile_name = quote(spec.profile_name, safe="")
        insecure = int(spec.tls.insecure)
        share_uri = (
            f"tuic://{user_uuid}:{password}@{spec.server_address}:{spec.server_port}/"
            "?congestion_control=cubic&udp_relay_mode=native"
            f"&sni={server_name}&allow_insecure={insecure}#{profile_name}"
        )
        return TuicConnectionInfo(
            server_address=spec.server_address,
            server_port=spec.server_port,
            user_uuid=spec.user_uuid,
            password=spec.password,
            server_name=spec.tls.server_name,
            share_uri=share_uri,
        )
