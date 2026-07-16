"""VMess over TLS and V2Ray transport behavior."""

import base64
import json
from dataclasses import dataclass

from sb_manager.tls.catalog import TlsClientPolicy


@dataclass(frozen=True, slots=True)
class VmessTlsInboundSpec:
    tag: str
    profile_name: str
    listen_port: int
    user_uuid: str
    tls: dict[str, object]
    transport: dict[str, object]


@dataclass(frozen=True, slots=True)
class VmessTlsConnectionSpec:
    profile_name: str
    server_address: str
    server_port: int
    user_uuid: str
    tls: TlsClientPolicy
    transport: dict[str, object]


@dataclass(frozen=True, slots=True)
class VmessTlsConnectionInfo:
    server_address: str
    server_port: int
    user_uuid: str
    server_name: str
    share_uri: str


class VmessTlsProtocol:
    """Build modern VMess server and client artifacts with legacy auth disabled."""

    def build_inbound(self, spec: VmessTlsInboundSpec) -> dict[str, object]:
        return {
            "type": "vmess",
            "tag": spec.tag,
            "listen": "::",
            "listen_port": spec.listen_port,
            "users": [
                {
                    "name": spec.profile_name,
                    "uuid": spec.user_uuid,
                    "alterId": 0,
                }
            ],
            "tls": spec.tls,
            "transport": spec.transport,
        }

    def build_connection_info(
        self,
        spec: VmessTlsConnectionSpec,
    ) -> VmessTlsConnectionInfo:
        headers = spec.transport.get("headers")
        host = ""
        if isinstance(headers, dict) and isinstance(header_host := headers.get("Host"), str):
            host = header_host
        transport_path = spec.transport.get("path", spec.transport.get("service_name", ""))
        payload = {
            "v": "2",
            "ps": spec.profile_name,
            "add": spec.server_address,
            "port": str(spec.server_port),
            "id": spec.user_uuid,
            "aid": "0",
            "scy": "auto",
            "net": str(spec.transport["type"]),
            "type": "none",
            "host": host,
            "path": str(transport_path),
            "tls": "tls",
            "sni": spec.tls.server_name,
        }
        encoded = base64.b64encode(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        ).decode()
        return VmessTlsConnectionInfo(
            server_address=spec.server_address,
            server_port=spec.server_port,
            user_uuid=spec.user_uuid,
            server_name=spec.tls.server_name,
            share_uri=f"vmess://{encoded}",
        )
