from sb_manager.domain.installation import (
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import (
    AnyTlsMaterial,
    Hysteria2Material,
    RealityMaterial,
    ShadowsocksMaterial,
    TrojanMaterial,
    TuicMaterial,
    VlessMaterial,
    VmessMaterial,
)
from sb_manager.protocols.catalog import (
    AnyTlsHandler,
    Hysteria2Handler,
    ProfileConnectionInfo,
    ProtocolCatalog,
    RealityHandler,
    ShadowsocksHandler,
    TrojanHandler,
    TuicHandler,
    VlessTlsHandler,
    VmessTlsHandler,
)
from sb_manager.tls.catalog import AcmeTlsHandler, AcmeTlsIntent, TlsCatalog
from sb_manager.transports.catalog import TransportCatalog, WebSocketTransportIntent


class FixedShadowsocksMaterialSource:
    def generate(self) -> ShadowsocksMaterial:
        return ShadowsocksMaterial(password="8JCsPssfgS8tiRwiMlhARg==")


class FixedRealityMaterialSource:
    def generate(self) -> RealityMaterial:
        return RealityMaterial(
            user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
            private_key="private-key-value",
            public_key="public-key-value",
            short_id="0123456789abcdef",
            server_name="www.cloudflare.com",
        )


class FixedHysteria2MaterialSource:
    def generate(self) -> Hysteria2Material:
        return Hysteria2Material(password="hy2-password")


class FixedTrojanMaterialSource:
    def generate(self) -> TrojanMaterial:
        return TrojanMaterial(password="trojan-password")


class FixedAnyTlsMaterialSource:
    def generate(self) -> AnyTlsMaterial:
        return AnyTlsMaterial(password="anytls-password")


class FixedTuicMaterialSource:
    def generate(self) -> TuicMaterial:
        return TuicMaterial(
            user_uuid="2dd61d93-75d8-4da4-ac0e-6aece7eac365",
            password="tuic-password",
        )


class FixedVlessMaterialSource:
    def generate(self) -> VlessMaterial:
        return VlessMaterial(user_uuid="bf000d23-0752-40b4-affe-68f7707a9661")


class FixedVmessMaterialSource:
    def generate(self) -> VmessMaterial:
        return VmessMaterial(user_uuid="bf000d23-0752-40b4-affe-68f7707a9661")


def test_catalog_materializes_a_complete_shadowsocks_profile() -> None:
    catalog = ProtocolCatalog(
        (ShadowsocksHandler(material_source=FixedShadowsocksMaterialSource()),)
    )
    profile = ManagedProfile(
        profile_id="profile-2",
        profile_name="备用",
        protocol=ProtocolKind.SHADOWSOCKS,
        listen_port=None,
        port_selection=PortSelection.AUTOMATIC,
        status=ProfileStatus.DRAFT,
        server_address="vpn.example.com",
    )

    materialized = catalog.materialize(profile, listen_port=8443)

    assert materialized.profile == ManagedProfile(
        profile_id="profile-2",
        profile_name="备用",
        protocol=ProtocolKind.SHADOWSOCKS,
        listen_port=8443,
        port_selection=PortSelection.AUTOMATIC,
        status=ProfileStatus.APPLIED,
        protocol_material=ShadowsocksMaterial(password="8JCsPssfgS8tiRwiMlhARg=="),
        server_address="vpn.example.com",
    )
    assert materialized.inbound == {
        "type": "shadowsocks",
        "tag": "profile-2",
        "listen": "::",
        "listen_port": 8443,
        "network": "tcp",
        "method": "2022-blake3-aes-128-gcm",
        "password": "8JCsPssfgS8tiRwiMlhARg==",
        "multiplex": {"enabled": True},
    }
    assert materialized.connection_info == ProfileConnectionInfo(
        server_address="vpn.example.com",
        server_port=8443,
        share_uri=(
            "ss://MjAyMi1ibGFrZTMtYWVzLTEyOC1nY206OEpDc1Bzc2ZnUzh0aVJ3aU1saEFSZz09"
            "@vpn.example.com:8443#%E5%A4%87%E7%94%A8"
        ),
    )


def test_catalog_materializes_a_complete_reality_profile() -> None:
    catalog = ProtocolCatalog((RealityHandler(material_source=FixedRealityMaterialSource()),))
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="vpn.example.com",
    )

    materialized = catalog.materialize(profile, listen_port=4433)

    assert isinstance(materialized.profile.protocol_material, RealityMaterial)
    assert materialized.profile.status is ProfileStatus.APPLIED
    assert materialized.inbound["type"] == "vless"
    assert materialized.inbound["tag"] == "profile-1"
    assert materialized.connection_info == ProfileConnectionInfo(
        server_address="vpn.example.com",
        server_port=4433,
        share_uri=(
            "vless://bf000d23-0752-40b4-affe-68f7707a9661@vpn.example.com:4433"
            "?encryption=none&flow=xtls-rprx-vision&security=reality"
            "&sni=www.cloudflare.com&fp=chrome&pbk=public-key-value"
            "&sid=0123456789abcdef&type=tcp#%E6%89%8B%E6%9C%BA"
        ),
    )
    assert "private-key-value" not in materialized.connection_info.share_uri


