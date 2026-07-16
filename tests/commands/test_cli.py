import json
from pathlib import Path

from sb_manager.adapters.json_file_state import JsonFileStateStore
from sb_manager.adapters.socket_ports import SocketPortSource
from sb_manager.application.core_update import PlanCoreUpdateRequest
from sb_manager.application.diagnostics_center import (
    DiagnosticCode,
    DiagnosticCondition,
)
from sb_manager.application.host_readiness import HostReadinessItemCode, ReadinessState
from sb_manager.application.manager import (
    AcmeTlsRequest,
    PlanProfileRequest,
    WebSocketTransportRequest,
)
from sb_manager.application.profile_apply import ApplyProfileRequest
from sb_manager.application.profile_availability import (
    PlanProfileAvailabilityRequest,
    ProfileAvailability,
)
from sb_manager.application.profile_editing import (
    PlanProfileEditRequest,
    ProfileEditScope,
)
from sb_manager.application.profile_recommendation import (
    ProfilePurpose,
    ProtocolVariant,
)
from sb_manager.application.profile_removal import ProfileRemovalScope
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
from sb_manager.seams.artifact_source import ArtifactArchitecture
from sb_manager.tls.catalog import AcmeTlsIntent
from sb_manager.transactions.apply import ApplyOutcome
from sb_manager.ui.app import ManagerApp

EXPECTED_APPLIED_REVISION = 2
EXPECTED_REMOVED_REVISION = 3


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
        "elif sys.argv[1:] == ['version']:\n"
        "    print('sing-box version 1.14.0-alpha.45')\n"
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
        "if request['operation'] == 'inspect-config':\n"
        "    print(json.dumps({'schema_version': 1, 'status': 'observed', "
        "'config': {'exists': False, 'sha256': None}}))\n"
        "    raise SystemExit(0)\n"
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


def test_cli_composes_the_purpose_first_profile_advisor() -> None:
    app = create_app([])

    report = app.profile_recommendation_advisor.recommend(ProfilePurpose.LOW_LATENCY)

    assert report.recommendations[0].variant is ProtocolVariant.HYSTERIA2


def test_cli_composes_an_exact_core_update_path() -> None:
    app = create_app([])

    assert app.core_updater is not None
    plan = app.core_updater.plan(
        PlanCoreUpdateRequest(
            version="1.14.0-alpha.45",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        )
    )

    assert plan.asset_name == "sing-box-1.14.0-alpha.45-linux-amd64.tar.gz"
    assert plan.mutates_host is False


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


def test_cli_composes_transactional_applied_profile_removal(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    listen_port = SocketPortSource().choose_available()
    profile_plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=listen_port,
        )
    )
    app.manager.save_profile_draft(profile_plan)
    assert app.profile_applier is not None
    app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert app.profile_remover is not None
    removal_plan = app.profile_remover.plan_removal("profile-1")
    result = app.profile_remover.remove_profile(removal_plan, confirmed=True)

    assert removal_plan.scope is ProfileRemovalScope.LIVE_CONFIGURATION
    assert result.committed_revision == EXPECTED_REMOVED_REVISION
    assert JsonFileStateStore(state_path).load().profiles == ()
    assert json.loads(config_path.read_text(encoding="utf-8"))["inbounds"] == []


def test_cli_composes_transactional_profile_pause_and_resume(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    listen_port = SocketPortSource().choose_available()
    profile_plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=listen_port,
        )
    )
    app.manager.save_profile_draft(profile_plan)
    assert app.profile_applier is not None
    app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert app.profile_availability_manager is not None
    pause_plan = app.profile_availability_manager.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.PAUSED,
        )
    )
    pause_result = app.profile_availability_manager.apply_change(
        pause_plan,
        confirmed=True,
    )

    assert pause_result.committed_revision == pause_plan.expected_revision + 1
    assert JsonFileStateStore(state_path).load().profiles[0].enabled is False
    assert json.loads(config_path.read_text(encoding="utf-8"))["inbounds"] == []

    resume_plan = app.profile_availability_manager.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.ACTIVE,
        )
    )
    resume_result = app.profile_availability_manager.apply_change(
        resume_plan,
        confirmed=True,
    )

    assert resume_result.committed_revision == resume_plan.expected_revision + 1
    assert JsonFileStateStore(state_path).load().profiles[0].enabled is True
    assert json.loads(config_path.read_text(encoding="utf-8"))["inbounds"][0]["tag"] == (
        "profile-1"
    )


