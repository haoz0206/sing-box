"""Shadowsocks 2022 configuration and connection behavior."""

import base64
from dataclasses import dataclass
from urllib.parse import quote

SHADOWSOCKS_METHOD = "2022-blake3-aes-128-gcm"


@dataclass(frozen=True, slots=True)
class ShadowsocksInboundSpec:
    """Values required to build one Shadowsocks 2022 inbound."""

    tag: str
    listen_port: int
    password: str


@dataclass(frozen=True, slots=True)
class ShadowsocksConnectionSpec:
    """Public endpoint and secret needed by a Shadowsocks client."""

    profile_name: str
    server_address: str
    server_port: int
    password: str


@dataclass(frozen=True, slots=True)
class ShadowsocksConnectionInfo:
    """Structured client settings and their SIP002 share URI."""

    server_address: str
    server_port: int
    method: str
    password: str
    share_uri: str


class ShadowsocksProtocol:
    """Build sing-box and client artifacts for Shadowsocks 2022."""

    def build_inbound(self, spec: ShadowsocksInboundSpec) -> dict[str, object]:
        return {
            "type": "shadowsocks",
            "tag": spec.tag,
            "listen": "::",
            "listen_port": spec.listen_port,
            "network": "tcp",
            "method": SHADOWSOCKS_METHOD,
            "password": spec.password,
            "multiplex": {"enabled": True},
        }

    def build_connection_info(self, spec: ShadowsocksConnectionSpec) -> ShadowsocksConnectionInfo:
        user_info = base64.urlsafe_b64encode(
            f"{SHADOWSOCKS_METHOD}:{spec.password}".encode()
        ).decode()
        user_info = user_info.rstrip("=")
        share_uri = (
            f"ss://{user_info}@{spec.server_address}:{spec.server_port}"
            f"#{quote(spec.profile_name, safe='')}"
        )
        return ShadowsocksConnectionInfo(
            server_address=spec.server_address,
            server_port=spec.server_port,
            method=SHADOWSOCKS_METHOD,
            password=spec.password,
            share_uri=share_uri,
        )
