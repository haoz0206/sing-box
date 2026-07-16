import time
from pathlib import Path

from textual.containers import VerticalScroll
from textual.widgets import Button, Input, Select, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import Manager
from sb_manager.application.profile_apply import (
    ApplyProfileRequest,
    ApplyProfileResult,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.protocols.catalog import ProfileConnectionInfo
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.tls.catalog import AcmeTlsIntent, OperatorFileTlsIntent
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    CommitResult,
    RollbackResult,
)
from sb_manager.transports.catalog import GrpcTransportIntent, WebSocketTransportIntent
from sb_manager.ui.app import ManagerApp


class RecordingProfileApplier:
    def __init__(self) -> None:
        self.requests: list[ApplyProfileRequest] = []

    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        self.requests.append(request)
        return ApplyProfileResult(
            transaction=ApplyTransactionResult(
                outcome=ApplyOutcome.APPLIED,
                validation=ConfigValidationResult(valid=True, diagnostics="valid"),
                runtime_refresh=RuntimeRefreshResult(success=True, diagnostics="reloaded"),
                postcondition=RuntimePostcondition(healthy=True, diagnostics="active"),
                rollback=None,
            ),
            committed_revision=2,
            connection_info=ProfileConnectionInfo(
                server_address="vpn.example.com",
                server_port=4433,
                share_uri=(
                    "vless://bf000d23-0752-40b4-affe-68f7707a9661@vpn.example.com:4433"
                    "?encryption=none&flow=xtls-rprx-vision&security=reality"
                    "&sni=www.cloudflare.com&fp=chrome&pbk=public-key-value"
                    "&sid=0123456789abcdef&type=tcp#%E6%89%8B%E6%9C%BA"
                ),
            ),
        )


class RollbackFailingProfileApplier:
    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        assert request.confirmed
        return ApplyProfileResult(
            transaction=ApplyTransactionResult(
                outcome=ApplyOutcome.ROLLBACK_FAILED,
                validation=ConfigValidationResult(valid=True, diagnostics="valid"),
                runtime_refresh=RuntimeRefreshResult(
                    success=False,
                    diagnostics="候选服务无法启动",
                ),
                postcondition=None,
                rollback=RollbackResult(
                    success=False,
                    diagnostics="旧服务无法重新启动",
                    recovery_instructions=(
                        "确认 /etc/sing-box/config.json 已恢复。",
                        "运行 systemctl restart sing-box.service。",
                    ),
                ),
            ),
            committed_revision=None,
        )


class CommitFailingProfileApplier:
    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        assert request.confirmed
        return ApplyProfileResult(
            transaction=ApplyTransactionResult(
                outcome=ApplyOutcome.COMMIT_FAILED,
                validation=ConfigValidationResult(valid=True, diagnostics="valid"),
                runtime_refresh=None,
                postcondition=None,
                rollback=None,
                commit=CommitResult(
                    success=False,
                    diagnostics="Permission denied: /etc/sing-box/config.json",
                ),
            ),
            committed_revision=None,
        )


class UnavailableProfileApplier:
    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        assert request.confirmed
        raise ConfigurationApplyError("sudo authorization denied")


class SlowProfileApplier(RecordingProfileApplier):
    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        time.sleep(0.2)
        return super().apply_profile(request)


async def test_operator_can_start_first_profile_from_empty_dashboard() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        empty_title = app.screen.query_one("#empty-state-title", Static)
        create_button = app.screen.query_one("#create-first-profile", Button)

        assert empty_title.content == "尚未创建代理配置"
        assert str(create_button.label) == "创建第一个配置"

        await pilot.click("#create-first-profile")

        selection_title = app.screen.query_one("#protocol-selection-title", Static)
        reality_option = app.screen.query_one("#protocol-vless-reality", Button)

        assert selection_title.content == "选择适合你的协议"
        assert str(reality_option.label) == "VLESS Reality · 推荐"


