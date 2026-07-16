from sb_manager.protocols.trojan import (
    TrojanConnectionInfo,
    TrojanConnectionSpec,
    TrojanInboundSpec,
    TrojanProtocol,
)
from sb_manager.tls.catalog import TlsClientPolicy


def test_trojan_produces_known_good_tls_inbound_and_share_uri() -> None:
    protocol = TrojanProtocol()
    tls = {
        "enabled": True,
        "server_name": "vpn.example.com",
        "certificate_provider": "tls-profile-4",
    }

    inbound = protocol.build_inbound(
        TrojanInboundSpec(
            tag="profile-4",
            profile_name="兼容网络",
            listen_port=443,
            password="trojan-password",
            tls=tls,
        )
    )
    connection = protocol.build_connection_info(
        TrojanConnectionSpec(
            profile_name="兼容网络",
            server_address="vpn.example.com",
            server_port=443,
            password="trojan-password",
            tls=TlsClientPolicy(server_name="vpn.example.com", insecure=False),
        )
    )

    assert inbound == {
        "type": "trojan",
        "tag": "profile-4",
        "listen": "::",
        "listen_port": 443,
        "users": [{"name": "兼容网络", "password": "trojan-password"}],
        "tls": tls,
    }
    assert connection == TrojanConnectionInfo(
        server_address="vpn.example.com",
        server_port=443,
        password="trojan-password",
        server_name="vpn.example.com",
        share_uri=(
            "trojan://trojan-password@vpn.example.com:443/"
            "?sni=vpn.example.com#%E5%85%BC%E5%AE%B9%E7%BD%91%E7%BB%9C"
        ),
    )
