import json
from pathlib import Path

from sb_manager.adapters.json_file_state import JsonFileStateStore
from sb_manager.adapters.socket_ports import SocketPortSource
from sb_manager.application.manager import (
    AcmeTlsRequest,
    PlanProfileRequest,
    WebSocketTransportRequest,
)
from sb_manager.application.profile_apply import ApplyProfileRequest
from sb_manager.cli import create_app
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import (
    AnyTlsMaterial,
    ShadowsocksMaterial,
    TrojanMaterial,
    TuicMaterial,
    VlessMaterial,
    VmessMaterial,
)
from sb_manager.tls.catalog import AcmeTlsIntent
from sb_manager.ui.app import ManagerApp

EXPECTED_APPLIED_REVISION = 2


def _write_fake_sing_box(tmp_path: Path) -> Path:
    binary = tmp_path / "sing-box"
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if sys.argv[1:3] == ['generate', 'reality-keypair']:\n"
        "    print('PrivateKey: private-key-value')\n"
        "    print('PublicKey: public-key-value')\n"
        "elif sys.argv[1] == 'check':\n"
        "    print('configuration is valid')\n"
        "else:\n"
        "    raise SystemExit(2)\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def _write_fake_systemctl(tmp_path: Path) -> Path:
    binary = tmp_path / "systemctl"
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('active' if sys.argv[1] == 'is-active' else 'reloaded')\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def _write_fake_privilege_runner(tmp_path: Path) -> Path:
    runner = tmp_path / "privilege-runner"
    runner.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "import sys\n"
        "if sys.argv[1] != '-n':\n"
        "    raise SystemExit(2)\n"
        "os.execv(sys.argv[2], sys.argv[2:])\n",
        encoding="utf-8",
    )
    runner.chmod(0o755)
    return runner


def _write_fake_privileged_helper(
    tmp_path: Path,
    incoming_directory: Path,
) -> tuple[Path, Path]:
    helper = tmp_path / "privileged-helper"
    log_path = tmp_path / "privileged-document.json"
    response = {
        "schema_version": 1,
        "status": "applied",
        "transaction": {
            "outcome": "applied",
            "validation": {"valid": True, "diagnostics": "configuration valid"},
            "commit": {"success": True, "diagnostics": "configuration committed"},
            "runtime_refresh": {"success": True, "diagnostics": "service refreshed"},
            "postcondition": {"healthy": True, "diagnostics": "service active"},
            "rollback": None,
        },
    }
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "request = json.load(sys.stdin)\n"
        f"incoming = Path({str(incoming_directory)!r})\n"
        "config = incoming / f\"config-{request['sha256']}.json\"\n"
        f"Path({str(log_path)!r}).write_text(config.read_text(), encoding='utf-8')\n"
        f"print({json.dumps(response)!r})\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)
    return helper, log_path


def _create_isolated_app(tmp_path: Path) -> tuple[ManagerApp, Path, Path]:
    state_path = tmp_path / "state/state.json"
    config_path = tmp_path / "etc/sing-box/config.json"
    app = create_app(
        [
            "--state-file",
            str(state_path),
            "--config-file",
            str(config_path),
            "--staging-dir",
            str(tmp_path / "staging"),
            "--sing-box-binary",
            str(_write_fake_sing_box(tmp_path)),
            "--runtime",
            "systemd",
            "--runtime-binary",
            str(_write_fake_systemctl(tmp_path)),
        ]
    )
    return app, state_path, config_path


def test_cli_composes_the_tui_with_a_persistent_state_store(tmp_path: Path) -> None:
    state_path = tmp_path / "manager" / "state.json"
    app = create_app(["--state-file", str(state_path)])
    plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=4433,
        )
    )

    app.manager.save_profile_draft(plan)

    assert JsonFileStateStore(state_path).load().profiles[0].profile_name == "手机"


def test_cli_composes_a_complete_isolated_apply_path(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    listen_port = SocketPortSource().choose_available()
    plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=listen_port,
        )
    )
    app.manager.save_profile_draft(plan)

    assert app.profile_applier is not None
    result = app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert result.committed_revision == EXPECTED_APPLIED_REVISION
    installation = JsonFileStateStore(state_path).load()
    assert installation.revision == EXPECTED_APPLIED_REVISION
    assert installation.profiles[0].status is ProfileStatus.APPLIED
    assert installation.profiles[0].protocol_material is not None
    assert json.loads(config_path.read_text(encoding="utf-8"))["inbounds"][0]["tag"] == "profile-1"