async def test_operator_gets_a_guided_reality_form() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")

        form_title = app.screen.query_one("#reality-form-title", Static)
        guidance = app.screen.query_one("#reality-guidance", Static)
        profile_name = app.screen.query_one("#profile-name", Input)
        server_address = app.screen.query_one("#server-address", Input)
        listen_port = app.screen.query_one("#listen-port", Input)
        preview_button = app.screen.query_one("#preview-plan", Button)

        assert form_title.content == "配置 VLESS Reality"
        assert guidance.content == "适合大多数网络环境。UUID、密钥和兼容站点将自动生成。"
        assert profile_name.placeholder == "例如：手机"
        assert server_address.placeholder == "例如：vpn.example.com 或 203.0.113.10"
        assert listen_port.placeholder == "留空自动选择"
        assert str(preview_button.label) == "预览变更计划"


async def test_operator_can_preview_a_reality_plan_without_changing_the_host() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#profile-name")
        await pilot.press("手", "机")
        await pilot.click("#server-address")
        await pilot.press(*"vpn.example.com")
        await pilot.click("#listen-port")
        await pilot.press("4", "4", "3", "3")
        await pilot.click("#preview-plan")

        assert app.screen.query_one("#plan-title", Static).content == "确认变更计划"
        assert app.screen.query_one("#plan-profile", Static).content == "配置：手机"
        assert app.screen.query_one("#plan-protocol", Static).content == "协议：VLESS Reality"
        assert app.screen.query_one("#plan-port", Static).content == "监听端口：4433"
        assert app.screen.query_one("#plan-generated", Static).content == (
            "自动生成：UUID、Reality 密钥、兼容站点"
        )
        assert app.screen.query_one("#plan-safety", Static).content == (
            "当前仅预览，不会修改服务器。"
        )


async def test_operator_sees_which_field_needs_attention() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#listen-port")
        await pilot.press("4", "4", "3", "3")
        await pilot.click("#preview-plan")

        error = app.screen.query_one("#profile-name-error", Static)

        assert error.content == "请输入配置名称"


async def test_operator_can_leave_port_selection_to_apply_time() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#profile-name")
        await pilot.press("手", "机")
        await pilot.click("#preview-plan")

        port_summary = app.screen.query_one("#plan-port", Static)

        assert port_summary.content == "监听端口：自动选择可用端口"


async def test_operator_can_save_the_previewed_profile_as_a_draft() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#profile-name")
        await pilot.press("手", "机")
        await pilot.click("#listen-port")
        await pilot.press("4", "4", "3", "3")
        await pilot.click("#preview-plan")
        await pilot.click("#save-draft")

        assert app.screen.query_one("#draft-saved-title", Static).content == "草案已保存"
        assert app.screen.query_one("#saved-profile", Static).content == "手机"
        assert app.screen.query_one("#saved-status", Static).content == "草案 · revision 1"
        assert app.screen.query_one("#saved-safety", Static).content == "尚未修改服务器。"


async def test_operator_sees_saved_profiles_after_reopening_the_tui() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(
            ManagedProfile(
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.DRAFT,
            ),
        ),
    )
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore(installation)))

    async with app.run_test():
        assert app.screen.query_one("#profile-list-title", Static).content == "代理配置"
        assert app.screen.query_one("#profile-0", Static).content == (
            "手机 · VLESS Reality · 草案 · 端口 4433"
        )
        assert str(app.screen.query_one("#add-profile", Button).label) == "添加配置"


async def test_operator_can_apply_a_specific_saved_draft_after_reopening() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=7,
        profiles=(
            ManagedProfile(
                profile_id="saved-draft",
                profile_name="待应用手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.DRAFT,
            ),
            ManagedProfile(
                profile_id="already-applied",
                profile_name="现有电脑",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=8443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
        ),
    )
    profile_applier = RecordingProfileApplier()
    app = ManagerApp(
        manager=Manager(state_store=MemoryStateStore(installation)),
        profile_applier=profile_applier,
    )

    async with app.run_test() as pilot:
        assert str(app.screen.query_one("#apply-profile-0", Button).label) == "应用草案"
        await pilot.click("#apply-profile-0")

        assert app.screen.query_one("#apply-confirm-profile", Static).content == (
            "配置：待应用手机"
        )
        await pilot.click("#confirm-apply")

        assert profile_applier.requests == [
            ApplyProfileRequest(
                profile_id="saved-draft",
                expected_revision=7,
                confirmed=True,
            )
        ]


