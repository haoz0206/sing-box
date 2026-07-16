from sb_manager.protocols.reality import (
    RealityConnectionInfo,
    RealityConnectionSpec,
    RealityInboundSpec,
    RealityProtocol,
)


def test_reality_protocol_produces_a_known_good_vless_inbound() -> None:
    spec = RealityInboundSpec(
        tag="profile-phone",
        profile_name="手机",
        listen_port=4433,
        user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
        server_name="www.cloudflare.com",
        private_key="UuMBgl7MXTPx9inmQp2UC7Jcnwc6XYbwDNebonM-FCc",
        short_id="0123456789abcdef",
    )

    assert RealityProtocol().build_inbound(spec) == {
        "type": "vless",
        "tag": "profile-phone",
        "listen": "::",
        "listen_port": 4433,
        "users": [
            {
                "name": "手机",
                "uuid": "bf000d23-0752-40b4-affe-68f7707a9661",
                "flow": "xtls-rprx-vision",
            }
        ],
        "tls": {
            "enabled": True,
            "server_name": "www.cloudflare.com",
            "reality": {
                "enabled": True,
                "handshake": {
                    "server": "www.cloudflare.com",
                    "server_port": 443,
                },
                "private_key": "UuMBgl7MXTPx9inmQp2UC7Jcnwc6XYbwDNebonM-FCc",
                "short_id": ["0123456789abcdef"],
            },
        },
    }


def test_reality_protocol_produces_known_good_connection_information() -> None:
    spec = RealityConnectionSpec(
        profile_name="手机",
        server_address="vpn.example.com",
        server_port=4433,
        user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
        server_name="www.cloudflare.com",
        public_key="public-key-value",
        short_id="0123456789abcdef",
    )

    assert RealityProtocol().build_connection_info(spec) == RealityConnectionInfo(
        server_address="vpn.example.com",
        server_port=4433,
        user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
        server_name="www.cloudflare.com",
        public_key="public-key-value",
        short_id="0123456789abcdef",
        flow="xtls-rprx-vision",
        share_uri=(
            "vless://bf000d23-0752-40b4-affe-68f7707a9661@vpn.example.com:4433"
            "?encryption=none&flow=xtls-rprx-vision&security=reality"
            "&sni=www.cloudflare.com&fp=chrome&pbk=public-key-value"
            "&sid=0123456789abcdef&type=tcp#%E6%89%8B%E6%9C%BA"
        ),
    )
