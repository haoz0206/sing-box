import json
from pathlib import Path
from typing import cast

import pytest

from sb_manager.adapters.json_file_state import (
    InvalidProfileMaterialError,
    JsonFileStateStore,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import (
    AnyTlsMaterial,
    Hysteria2Material,
    ProtocolMaterial,
    ShadowsocksMaterial,
    SnellV6Material,
    TrojanMaterial,
    TuicMaterial,
    VlessMaterial,
    VmessMaterial,
)
from sb_manager.protocols.reality import RealityMaterial
from sb_manager.seams.state_store import UnsupportedStateSchemaError
from sb_manager.tls.catalog import AcmeTlsIntent
from sb_manager.transports.catalog import WebSocketTransportIntent


def test_json_state_store_survives_reopen(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    expected = ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(
            ManagedProfile(
                profile_id="profile-1",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=RealityMaterial(
                    user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
                    private_key="private-key-value",
                    public_key="public-key-value",
                    short_id="0123456789abcdef",
                    server_name="www.cloudflare.com",
                ),
            ),
        ),
        expected_config_sha256="f" * 64,
    )

    JsonFileStateStore(state_path).save(expected)

    assert JsonFileStateStore(state_path).load() == expected


def test_json_state_store_persists_paused_applied_profile(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    paused = ManagedProfile(
        profile_id="profile-1",
        profile_name="暂停中的配置",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
    )
    expected = ManagedInstallation(
        schema_version=1,
        revision=3,
        profiles=(paused,),
        expected_config_sha256="a" * 64,
    )

    JsonFileStateStore(state_path).save(expected)

    assert JsonFileStateStore(state_path).load() == expected


def test_json_state_store_rejects_an_unsupported_schema(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        '{"schema_version": 2, "revision": 7, "profiles": []}',
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedStateSchemaError) as caught:
        JsonFileStateStore(state_path).load()

    assert (caught.value.supported, caught.value.found) == (1, 2)


def test_json_state_store_keeps_the_previous_revision_as_a_backup(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    store = JsonFileStateStore(state_path)
    previous = ManagedInstallation(schema_version=1, revision=1, profiles=())
    current = ManagedInstallation(schema_version=1, revision=2, profiles=())

    store.save(previous)
    store.save(current)

    assert JsonFileStateStore(store.backup_path).load() == previous
    assert store.load() == current


def test_json_state_store_round_trips_tagged_shadowsocks_material(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    expected = ManagedInstallation(
        schema_version=1,
        revision=2,
        profiles=(
            ManagedProfile(
                profile_id="profile-2",
                profile_name="备用",
                protocol=ProtocolKind.SHADOWSOCKS,
                listen_port=8443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=ShadowsocksMaterial(password="8JCsPssfgS8tiRwiMlhARg=="),
                server_address="vpn.example.com",
            ),
        ),
    )

    JsonFileStateStore(state_path).save(expected)

    assert JsonFileStateStore(state_path).load() == expected


def test_json_state_store_round_trips_tagged_snell_v6_material(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    material = SnellV6Material(psk="AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8")
    expected = ManagedInstallation(
        schema_version=1,
        revision=2,
        profiles=(
            ManagedProfile(
                profile_id="profile-7",
                profile_name="Snell preview",
                protocol=ProtocolKind.SNELL_V6,
                listen_port=18443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=material,
                server_address="proxy.example.com",
            ),
        ),
    )

    JsonFileStateStore(state_path).save(expected)

    assert JsonFileStateStore(state_path).load() == expected
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["profiles"][0]["protocol_material"] == {
        "kind": "snell-v6",
        "psk": material.psk,
    }


@pytest.mark.parametrize(
    ("protocol", "material"),
    [
        pytest.param(ProtocolKind.SNELL_V6, None, id="snell-missing"),
        pytest.param(
            ProtocolKind.SNELL_V6,
            ShadowsocksMaterial(password="wrong-protocol-material"),
            id="snell-with-shadowsocks-material",
        ),
        pytest.param(
            ProtocolKind.SHADOWSOCKS,
            SnellV6Material(psk="AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"),
            id="shadowsocks-with-snell-material",
        ),
    ],
)
def test_json_state_store_rejects_invalid_protocol_material_before_save(
    tmp_path: Path,
    protocol: ProtocolKind,
    material: ProtocolMaterial | None,
) -> None:
    state_path = tmp_path / "state.json"
    installation = ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(
            ManagedProfile(
                profile_id="profile-7",
                profile_name="Snell preview",
                protocol=protocol,
                listen_port=18443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.DRAFT,
                protocol_material=material,
            ),
        ),
    )

    with pytest.raises(InvalidProfileMaterialError, match="profile-7"):
        JsonFileStateStore(state_path).save(installation)

    assert not state_path.exists()


@pytest.mark.parametrize(
    ("protocol", "material_data"),
    [
        pytest.param("snell-v6", None, id="snell-missing"),
        pytest.param(
            "snell-v6",
            {"kind": "shadowsocks-2022", "password": "wrong-protocol-material"},
            id="snell-with-shadowsocks-material",
        ),
        pytest.param(
            "shadowsocks-2022",
            {"kind": "snell-v6", "psk": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"},
            id="shadowsocks-with-snell-material",
        ),
    ],
)
def test_json_state_store_rejects_invalid_protocol_material_while_loading(
    protocol: str,
    material_data: object,
) -> None:
    payload = {
        "schema_version": 1,
        "revision": 1,
        "profiles": [
            {
                "profile_id": "profile-7",
                "profile_name": "Snell preview",
                "protocol": protocol,
                "listen_port": 18443,
                "port_selection": "fixed",
                "status": "draft",
                "enabled": True,
                "reality_material": None,
                "protocol_material": material_data,
                "server_address": "proxy.example.com",
                "tls_intent": None,
                "transport_intent": None,
            }
        ],
        "expected_config_sha256": None,
    }

    with pytest.raises(InvalidProfileMaterialError, match="profile-7"):
        JsonFileStateStore.load_payload(json.dumps(payload).encode())


def test_json_state_store_rejects_malformed_tagged_snell_v6_material() -> None:
    payload = {
        "schema_version": 1,
        "revision": 2,
        "profiles": [
            {
                "profile_id": "profile-7",
                "profile_name": "Snell preview",
                "protocol": "snell-v6",
                "listen_port": 18443,
                "port_selection": "fixed",
                "status": "applied",
                "enabled": True,
                "reality_material": None,
                "protocol_material": {"kind": "snell-v6", "psk": "too-short"},
                "server_address": "proxy.example.com",
                "tls_intent": None,
                "transport_intent": None,
            }
        ],
        "expected_config_sha256": None,
    }

    with pytest.raises(
        ValueError,
        match="Managed Snell v6 PSK must be 43 URL-safe characters",
    ):
        JsonFileStateStore.load_payload(json.dumps(payload).encode())


def test_json_state_store_migrates_legacy_reality_material(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        """{
  "schema_version": 1,
  "revision": 2,
  "profiles": [
    {
      "profile_id": "profile-1",
      "profile_name": "手机",
      "protocol": "vless-reality",
      "listen_port": 4433,
      "port_selection": "fixed",
      "status": "applied",
      "server_address": "vpn.example.com",
      "reality_material": {
        "user_uuid": "bf000d23-0752-40b4-affe-68f7707a9661",
        "private_key": "private-key-value",
        "public_key": "public-key-value",
        "short_id": "0123456789abcdef",
        "server_name": "www.cloudflare.com"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )

    profile = JsonFileStateStore(state_path).load().profiles[0]

    assert profile.enabled is True
    assert profile.protocol_material == RealityMaterial(
        user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
        private_key="private-key-value",
        public_key="public-key-value",
        short_id="0123456789abcdef",
        server_name="www.cloudflare.com",
    )


def test_json_state_store_refuses_unregistered_protocol_material(tmp_path: Path) -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="未知协议",
        protocol=ProtocolKind.SHADOWSOCKS,
        listen_port=8443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        protocol_material=cast(ProtocolMaterial, object()),
    )

    with pytest.raises(TypeError, match="Unregistered protocol material"):
        JsonFileStateStore(tmp_path / "state.json").save(
            ManagedInstallation(schema_version=1, revision=2, profiles=(profile,))
        )


def test_json_state_store_round_trips_hysteria2_material_and_acme_intent(
    tmp_path: Path,
) -> None:
    expected = ManagedInstallation(
        schema_version=1,
        revision=3,
        profiles=(
            ManagedProfile(
                profile_id="profile-3",
                profile_name="移动网络",
                protocol=ProtocolKind.HYSTERIA2,
                listen_port=8443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=Hysteria2Material(password="hy2-password"),
                server_address="vpn.example.com",
                tls_intent=AcmeTlsIntent(
                    server_name="vpn.example.com",
                    email="operator@example.com",
                    data_directory=tmp_path / "acme",
                ),
            ),
        ),
    )
    state_path = tmp_path / "state.json"

    JsonFileStateStore(state_path).save(expected)

    assert JsonFileStateStore(state_path).load() == expected


def test_json_state_store_round_trips_trojan_material_and_tls_intent(tmp_path: Path) -> None:
    expected = ManagedInstallation(
        schema_version=1,
        revision=4,
        profiles=(
            ManagedProfile(
                profile_id="profile-4",
                profile_name="兼容网络",
                protocol=ProtocolKind.TROJAN,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=TrojanMaterial(password="trojan-password"),
                server_address="vpn.example.com",
                tls_intent=AcmeTlsIntent(
                    server_name="vpn.example.com",
                    email="operator@example.com",
                    data_directory=tmp_path / "acme",
                ),
            ),
        ),
    )
    state_path = tmp_path / "state.json"

    JsonFileStateStore(state_path).save(expected)

    assert JsonFileStateStore(state_path).load() == expected


def test_json_state_store_round_trips_anytls_material_and_tls_intent(tmp_path: Path) -> None:
    expected = ManagedInstallation(
        schema_version=1,
        revision=5,
        profiles=(
            ManagedProfile(
                profile_id="profile-5",
                profile_name="抗干扰",
                protocol=ProtocolKind.ANYTLS,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=AnyTlsMaterial(password="anytls-password"),
                server_address="vpn.example.com",
                tls_intent=AcmeTlsIntent(
                    server_name="vpn.example.com",
                    email="operator@example.com",
                    data_directory=tmp_path / "acme",
                ),
            ),
        ),
    )
    state_path = tmp_path / "state.json"

    JsonFileStateStore(state_path).save(expected)

    assert JsonFileStateStore(state_path).load() == expected


def test_json_state_store_round_trips_tuic_material_and_tls_intent(tmp_path: Path) -> None:
    expected = ManagedInstallation(
        schema_version=1,
        revision=6,
        profiles=(
            ManagedProfile(
                profile_id="profile-6",
                profile_name="低延迟",
                protocol=ProtocolKind.TUIC,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=TuicMaterial(
                    user_uuid="2dd61d93-75d8-4da4-ac0e-6aece7eac365",
                    password="tuic-password",
                ),
                server_address="vpn.example.com",
                tls_intent=AcmeTlsIntent(
                    server_name="vpn.example.com",
                    email="operator@example.com",
                    data_directory=tmp_path / "acme",
                ),
            ),
        ),
    )
    state_path = tmp_path / "state.json"

    JsonFileStateStore(state_path).save(expected)

    assert JsonFileStateStore(state_path).load() == expected


def test_json_state_store_round_trips_vless_tls_and_websocket_intents(tmp_path: Path) -> None:
    expected = ManagedInstallation(
        schema_version=1,
        revision=7,
        profiles=(
            ManagedProfile(
                profile_id="profile-7",
                profile_name="CDN 兼容",
                protocol=ProtocolKind.VLESS_TLS,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=VlessMaterial(user_uuid="bf000d23-0752-40b4-affe-68f7707a9661"),
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
            ),
        ),
    )
    state_path = tmp_path / "state.json"

    JsonFileStateStore(state_path).save(expected)

    assert JsonFileStateStore(state_path).load() == expected


def test_json_state_store_round_trips_vmess_tls_and_websocket_intents(tmp_path: Path) -> None:
    expected = ManagedInstallation(
        schema_version=1,
        revision=8,
        profiles=(
            ManagedProfile(
                profile_id="profile-8",
                profile_name="旧客户端兼容",
                protocol=ProtocolKind.VMESS_TLS,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=VmessMaterial(user_uuid="bf000d23-0752-40b4-affe-68f7707a9661"),
                server_address="edge.example.com",
                tls_intent=AcmeTlsIntent(
                    server_name="vpn.example.com",
                    email="operator@example.com",
                    data_directory=tmp_path / "acme",
                ),
                transport_intent=WebSocketTransportIntent(
                    path="/vmess",
                    host="vpn.example.com",
                ),
            ),
        ),
    )
    state_path = tmp_path / "state.json"

    JsonFileStateStore(state_path).save(expected)

    assert JsonFileStateStore(state_path).load() == expected