async def test_operator_sees_applied_status_after_reopening_the_tui() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=2,
        profiles=(
            ManagedProfile(
                profile_id="profile-1",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
        ),
    )
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore(installation)))

    async with app.run_test():
        assert app.screen.query_one("#profile-0", Static).content == (
            "手机 · VLESS Reality · 已应用 · 端口 4433"
        )


async def test_operator_sees_an_inline_error_for_an_invalid_port() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#profile-name")
        await pilot.press("手", "机")
        await pilot.click("#listen-port")
        await pilot.press("6", "5", "5", "3", "6")
        await pilot.click("#preview-plan")

        assert app.screen.query_one("#listen-port-error", Static).content == (
            "端口必须在 1 到 65535 之间"
        )


async def test_operator_explicitly_confirms_apply_and_sees_success() -> None:
    profile_applier = RecordingProfileApplier()
    app = ManagerApp(profile_applier=profile_applier)

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#profile-name")
        await pilot.press("手", "机")
        await pilot.click("#server-address")
        await pilot.press(*"vpn.example.com")
        await pilot.click("#listen-port")
        await pilot.press("4", "4", "3", "3")
        await pilot.click("#preview-plan")
        await pilot.click("#save-draft")

        assert str(app.screen.query_one("#apply-draft", Button).label) == "应用到服务器"
        await pilot.click("#apply-draft")

        assert app.screen.query_one("#apply-confirm-title", Static).content == "即将修改服务器"
        assert app.screen.query_one("#apply-confirm-profile", Static).content == "配置：手机"
        assert app.screen.query_one("#apply-confirm-warning", Static).content == (
            "将写入 sing-box 配置并刷新服务，失败时自动回滚。"
        )
        assert str(app.screen.query_one("#confirm-apply", Button).label) == "确认并应用"
        assert profile_applier.requests == []

        await pilot.click("#confirm-apply")

        assert profile_applier.requests == [
            ApplyProfileRequest(
                profile_id="profile-1",
                expected_revision=1,
                confirmed=True,
            )
        ]
        assert app.screen.query_one("#apply-result-title", Static).content == "应用成功"
        assert app.screen.query_one("#apply-result-revision", Static).content == (
            "已提交 revision 2"
        )
        assert app.screen.query_one("#apply-result-health", Static).content == (
            "sing-box 配置已生效，服务运行正常。"
        )
        assert app.screen.query_one("#apply-result-endpoint", Static).content == (
            "服务器：vpn.example.com:4433"
        )
        assert app.screen.query_one("#apply-result-share-uri", Input).value == (
            "vless://bf000d23-0752-40b4-affe-68f7707a9661@vpn.example.com:4433"
            "?encryption=none&flow=xtls-rprx-vision&security=reality"
            "&sni=www.cloudflare.com&fp=chrome&pbk=public-key-value"
            "&sid=0123456789abcdef&type=tcp#%E6%89%8B%E6%9C%BA"
        )


async def test_slow_apply_runs_in_background_and_prevents_duplicate_confirmation() -> None:
    app = ManagerApp(profile_applier=SlowProfileApplier())

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")
        app.screen.query_one("#profile-name", Input).value = "后台应用"
        app.screen.query_one("#listen-port", Input).value = "4433"
        await pilot.click("#preview-plan")
        await pilot.click("#save-draft")
        await pilot.click("#apply-draft")
        await pilot.click("#confirm-apply")

        assert app.screen.query_one("#apply-progress", Static).content == (
            "正在校验、提交并检查服务健康状态; 请勿关闭程序。"
        )
        assert app.screen.query_one("#confirm-apply", Button).disabled is True
        await pilot.pause(0.3)

        assert app.screen.query_one("#apply-result-title", Static).content == "应用成功"


