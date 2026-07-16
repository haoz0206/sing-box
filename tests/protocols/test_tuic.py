from sb_manager.protocols.tuic import (
    TuicConnectionInfo,
    TuicConnectionSpec,
    TuicInboundSpec,
    TuicProtocol,
)
from sb_manager.tls.catalog import TlsClientPolicy


def test_tuic_produces_known_good_secure_inbound_and_connection_info() -> None:
    protocol = TuicProtocol()
    tls = {
        "enabled": True,
        "server_name": "vpn.example.com",
        "certificate_provider": "tls-profile-6",
    }

    inbound = protocol.build_inbound(
        TuicInboundSpec(
            tag="profile-6",
            profile_name="低延迟",
            listen_port=443,
            user_uuid="2dd61d93-75d8-4da4-ac0e-6aece7eac365",
            password="tuic-password",
            tls=tls,
        )
    )
    connection = protocol.build_connection_info(
        TuicConnectionSpec(
            profile_name="低延迟",
            server_address="vpn.example.com",
            server_port=443,
            user_uuid="2dd61d93-75d8-4da4-ac0e-6aece7eac365",
            password="tuic-password",
            tls=TlsClientPolicy(server_name="vpn.example.com", insecure=False),
        )
    )

    assert inbound == {
        "type": "tuic",
        "tag": "profile-6",
        "listen": "::",
        "listen_port": 443,
        "users": [
            {
                "name": "低延迟",
                "uuid": "2dd61d93-75d8-4da4-ac0e-6aece7eac365",
                "password": "tuic-password",
            }
        ],
        "congestion_control": "cubic",
        "zero_rtt_handshake": False,
        "tls": tls,
    }
    assert connection == TuicConnectionInfo(
        server_address="vpn.example.com",
        server_port=443,
        user_uuid="2dd61d93-75d8-4da4-ac0e-6aece7eac365",
        password="tuic-password",
        server_name="vpn.example.com",
        share_uri=(
            "tuic://2dd61d93-75d8-4da4-ac0e-6aece7eac365:tuic-password"
            "@vpn.example.com:443/?congestion_control=cubic&udp_relay_mode=native"
            "&sni=vpn.example.com&allow_insecure=0#%E4%BD%8E%E5%BB%B6%E8%BF%9F"
        ),
    )