def test_catalog_materializes_hysteria2_with_inline_acme(tmp_path) -> None:
    handler = Hysteria2Handler(
        material_source=FixedHysteria2MaterialSource(),
        tls_catalog=TlsCatalog((AcmeTlsHandler(),)),
    )
    profile = ManagedProfile(
        profile_id="profile-3",
        profile_name="移动网络",
        protocol=ProtocolKind.HYSTERIA2,
        listen_port=8443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="vpn.example.com",
        tls_intent=AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        ),
    )

    materialized = ProtocolCatalog((handler,)).materialize(profile, listen_port=8443)

    assert materialized.profile.protocol_material == Hysteria2Material(password="hy2-password")
    assert materialized.inbound["type"] == "hysteria2"
    assert materialized.inbound["tls"] == {
        "enabled": True,
        "server_name": "vpn.example.com",
        "acme": {
            "domain": ["vpn.example.com"],
            "email": "operator@example.com",
            "data_directory": str(tmp_path / "acme"),
        },
    }
    assert materialized.certificate_providers == ()
    assert materialized.connection_info is not None
    assert materialized.connection_info.share_uri == (
        "hysteria2://hy2-password@vpn.example.com:8443/"
        "?sni=vpn.example.com&insecure=0#%E7%A7%BB%E5%8A%A8%E7%BD%91%E7%BB%9C"
    )


def test_catalog_materializes_trojan_with_inline_acme(tmp_path) -> None:
    handler = TrojanHandler(
        material_source=FixedTrojanMaterialSource(),
        tls_catalog=TlsCatalog((AcmeTlsHandler(),)),
    )
    profile = ManagedProfile(
        profile_id="profile-4",
        profile_name="兼容网络",
        protocol=ProtocolKind.TROJAN,
        listen_port=443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="vpn.example.com",
        tls_intent=AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        ),
    )

    materialized = ProtocolCatalog((handler,)).materialize(profile, listen_port=443)

    assert materialized.profile.protocol_material == TrojanMaterial(password="trojan-password")
    assert materialized.inbound["type"] == "trojan"
    assert materialized.inbound["tls"]["acme"]["domain"] == ["vpn.example.com"]
    assert materialized.certificate_providers == ()
    assert materialized.connection_info is not None
    assert materialized.connection_info.share_uri == (
        "trojan://trojan-password@vpn.example.com:443/"
        "?sni=vpn.example.com#%E5%85%BC%E5%AE%B9%E7%BD%91%E7%BB%9C"
    )