async def test_operator_sees_manual_recovery_steps_when_rollback_fails() -> None:
    app = ManagerApp(profile_applier=RollbackFailingProfileApplier())

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#profile-name")
        await pilot.press("手", "机")
        await pilot.click("#listen-port")
        await pilot.press("4", "4", "3", "3")
        await pilot.click("#preview-plan")
        await pilot.click("#save-draft")
        await pilot.click("#apply-draft")
        await pilot.click("#confirm-apply")

        assert app.screen.query_one("#apply-result-title", Static).content == (
            "回滚未完成，需要人工恢复"
        )
        assert app.screen.query_one("#apply-result-details", Static).content == (
            "旧服务无法重新启动"
        )
        assert app.screen.query_one("#recovery-step-0", Static).content == (
            "1. 确认 /etc/sing-box/config.json 已恢复。"
        )
        assert app.screen.query_one("#recovery-step-1", Static).content == (
            "2. 运行 systemctl restart sing-box.service。"
        )


async def test_operator_gets_actionable_guidance_when_helper_result_is_unknown() -> None:
    app = ManagerApp(profile_applier=UnavailableProfileApplier())

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#profile-name")
        await pilot.press("手", "机")
        await pilot.click("#listen-port")
        await pilot.press("4", "4", "3", "3")
        await pilot.click("#preview-plan")
        await pilot.click("#save-draft")
        await pilot.click("#apply-draft")
        await pilot.click("#confirm-apply")

        assert app.screen.query_one("#apply-error-title", Static).content == (
            "无法确认服务器变更结果"
        )
        assert app.screen.query_one("#apply-error-details", Static).content == (
            "sudo authorization denied"
        )
        assert app.screen.query_one("#apply-error-safety", Static).content == (
            "desired state 未提交。请先检查 sing-box 服务和 helper 日志，再决定是否重试。"
        )


async def test_operator_can_create_a_shadowsocks_2022_draft() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")

        shadowsocks_option = app.screen.query_one("#protocol-shadowsocks", Button)
        assert str(shadowsocks_option.label) == "Shadowsocks 2022 · 简洁稳定"
        await pilot.click("#protocol-shadowsocks")

        assert app.screen.query_one("#shadowsocks-form-title", Static).content == (
            "配置 Shadowsocks 2022"
        )
        assert app.screen.query_one("#protocol-guidance", Static).content == (
            "无需 TLS，适合需要简洁配置的场景。安全密钥将自动生成。"
        )
        await pilot.click("#profile-name")
        await pilot.press("备", "用")
        await pilot.click("#server-address")
        await pilot.press(*"vpn.example.com")
        await pilot.click("#listen-port")
        await pilot.press("8", "4", "4", "3")
        await pilot.click("#preview-plan")

        assert app.screen.query_one("#plan-protocol", Static).content == ("协议：Shadowsocks 2022")
        assert app.screen.query_one("#plan-generated", Static).content == (
            "自动生成：Shadowsocks 2022 安全密钥"
        )
        await pilot.click("#save-draft")

        profile = app.manager.get_installation().profiles[0]
        assert profile.protocol is ProtocolKind.SHADOWSOCKS
        assert profile.server_address == "vpn.example.com"


async def test_operator_can_create_a_hysteria2_acme_draft(tmp_path) -> None:
    manager = Manager(
        state_store=MemoryStateStore(),
        acme_data_directory=tmp_path / "acme",
    )
    app = ManagerApp(manager=manager)

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")

        hysteria2_option = app.screen.query_one("#protocol-hysteria2", Button)
        assert str(hysteria2_option.label) == "Hysteria2 · 移动网络"
        await pilot.click("#protocol-hysteria2")

        assert app.screen.query_one("#hysteria2-form-title", Static).content == "配置 Hysteria2"
        await pilot.click("#profile-name")
        await pilot.press("移", "动", "网", "络")
        await pilot.click("#server-address")
        await pilot.press(*"vpn.example.com")
        app.screen.query_one("#tls-server-name", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-email", Input).value = "operator@example.com"
        app.screen.query_one("#listen-port", Input).value = "8443"
        app.screen.query_one("#preview-plan", Button).press()
        await pilot.pause()

        assert app.screen.query_one("#plan-protocol", Static).content == "协议：Hysteria2"
        assert app.screen.query_one("#plan-generated", Static).content == (
            "自动生成：Hysteria2 认证密码、TLS 证书"
        )
        assert app.screen.query_one("#plan-tls", Static).content == (
            "TLS：ACME · vpn.example.com · operator@example.com"
        )
        await pilot.click("#save-draft")

        profile = app.manager.get_installation().profiles[0]
        assert profile.protocol is ProtocolKind.HYSTERIA2
        assert profile.tls_intent == AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        )


