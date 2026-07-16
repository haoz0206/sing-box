from sb_manager.protocols.anytls import (
    AnyTlsConnectionInfo,
    AnyTlsConnectionSpec,
    AnyTlsInboundSpec,
    AnyTlsProtocol,
)
from sb_manager.tls.catalog import TlsClientPolicy


def test_anytls_produces_known_good_tls_inbound_and_share_uri() -> None:
    protocol = AnyTlsProtocol()
    tls = {
        "enabled": True,
        "server_name": "vpn.example.com",
        "certificate_provider": "tls-profile-5",
    }

    inbound = protocol.build_inbound(
        AnyTlsInboundSpec(
            tag="profile-5",
            profile_name="抗干扰",
            listen_port=443,
            password="anytls-password",
            tls=tls,
        )
    )
    connection = protocol.build_connection_info(
        AnyTlsConnectionSpec(
            profile_name="抗干扰",
            server_address="vpn.example.com",
            server_port=443,
            password="anytls-password",
            tls=TlsClientPolicy(server_name="vpn.example.com", insecure=False),
        )
    )

    assert inbound == {
        "type": "anytls",
        "tag": "profile-5",
        "listen": "::",
        "listen_port": 443,
        "users": [{"name": "抗干扰", "password": "anytls-password"}],
        "tls": tls,
    }
    assert connection == AnyTlsConnectionInfo(
        server_address="vpn.example.com",
        server_port=443,
        password="anytls-password",
        server_name="vpn.example.com",
        share_uri=(
            "anytls://anytls-password@vpn.example.com:443/"
            "?sni=vpn.example.com&insecure=0#%E6%8A%97%E5%B9%B2%E6%89%B0"
        ),
    )
