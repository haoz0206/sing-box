from pathlib import Path
from typing import cast

import pytest

from sb_manager.adapters.json_file_state import JsonFileStateStore
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
    TrojanMaterial,
    TuicMaterial,
)
from sb_manager.protocols.reality import RealityMaterial
from sb_manager.seams.state_store import UnsupportedStateSchemaError
from sb_manager.tls.catalog import AcmeTlsIntent


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