async def test_operator_can_create_a_trojan_acme_draft(tmp_path) -> None:
    manager = Manager(
        state_store=MemoryStateStore(),
        acme_data_directory=tmp_path / "acme",
    )
    app = ManagerApp(manager=manager)

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")

        option = app.screen.query_one("#protocol-trojan", Button)
        assert str(option.label) == "Trojan · TLS 兼容"
        option.press()
        await pilot.pause()

        assert app.screen.query_one("#trojan-form-title", Static).content == "配置 Trojan"
        app.screen.query_one("#profile-name", Input).value = "兼容网络"
        app.screen.query_one("#server-address", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-server-name", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-email", Input).value = "operator@example.com"
        app.screen.query_one("#listen-port", Input).value = "443"
        app.screen.query_one("#preview-plan", Button).press()
        await pilot.pause()

        assert app.screen.query_one("#plan-protocol", Static).content == "协议：Trojan"
        assert app.screen.query_one("#plan-generated", Static).content == (
            "自动生成：Trojan 认证密码、TLS 证书"
        )
        await pilot.click("#save-draft")

        profile = app.manager.get_installation().profiles[0]
        assert profile.protocol is ProtocolKind.TROJAN
        assert profile.tls_intent == AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        )


async def test_operator_can_create_an_anytls_acme_draft(tmp_path) -> None:
    manager = Manager(
        state_store=MemoryStateStore(),
        acme_data_directory=tmp_path / "acme",
    )
    app = ManagerApp(manager=manager)

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")

        option = app.screen.query_one("#protocol-anytls", Button)
        assert str(option.label) == "AnyTLS · 抗 TLS 嵌套指纹"
        assert isinstance(app.screen.query_one("#protocol-selection"), VerticalScroll)
        option.press()
        await pilot.pause()

        assert app.screen.query_one("#anytls-form-title", Static).content == "配置 AnyTLS"
        app.screen.query_one("#profile-name", Input).value = "抗干扰"
        app.screen.query_one("#server-address", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-server-name", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-email", Input).value = "operator@example.com"
        app.screen.query_one("#listen-port", Input).value = "443"
        app.screen.query_one("#preview-plan", Button).press()
        await pilot.pause()

        assert app.screen.query_one("#plan-protocol", Static).content == "协议：AnyTLS"
        assert app.screen.query_one("#plan-generated", Static).content == (
            "自动生成：AnyTLS 认证密码、TLS 证书"
        )
        await pilot.click("#save-draft")

        profile = app.manager.get_installation().profiles[0]
        assert profile.protocol is ProtocolKind.ANYTLS
        assert profile.tls_intent == AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        )


async def test_operator_can_create_a_tuic_acme_draft(tmp_path) -> None:
    manager = Manager(
        state_store=MemoryStateStore(),
        acme_data_directory=tmp_path / "acme",
    )
    app = ManagerApp(manager=manager)

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        option = app.screen.query_one("#protocol-tuic", Button)
        assert str(option.label) == "TUIC · QUIC 低延迟"
        option.press()
        await pilot.pause()

        assert app.screen.query_one("#tuic-form-title", Static).content == "配置 TUIC"
        app.screen.query_one("#profile-name", Input).value = "低延迟"
        app.screen.query_one("#server-address", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-server-name", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-email", Input).value = "operator@example.com"
        app.screen.query_one("#listen-port", Input).value = "443"
        app.screen.query_one("#preview-plan", Button).press()
        await pilot.pause()

        assert app.screen.query_one("#plan-protocol", Static).content == "协议：TUIC"
        assert app.screen.query_one("#plan-generated", Static).content == (
            "自动生成：TUIC UUID、TUIC 认证密码、TLS 证书"
        )
        await pilot.click("#save-draft")
        profile = app.manager.get_installation().profiles[0]
        assert profile.protocol is ProtocolKind.TUIC