def test_catalog_materializes_anytls_with_inline_acme(tmp_path) -> None:
    handler = AnyTlsHandler(
        material_source=FixedAnyTlsMaterialSource(),
        tls_catalog=TlsCatalog((AcmeTlsHandler(),)),
    )
    profile = ManagedProfile(
        profile_id="profile-5",
        profile_name="抗干扰",
        protocol=ProtocolKind.ANYTLS,
        listen_port=443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="vpn.example.com",
        tls_intent=AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        ),
    )

    materialized = ProtocolCatalog((handler,)).materialize(profile, listen_port=443)

    assert materialized.profile.protocol_material == AnyTlsMaterial(password="anytls-password")
    assert materialized.inbound["type"] == "anytls"
    assert materialized.inbound["tls"]["acme"]["domain"] == ["vpn.example.com"]
    assert materialized.certificate_providers == ()
    assert materialized.connection_info is not None
    assert materialized.connection_info.share_uri == (
        "anytls://anytls-password@vpn.example.com:443/"
        "?sni=vpn.example.com&insecure=0#%E6%8A%97%E5%B9%B2%E6%89%B0"
    )


def test_catalog_materializes_tuic_with_inline_acme(tmp_path) -> None:
    handler = TuicHandler(
        material_source=FixedTuicMaterialSource(),
        tls_catalog=TlsCatalog((AcmeTlsHandler(),)),
    )
    profile = ManagedProfile(
        profile_id="profile-6",
        profile_name="低延迟",
        protocol=ProtocolKind.TUIC,
        listen_port=443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="vpn.example.com",
        tls_intent=AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        ),
    )

    materialized = ProtocolCatalog((handler,)).materialize(profile, listen_port=443)

    assert materialized.profile.protocol_material == TuicMaterial(
        user_uuid="2dd61d93-75d8-4da4-ac0e-6aece7eac365",
        password="tuic-password",
    )
    assert materialized.inbound["type"] == "tuic"
    assert materialized.inbound["zero_rtt_handshake"] is False
    assert materialized.inbound["tls"]["acme"]["domain"] == ["vpn.example.com"]
    assert materialized.certificate_providers == ()
    assert materialized.connection_info is not None
    assert materialized.connection_info.share_uri.startswith("tuic://")


def test_catalog_materializes_vless_tls_websocket_across_deep_catalogs(tmp_path) -> None:
    handler = VlessTlsHandler(
        material_source=FixedVlessMaterialSource(),
        tls_catalog=TlsCatalog((AcmeTlsHandler(),)),
        transport_catalog=TransportCatalog(),
    )
    profile = ManagedProfile(
        profile_id="profile-7",
        profile_name="CDN 兼容",
        protocol=ProtocolKind.VLESS_TLS,
        listen_port=443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="edge.example.com",
        tls_intent=AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        ),
        transport_intent=WebSocketTransportIntent(
            path="/proxy",
            host="vpn.example.com",
        ),
    )

    materialized = ProtocolCatalog((handler,)).materialize(profile, listen_port=443)

    assert materialized.profile.protocol_material == VlessMaterial(
        user_uuid="bf000d23-0752-40b4-affe-68f7707a9661"
    )
    assert materialized.inbound["transport"] == {"type": "ws", "path": "/proxy"}
    assert materialized.inbound["tls"]["acme"]["domain"] == ["vpn.example.com"]
    assert materialized.certificate_providers == ()
    assert materialized.connection_info is not None
    assert "type=ws" in materialized.connection_info.share_uri


def test_catalog_materializes_vmess_tls_websocket_across_deep_catalogs(tmp_path) -> None:
    handler = VmessTlsHandler(
        material_source=FixedVmessMaterialSource(),
        tls_catalog=TlsCatalog((AcmeTlsHandler(),)),
        transport_catalog=TransportCatalog(),
    )
    profile = ManagedProfile(
        profile_id="profile-8",
        profile_name="旧客户端兼容",
        protocol=ProtocolKind.VMESS_TLS,
        listen_port=443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="edge.example.com",
        tls_intent=AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        ),
        transport_intent=WebSocketTransportIntent(path="/vmess", host="vpn.example.com"),
    )

    materialized = ProtocolCatalog((handler,)).materialize(profile, listen_port=443)

    assert materialized.profile.protocol_material == VmessMaterial(
        user_uuid="bf000d23-0752-40b4-affe-68f7707a9661"
    )
    assert materialized.inbound["users"][0]["alterId"] == 0
    assert materialized.inbound["transport"] == {"type": "ws", "path": "/vmess"}
    assert materialized.connection_info is not None
    assert materialized.connection_info.share_uri.startswith("vmess://")