def test_cli_routes_privileged_apply_through_helper_without_direct_host_write(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state/state.json"
    direct_config_path = tmp_path / "must-not-write/config.json"
    incoming_directory = tmp_path / "incoming"
    helper, helper_log = _write_fake_privileged_helper(tmp_path, incoming_directory)
    app = create_app(
        [
            "--state-file",
            str(state_path),
            "--config-file",
            str(direct_config_path),
            "--apply-mode",
            "privileged",
            "--privilege-runner",
            str(_write_fake_privilege_runner(tmp_path)),
            "--privileged-helper-binary",
            str(helper),
            "--privileged-incoming-dir",
            str(incoming_directory),
        ]
    )
    listen_port = SocketPortSource().choose_available()
    plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="受限应用",
            protocol=ProtocolKind.SHADOWSOCKS,
            listen_port=listen_port,
        )
    )
    app.manager.save_profile_draft(plan)

    assert app.profile_applier is not None
    result = app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert result.committed_revision == EXPECTED_APPLIED_REVISION
    assert not direct_config_path.exists()
    helper_document = json.loads(helper_log.read_text(encoding="utf-8"))
    assert helper_document["inbounds"][0]["type"] == "shadowsocks"


def test_cli_composes_a_complete_shadowsocks_apply_path(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    listen_port = SocketPortSource().choose_available()
    plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="备用",
            protocol=ProtocolKind.SHADOWSOCKS,
            listen_port=listen_port,
            server_address="vpn.example.com",
        )
    )
    app.manager.save_profile_draft(plan)

    assert app.profile_applier is not None
    result = app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert result.committed_revision == EXPECTED_APPLIED_REVISION
    assert result.connection_info is not None
    assert result.connection_info.share_uri.startswith("ss://")
    profile = JsonFileStateStore(state_path).load().profiles[0]
    assert isinstance(profile.protocol_material, ShadowsocksMaterial)
    inbound = json.loads(config_path.read_text(encoding="utf-8"))["inbounds"][0]
    assert inbound["type"] == "shadowsocks"
    assert inbound["password"] == profile.protocol_material.password


def test_cli_composes_a_complete_hysteria2_acme_apply_path(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    listen_port = SocketPortSource().choose_available()
    store = JsonFileStateStore(state_path)
    initial = store.load()
    store.save(
        ManagedInstallation(
            schema_version=initial.schema_version,
            revision=1,
            profiles=(
                ManagedProfile(
                    profile_id="profile-1",
                    profile_name="高速",
                    protocol=ProtocolKind.HYSTERIA2,
                    listen_port=listen_port,
                    port_selection=PortSelection.FIXED,
                    status=ProfileStatus.DRAFT,
                    server_address="vpn.example.com",
                    tls_intent=AcmeTlsIntent(
                        server_name="vpn.example.com",
                        email="operator@example.com",
                        data_directory=tmp_path / "acme",
                    ),
                ),
            ),
        )
    )

    assert app.profile_applier is not None
    result = app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert result.committed_revision == EXPECTED_APPLIED_REVISION
    assert result.connection_info is not None
    assert result.connection_info.share_uri.startswith("hysteria2://")
    document = json.loads(config_path.read_text(encoding="utf-8"))
    assert document["inbounds"][0]["type"] == "hysteria2"
    assert document["certificate_providers"] == [
        {
            "type": "acme",
            "tag": "tls-profile-1",
            "domain": ["vpn.example.com"],
            "email": "operator@example.com",
            "data_directory": str(tmp_path / "acme"),
            "key_type": "p256",
        }
    ]


def test_cli_composes_a_complete_trojan_acme_apply_path(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    listen_port = SocketPortSource().choose_available()
    plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="兼容网络",
            protocol=ProtocolKind.TROJAN,
            listen_port=listen_port,
            server_address="vpn.example.com",
            tls=AcmeTlsRequest(
                server_name="vpn.example.com",
                email="operator@example.com",
            ),
        )
    )
    app.manager.save_profile_draft(plan)

    assert app.profile_applier is not None
    result = app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert result.committed_revision == EXPECTED_APPLIED_REVISION
    assert result.connection_info is not None
    assert result.connection_info.share_uri.startswith("trojan://")
    profile = JsonFileStateStore(state_path).load().profiles[0]
    assert isinstance(profile.protocol_material, TrojanMaterial)
    document = json.loads(config_path.read_text(encoding="utf-8"))
    assert document["inbounds"][0]["type"] == "trojan"
    assert document["certificate_providers"][0]["tag"] == "tls-profile-1"