async def test_operator_can_choose_root_managed_tls_files_as_an_advanced_strategy() -> None:
    trusted_tls_directory = Path("/etc/sing-box-manager/tls")
    manager = Manager(
        state_store=MemoryStateStore(),
        trusted_tls_directory=trusted_tls_directory,
    )
    app = ManagerApp(manager=manager)

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        app.screen.query_one("#protocol-trojan", Button).press()
        await pilot.pause()

        strategy = app.screen.query_one("#tls-strategy", Select)
        strategy.value = "operator-files"
        await pilot.pause()

        assert app.screen.query_one("#tls-acme-fields").display is False
        assert app.screen.query_one("#tls-file-fields").display is True
        app.screen.query_one("#profile-name", Input).value = "已有证书入口"
        app.screen.query_one("#server-address", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-server-name", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-certificate-path", Input).value = str(
            trusted_tls_directory / "server.crt"
        )
        app.screen.query_one("#tls-key-path", Input).value = str(
            trusted_tls_directory / "server.key"
        )
        app.screen.query_one("#listen-port", Input).value = "443"
        app.screen.query_one("#preview-plan", Button).press()
        await pilot.pause()

        assert app.screen.query_one("#plan-tls", Static).content == (
            "TLS：已有证书 · vpn.example.com · /etc/sing-box-manager/tls/server.crt"
        )
        assert app.screen.query_one("#plan-generated", Static).content == (
            "自动生成：Trojan 认证密码"
        )
        await pilot.click("#save-draft")

        assert app.manager.get_installation().profiles[0].tls_intent == (
            OperatorFileTlsIntent(
                server_name="vpn.example.com",
                certificate_path=trusted_tls_directory / "server.crt",
                key_path=trusted_tls_directory / "server.key",
            )
        )


