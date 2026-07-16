from sb_manager.protocols.shadowsocks import (
    ShadowsocksConnectionInfo,
    ShadowsocksConnectionSpec,
    ShadowsocksInboundSpec,
    ShadowsocksProtocol,
)


def test_shadowsocks_2022_produces_a_known_good_inbound() -> None:
    spec = ShadowsocksInboundSpec(
        tag="profile-2",
        listen_port=8443,
        password="8JCsPssfgS8tiRwiMlhARg==",
    )

    assert ShadowsocksProtocol().build_inbound(spec) == {
        "type": "shadowsocks",
        "tag": "profile-2",
        "listen": "::",
        "listen_port": 8443,
        "network": "tcp",
        "method": "2022-blake3-aes-128-gcm",
        "password": "8JCsPssfgS8tiRwiMlhARg==",
        "multiplex": {"enabled": True},
    }


def test_shadowsocks_2022_produces_known_good_connection_information() -> None:
    spec = ShadowsocksConnectionSpec(
        profile_name="备用",
        server_address="vpn.example.com",
        server_port=8443,
        password="8JCsPssfgS8tiRwiMlhARg==",
    )

    assert ShadowsocksProtocol().build_connection_info(spec) == ShadowsocksConnectionInfo(
        server_address="vpn.example.com",
        server_port=8443,
        method="2022-blake3-aes-128-gcm",
        password="8JCsPssfgS8tiRwiMlhARg==",
        share_uri=(
            "ss://MjAyMi1ibGFrZTMtYWVzLTEyOC1nY206OEpDc1Bzc2ZnUzh0aVJ3aU1saEFSZz09"
            "@vpn.example.com:8443#%E5%A4%87%E7%94%A8"
        ),
    )