def test_cli_composes_transactional_applied_profile_editing(tmp_path: Path) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    port_source = SocketPortSource()
    listen_port = port_source.choose_available()
    edited_port = port_source.choose_available()
    while edited_port == listen_port:
        edited_port = port_source.choose_available()
    profile_plan = app.manager.plan_profile(
        PlanProfileRequest(
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=listen_port,
            server_address="old.example.com",
        )
    )
    app.manager.save_profile_draft(profile_plan)
    assert app.profile_applier is not None
    app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert app.profile_editor is not None
    edit_plan = app.profile_editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="平板",
            server_address="new.example.com",
            listen_port=edited_port,
        )
    )
    result = app.profile_editor.apply_edit(edit_plan, confirmed=True)

    assert edit_plan.scope is ProfileEditScope.LIVE_CONFIGURATION
    assert result.committed_revision == EXPECTED_REMOVED_REVISION
    assert result.listen_port == edited_port
    installation = JsonFileStateStore(state_path).load()
    assert installation.profiles[0].profile_name == "平板"
    assert installation.profiles[0].server_address == "new.example.com"
    assert installation.profiles[0].listen_port == edited_port
    inbound = json.loads(config_path.read_text(encoding="utf-8"))["inbounds"][0]
    assert inbound["users"][0]["name"] == "平板"
    assert inbound["listen_port"] == edited_port


def test_cli_composes_read_only_prioritized_diagnostics_center(tmp_path: Path) -> None:
    app, _, _ = _create_isolated_app(tmp_path)

    assert app.diagnostics_center is not None
    report = app.diagnostics_center.inspect()

    assert tuple(item.code for item in report.items) == (
        DiagnosticCode.DESIRED_STATE,
        DiagnosticCode.LIVE_CONFIGURATION,
        DiagnosticCode.CONFIG_TARGET,
        DiagnosticCode.PRIVILEGED_HELPER,
        DiagnosticCode.CORE,
        DiagnosticCode.GENERATED_CONFIGURATION,
        DiagnosticCode.DOMAIN_RESOLUTION,
        DiagnosticCode.RUNTIME,
    )
    assert report.items[0].condition is DiagnosticCondition.HEALTHY
    assert report.items[-2].condition is DiagnosticCondition.HEALTHY
    assert report.items[-3].diagnostics == "sing-box check completed successfully"
    assert report.items[-2].summary == "当前没有需要 DNS 解析的公开域名"
    assert report.items[-1].condition is DiagnosticCondition.HEALTHY


def test_cli_diagnostics_resolve_persisted_public_domain(tmp_path: Path) -> None:
    app, state_path, _ = _create_isolated_app(tmp_path)
    JsonFileStateStore(state_path).save(
        ManagedInstallation(
            schema_version=1,
            revision=1,
            profiles=(
                ManagedProfile(
                    profile_id="profile-1",
                    profile_name="本机测试",
                    protocol=ProtocolKind.VLESS_REALITY,
                    listen_port=4433,
                    port_selection=PortSelection.FIXED,
                    status=ProfileStatus.DRAFT,
                    server_address="LOCALHOST.",
                ),
            ),
        )
    )

    assert app.diagnostics_center is not None
    report = app.diagnostics_center.inspect()

    resolution = next(
        item for item in report.items if item.code is DiagnosticCode.DOMAIN_RESOLUTION
    )
    assert resolution.condition is DiagnosticCondition.HEALTHY
    assert resolution.summary == "1 个公开域名可解析"
    assert resolution.diagnostics.startswith("localhost → ")


def test_cli_refuses_unmanaged_config_until_exact_adoption_is_confirmed(
    tmp_path: Path,
) -> None:
    app, state_path, config_path = _create_isolated_app(tmp_path)
    config_path.parent.mkdir(parents=True)
    unmanaged_bytes = b'{"inbounds":[{"tag":"operator-owned"}]}\n'
    config_path.write_bytes(unmanaged_bytes)
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

    rejected = app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert rejected.transaction.outcome is ApplyOutcome.PRECONDITION_FAILED
    assert config_path.read_bytes() == unmanaged_bytes
    assert JsonFileStateStore(state_path).load().profiles[0].status is ProfileStatus.DRAFT

    assert app.config_adopter is not None
    adoption_plan = app.config_adopter.plan()
    adoption = app.config_adopter.adopt(adoption_plan, confirmed=True)
    applied = app.profile_applier.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=adoption.committed_revision,
            confirmed=True,
        )
    )

    assert applied.transaction.outcome is ApplyOutcome.APPLIED
    assert JsonFileStateStore(state_path).load().profiles[0].status is ProfileStatus.APPLIED
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


def test_cli_privileged_mode_checks_the_managed_core_path_by_default(tmp_path: Path) -> None:
    incoming_directory = tmp_path / "incoming"
    helper, _ = _write_fake_privileged_helper(tmp_path, incoming_directory)
    app = create_app(
        [
            "--state-file",
            str(tmp_path / "state.json"),
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

    assert app.host_readiness is not None
    report = app.host_readiness.inspect()
    core = next(item for item in report.items if item.code is HostReadinessItemCode.CORE)

    assert core.state is ReadinessState.ACTION_REQUIRED
    assert "/opt/sing-box-manager/core/current/sing-box" in core.diagnostics


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
