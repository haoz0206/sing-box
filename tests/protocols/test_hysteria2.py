from sb_manager.protocols.hysteria2 import (
    Hysteria2ConnectionInfo,
    Hysteria2ConnectionSpec,
    Hysteria2InboundSpec,
    Hysteria2Protocol,
)
from sb_manager.tls.catalog import TlsClientPolicy


def test_hysteria2_produces_a_known_good_inbound() -> None:
    spec = Hysteria2InboundSpec(
        tag="profile-3",
        profile_name="移动网络",
        listen_port=8443,
        password="hy2-password",
        tls={
            "enabled": True,
            "server_name": "vpn.example.com",
            "certificate_provider": "tls-profile-3",
        },
    )

    assert Hysteria2Protocol().build_inbound(spec) == {
        "type": "hysteria2",
        "tag": "profile-3",
        "listen": "::",
        "listen_port": 8443,
        "users": [{"name": "移动网络", "password": "hy2-password"}],
        "ignore_client_bandwidth": True,
        "tls": {
            "enabled": True,
            "server_name": "vpn.example.com",
            "certificate_provider": "tls-profile-3",
        },
    }


def test_hysteria2_produces_known_good_strict_tls_connection_information() -> None:
    spec = Hysteria2ConnectionSpec(
        profile_name="移动网络",
        server_address="vpn.example.com",
        server_port=8443,
        password="hy2-password",
        tls=TlsClientPolicy(server_name="vpn.example.com", insecure=False),
    )

    assert Hysteria2Protocol().build_connection_info(spec) == Hysteria2ConnectionInfo(
        server_address="vpn.example.com",
        server_port=8443,
        password="hy2-password",
        server_name="vpn.example.com",
        insecure=False,
        share_uri=(
            "hysteria2://hy2-password@vpn.example.com:8443/"
            "?sni=vpn.example.com&insecure=0#%E7%A7%BB%E5%8A%A8%E7%BD%91%E7%BB%9C"
        ),
    )
