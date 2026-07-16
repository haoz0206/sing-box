import base64
import json

from sb_manager.protocols.vmess_tls import (
    VmessTlsConnectionSpec,
    VmessTlsInboundSpec,
    VmessTlsProtocol,
)
from sb_manager.tls.catalog import TlsClientPolicy


def test_vmess_tls_websocket_produces_modern_inbound_and_share_payload() -> None:
    protocol = VmessTlsProtocol()
    tls = {
        "enabled": True,
        "server_name": "vpn.example.com",
        "certificate_provider": "tls-profile-8",
    }

    inbound = protocol.build_inbound(
        VmessTlsInboundSpec(
            tag="profile-8",
            profile_name="旧客户端兼容",
            listen_port=443,
            user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
            tls=tls,
            transport={"type": "ws", "path": "/vmess"},
        )
    )
    connection = protocol.build_connection_info(
        VmessTlsConnectionSpec(
            profile_name="旧客户端兼容",
            server_address="edge.example.com",
            server_port=443,
            user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
            tls=TlsClientPolicy(server_name="vpn.example.com", insecure=False),
            transport={
                "type": "ws",
                "path": "/vmess",
                "headers": {"Host": "vpn.example.com"},
            },
        )
    )

    assert inbound == {
        "type": "vmess",
        "tag": "profile-8",
        "listen": "::",
        "listen_port": 443,
        "users": [
            {
                "name": "旧客户端兼容",
                "uuid": "bf000d23-0752-40b4-affe-68f7707a9661",
                "alterId": 0,
            }
        ],
        "tls": tls,
        "transport": {"type": "ws", "path": "/vmess"},
    }
    assert connection.share_uri.startswith("vmess://")
    payload = json.loads(base64.b64decode(connection.share_uri.removeprefix("vmess://")))
    assert payload == {
        "v": "2",
        "ps": "旧客户端兼容",
        "add": "edge.example.com",
        "port": "443",
        "id": "bf000d23-0752-40b4-affe-68f7707a9661",
        "aid": "0",
        "scy": "auto",
        "net": "ws",
        "type": "none",
        "host": "vpn.example.com",
        "path": "/vmess",
        "tls": "tls",
        "sni": "vpn.example.com",
    }


def test_vmess_tls_grpc_share_payload_carries_service_name() -> None:
    connection = VmessTlsProtocol().build_connection_info(
        VmessTlsConnectionSpec(
            profile_name="VMess gRPC",
            server_address="vpn.example.com",
            server_port=443,
            user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
            tls=TlsClientPolicy(server_name="vpn.example.com", insecure=False),
            transport={"type": "grpc", "service_name": "VmService"},
        )
    )

    payload = json.loads(base64.b64decode(connection.share_uri.removeprefix("vmess://")))
    assert payload["net"] == "grpc"
    assert payload["path"] == "VmService"
    assert payload["host"] == ""
