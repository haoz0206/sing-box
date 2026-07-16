from sb_manager.protocols.vless_tls import (
    VlessTlsConnectionInfo,
    VlessTlsConnectionSpec,
    VlessTlsInboundSpec,
    VlessTlsProtocol,
)
from sb_manager.tls.catalog import TlsClientPolicy


def test_vless_tls_websocket_produces_known_good_inbound_and_share_uri() -> None:
    protocol = VlessTlsProtocol()
    server_tls = {
        "enabled": True,
        "server_name": "vpn.example.com",
        "certificate_provider": "tls-profile-7",
    }

    inbound = protocol.build_inbound(
        VlessTlsInboundSpec(
            tag="profile-7",
            profile_name="CDN 兼容",
            listen_port=443,
            user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
            tls=server_tls,
            transport={"type": "ws", "path": "/proxy"},
        )
    )
    connection = protocol.build_connection_info(
        VlessTlsConnectionSpec(
            profile_name="CDN 兼容",
            server_address="edge.example.com",
            server_port=443,
            user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
            tls=TlsClientPolicy(server_name="vpn.example.com", insecure=False),
            transport={
                "type": "ws",
                "path": "/proxy",
                "headers": {"Host": "vpn.example.com"},
            },
        )
    )

    assert inbound == {
        "type": "vless",
        "tag": "profile-7",
        "listen": "::",
        "listen_port": 443,
        "users": [
            {
                "name": "CDN 兼容",
                "uuid": "bf000d23-0752-40b4-affe-68f7707a9661",
            }
        ],
        "tls": server_tls,
        "transport": {"type": "ws", "path": "/proxy"},
    }
    assert connection == VlessTlsConnectionInfo(
        server_address="edge.example.com",
        server_port=443,
        user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
        server_name="vpn.example.com",
        share_uri=(
            "vless://bf000d23-0752-40b4-affe-68f7707a9661@edge.example.com:443"
            "?encryption=none&security=tls&sni=vpn.example.com&type=ws"
            "&host=vpn.example.com&path=%2Fproxy#CDN%20%E5%85%BC%E5%AE%B9"
        ),
    )