def test_cli_composes_a_complete_anytls_acme_apply_path(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    listen_port = SocketPortSource().choose_available()
    plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="抗干扰",
            protocol=ProtocolKind.ANYTLS,
            listen_port=listen_port,
            server_address="vpn.example.com",
            tls=AcmeTlsRequest(
                server_name="vpn.example.com",
                email="operator@example.com",
            ),
        )
    )
    app.manager.save_profile_draft(plan)

    assert app.profile_applier is not None
    result = app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert result.committed_revision == EXPECTED_APPLIED_REVISION
    assert result.connection_info is not None
    assert result.connection_info.share_uri.startswith("anytls://")
    profile = JsonFileStateStore(state_path).load().profiles[0]
    assert isinstance(profile.protocol_material, AnyTlsMaterial)
    document = json.loads(config_path.read_text(encoding="utf-8"))
    assert document["inbounds"][0]["type"] == "anytls"
    assert document["certificate_providers"][0]["tag"] == "tls-profile-1"


def test_cli_composes_a_complete_tuic_acme_apply_path(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    listen_port = SocketPortSource().choose_available()
    plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="低延迟",
            protocol=ProtocolKind.TUIC,
            listen_port=listen_port,
            server_address="vpn.example.com",
            tls=AcmeTlsRequest(
                server_name="vpn.example.com",
                email="operator@example.com",
            ),
        )
    )
    app.manager.save_profile_draft(plan)

    assert app.profile_applier is not None
    result = app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert result.committed_revision == EXPECTED_APPLIED_REVISION
    assert result.connection_info is not None
    assert result.connection_info.share_uri.startswith("tuic://")
    profile = JsonFileStateStore(state_path).load().profiles[0]
    assert isinstance(profile.protocol_material, TuicMaterial)
    document = json.loads(config_path.read_text(encoding="utf-8"))
    assert document["inbounds"][0]["type"] == "tuic"
    assert document["inbounds"][0]["zero_rtt_handshake"] is False


def test_cli_composes_a_complete_vless_tls_websocket_apply_path(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    listen_port = SocketPortSource().choose_available()
    plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="CDN 兼容",
            protocol=ProtocolKind.VLESS_TLS,
            listen_port=listen_port,
            server_address="edge.example.com",
            tls=AcmeTlsRequest(
                server_name="vpn.example.com",
                email="operator@example.com",
            ),
            transport=WebSocketTransportRequest(
                path="/proxy",
                host="vpn.example.com",
            ),
        )
    )
    app.manager.save_profile_draft(plan)

    assert app.profile_applier is not None
    result = app.profile_applier.apply_profile(
        ApplyProfileRequest(profile_id="profile-1", expected_revision=1, confirmed=True)
    )

    assert result.committed_revision == EXPECTED_APPLIED_REVISION
    profile = JsonFileStateStore(state_path).load().profiles[0]
    assert isinstance(profile.protocol_material, VlessMaterial)
    document = json.loads(config_path.read_text(encoding="utf-8"))
    assert document["inbounds"][0]["transport"] == {"type": "ws", "path": "/proxy"}
    assert document["certificate_providers"][0]["tag"] == "tls-profile-1"


def test_cli_composes_a_complete_vmess_tls_websocket_apply_path(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    listen_port = SocketPortSource().choose_available()
    plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="旧客户端兼容",
            protocol=ProtocolKind.VMESS_TLS,
            listen_port=listen_port,
            server_address="edge.example.com",
            tls=AcmeTlsRequest(
                server_name="vpn.example.com",
                email="operator@example.com",
            ),
            transport=WebSocketTransportRequest(
                path="/vmess",
                host="vpn.example.com",
            ),
        )
    )
    app.manager.save_profile_draft(plan)

    assert app.profile_applier is not None
    result = app.profile_applier.apply_profile(
        ApplyProfileRequest(profile_id="profile-1", expected_revision=1, confirmed=True)
    )

    assert result.committed_revision == EXPECTED_APPLIED_REVISION
    profile = JsonFileStateStore(state_path).load().profiles[0]
    assert isinstance(profile.protocol_material, VmessMaterial)
    inbound = json.loads(config_path.read_text(encoding="utf-8"))["inbounds"][0]
    assert inbound["type"] == "vmess"
    assert inbound["users"][0]["alterId"] == 0