async def test_operator_can_create_a_vless_tls_websocket_draft(tmp_path) -> None:
    manager = Manager(
        state_store=MemoryStateStore(),
        acme_data_directory=tmp_path / "acme",
    )
    app = ManagerApp(manager=manager)

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        option = app.screen.query_one("#protocol-vless-websocket", Button)
        assert str(option.label) == "VLESS TLS · WebSocket/CDN"
        option.press()
        await pilot.pause()

        assert app.screen.query_one("#vless-websocket-form-title", Static).content == (
            "配置 VLESS TLS WebSocket"
        )
        app.screen.query_one("#profile-name", Input).value = "CDN 兼容"
        app.screen.query_one("#server-address", Input).value = "edge.example.com"
        app.screen.query_one("#tls-server-name", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-email", Input).value = "operator@example.com"
        app.screen.query_one("#websocket-path", Input).value = "/proxy"
        app.screen.query_one("#websocket-host", Input).value = "vpn.example.com"
        app.screen.query_one("#listen-port", Input).value = "443"
        app.screen.query_one("#preview-plan", Button).press()
        await pilot.pause()

        assert app.screen.query_one("#plan-protocol", Static).content == "协议：VLESS TLS"
        assert app.screen.query_one("#plan-transport", Static).content == (
            "传输：WebSocket · /proxy · Host vpn.example.com"
        )
        await pilot.click("#save-draft")
        profile = app.manager.get_installation().profiles[0]
        assert profile.protocol is ProtocolKind.VLESS_TLS
        assert profile.transport_intent == WebSocketTransportIntent(
            path="/proxy",
            host="vpn.example.com",
        )


async def test_operator_can_create_a_vless_tls_grpc_draft(tmp_path) -> None:
    manager = Manager(
        state_store=MemoryStateStore(),
        acme_data_directory=tmp_path / "acme",
    )
    app = ManagerApp(manager=manager)

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        option = app.screen.query_one("#protocol-vless-grpc", Button)
        assert str(option.label) == "VLESS TLS · gRPC"
        option.press()
        await pilot.pause()

        assert app.screen.query_one("#vless-grpc-form-title", Static).content == (
            "配置 VLESS TLS gRPC"
        )
        app.screen.query_one("#profile-name", Input).value = "gRPC 入口"
        app.screen.query_one("#server-address", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-server-name", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-email", Input).value = "operator@example.com"
        app.screen.query_one("#grpc-service-name", Input).value = "ProxyService"
        app.screen.query_one("#listen-port", Input).value = "443"
        app.screen.query_one("#preview-plan", Button).press()
        await pilot.pause()

        assert app.screen.query_one("#plan-transport", Static).content == (
            "传输：gRPC · ProxyService"
        )
        await pilot.click("#save-draft")
        profile = app.manager.get_installation().profiles[0]
        assert profile.transport_intent == GrpcTransportIntent(service_name="ProxyService")


async def test_operator_can_create_a_vmess_tls_websocket_draft(tmp_path) -> None:
    manager = Manager(
        state_store=MemoryStateStore(),
        acme_data_directory=tmp_path / "acme",
    )
    app = ManagerApp(manager=manager)

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        option = app.screen.query_one("#protocol-vmess-websocket", Button)
        assert str(option.label) == "VMess TLS · 旧客户端兼容"
        option.press()
        await pilot.pause()

        assert app.screen.query_one("#vmess-websocket-form-title", Static).content == (
            "配置 VMess TLS WebSocket"
        )
        app.screen.query_one("#profile-name", Input).value = "旧客户端兼容"
        app.screen.query_one("#server-address", Input).value = "edge.example.com"
        app.screen.query_one("#tls-server-name", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-email", Input).value = "operator@example.com"
        app.screen.query_one("#websocket-path", Input).value = "/vmess"
        app.screen.query_one("#websocket-host", Input).value = "vpn.example.com"
        app.screen.query_one("#listen-port", Input).value = "443"
        app.screen.query_one("#preview-plan", Button).press()
        await pilot.pause()

        assert app.screen.query_one("#plan-protocol", Static).content == "协议：VMess TLS"
        await pilot.click("#save-draft")
        profile = app.manager.get_installation().profiles[0]
        assert profile.protocol is ProtocolKind.VMESS_TLS


async def test_operator_can_create_a_vmess_tls_grpc_draft(tmp_path) -> None:
    manager = Manager(
        state_store=MemoryStateStore(),
        acme_data_directory=tmp_path / "acme",
    )
    app = ManagerApp(manager=manager)

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        option = app.screen.query_one("#protocol-vmess-grpc", Button)
        assert str(option.label) == "VMess TLS · gRPC 兼容"
        option.press()
        await pilot.pause()

        assert app.screen.query_one("#vmess-grpc-form-title", Static).content == (
            "配置 VMess TLS gRPC"
        )
        app.screen.query_one("#profile-name", Input).value = "VMess gRPC"
        app.screen.query_one("#server-address", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-server-name", Input).value = "vpn.example.com"
        app.screen.query_one("#tls-email", Input).value = "operator@example.com"
        app.screen.query_one("#grpc-service-name", Input).value = "VmService"
        app.screen.query_one("#listen-port", Input).value = "443"
        app.screen.query_one("#preview-plan", Button).press()
        await pilot.pause()

        assert app.screen.query_one("#plan-transport", Static).content == ("传输：gRPC · VmService")
        await pilot.click("#save-draft")
        assert app.manager.get_installation().profiles[0].transport_intent == (
            GrpcTransportIntent(service_name="VmService")
        )


async def test_operator_sees_actionable_configuration_commit_failure() -> None:
    app = ManagerApp(profile_applier=CommitFailingProfileApplier())

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#profile-name")
        await pilot.press("手", "机")
        await pilot.click("#listen-port")
        await pilot.press("4", "4", "3", "3")
        await pilot.click("#preview-plan")
        await pilot.click("#save-draft")
        await pilot.click("#apply-draft")
        await pilot.click("#confirm-apply")

        assert app.screen.query_one("#apply-result-title", Static).content == "无法写入配置"
        assert app.screen.query_one("#apply-result-details", Static).content == (
            "Permission denied: /etc/sing-box/config.json"
        )
        assert app.screen.query_one("#apply-result-safety", Static).content == (
            "尚未刷新服务，原有配置保持不变。"
        )
