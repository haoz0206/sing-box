import time
from pathlib import Path
from typing import cast

from textual.containers import VerticalScroll
from textual.pilot import Pilot
from textual.widgets import Button, Input, Select, Static, TextArea

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.certificate_diagnostics import (
    CertificateDiagnosticCondition,
    CertificateDiagnosticsReport,
)
from sb_manager.application.config_adoption import (
    ConfigAdoptionPlan,
    ConfigAdoptionResult,
)
from sb_manager.application.host_diagnostics import (
    HostCondition,
    HostDiagnosticsReport,
)
from sb_manager.application.host_readiness import (
    HostReadinessItem,
    HostReadinessItemCode,
    HostReadinessReport,
    ReadinessState,
)
from sb_manager.application.manager import Manager, PlanProfileRequest, ProfilePlan
from sb_manager.application.profile_apply import (
    ApplyProfileRequest,
    ApplyProfileResult,
)
from sb_manager.application.profile_details import (
    ProfileDetails,
    ProfileDetailsNotFoundError,
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
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools, ManagerAppInterfaceTools
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText

EXPECTED_DASHBOARD_REVISION = 2
EXPECTED_REFRESH_INSPECTIONS = 2


class DashboardRecommendationMarkerCatalog:
    """Render marker copy only for the semantic first-profile recommendation."""

    def text(self, key: UiText, /, **values: object) -> str:
        markers = {
            "dashboard.recommendation.add_profile": "从目录开始首个配置",
            "dashboard.action.add_profile": "目录中的创建动作",
        }
        if marker := markers.get(key.value):
            return marker
        return SIMPLIFIED_CHINESE.text(key, **values)


async def open_direct_protocol_selection(
    app: ManagerApp,
    pilot: Pilot[None],
) -> None:
    app.screen.query_one("#choose-protocol-directly", Button).press()
    await pilot.pause()


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


class PreconditionFailingProfileApplier:
    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        assert request.confirmed
        return ApplyProfileResult(
            transaction=ApplyTransactionResult(
                outcome=ApplyOutcome.PRECONDITION_FAILED,
                validation=ConfigValidationResult(valid=True, diagnostics="valid"),
                runtime_refresh=None,
                postcondition=None,
                rollback=None,
                commit=CommitResult(
                    success=False,
                    diagnostics="Live configuration fingerprint changed after review",
                ),
            ),
            committed_revision=None,
        )


class UnavailableProfileApplier:
    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        assert request.confirmed
        raise ConfigurationApplyError("sudo authorization denied")


class UnexpectedProfileApplier:
    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        assert request.confirmed
        raise RuntimeError("token=private-apply-worker-error")


class SlowProfileApplier(RecordingProfileApplier):
    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        time.sleep(0.2)
        return super().apply_profile(request)


class HealthyHostDiagnostics:
    def inspect(self) -> HostDiagnosticsReport:
        return HostDiagnosticsReport(
            condition=HostCondition.HEALTHY,
            summary="sing-box 服务运行正常",
            diagnostics="active",
            recovery_instructions=(),
        )


class UnhealthyHostDiagnostics:
    def inspect(self) -> HostDiagnosticsReport:
        return HostDiagnosticsReport(
            condition=HostCondition.UNHEALTHY,
            summary="sing-box 服务未通过健康检查",
            diagnostics="sing-box.service is inactive",
            recovery_instructions=(
                "运行 systemctl restart sing-box.service。",
                "运行 systemctl status sing-box.service --no-pager。",
            ),
        )


class FlakyHostDiagnostics:
    def __init__(self) -> None:
        self.calls = 0

    def inspect(self) -> HostDiagnosticsReport:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("synthetic runtime failure containing private diagnostics")
        return HostDiagnosticsReport(
            condition=HostCondition.HEALTHY,
            summary="sing-box 服务运行正常",
            diagnostics="active",
            recovery_instructions=(),
        )


class FixedCertificateDiagnostics:
    def __init__(self, report: CertificateDiagnosticsReport) -> None:
        self.report = report
        self.inspections = 0

    def inspect(self, installation: ManagedInstallation) -> CertificateDiagnosticsReport:
        assert installation.revision == EXPECTED_DASHBOARD_REVISION
        self.inspections += 1
        return self.report


def app_with_certificate_report(
    report: CertificateDiagnosticsReport,
) -> tuple[ManagerApp, FixedCertificateDiagnostics]:
    installation = ManagedInstallation(
        schema_version=1,
        revision=EXPECTED_DASHBOARD_REVISION,
        profiles=(
            ManagedProfile(
                profile_id="applied-profile",
                profile_name="现有配置",
                protocol=ProtocolKind.TROJAN,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
        ),
    )
    diagnostics = FixedCertificateDiagnostics(report)
    return (
        ManagerApp(
            manager=Manager(state_store=MemoryStateStore(installation)),
            host_tools=ManagerAppHostTools(certificate_diagnostics=diagnostics),
        ),
        diagnostics,
    )


class FlakyCertificateDiagnostics:
    def __init__(self) -> None:
        self.inspections = 0

    def inspect(self, installation: ManagedInstallation) -> CertificateDiagnosticsReport:
        self.inspections += 1
        if self.inspections == 1:
            raise RuntimeError("token=private-certificate-dashboard-probe")
        return CertificateDiagnosticsReport(
            condition=CertificateDiagnosticCondition.HEALTHY,
            summary="当前托管证书状态正常",
            diagnostics="没有需要维护的证书",
            guidance="当前无需处理",
        )


class FixedHostReadiness:
    def __init__(self, *reports: HostReadinessReport) -> None:
        self.reports = reports
        self.calls = 0

    def inspect(self) -> HostReadinessReport:
        report = self.reports[min(self.calls, len(self.reports) - 1)]
        self.calls += 1
        return report


class FlakyHostReadiness:
    def __init__(self, recovered_report: HostReadinessReport) -> None:
        self.recovered_report = recovered_report
        self.calls = 0

    def inspect(self) -> HostReadinessReport:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("synthetic probe failure containing private diagnostics")
        return self.recovered_report


class NeverCalledCoreUpdater:
    def plan(self, request: object) -> object:
        raise AssertionError("opening the core form must not create a plan")

    def execute(self, plan: object, *, confirmed: bool) -> object:
        raise AssertionError("opening the core form must not activate a core")


def _helper_readiness(state: ReadinessState) -> HostReadinessItem:
    return HostReadinessItem(
        code=HostReadinessItemCode.PRIVILEGED_HELPER,
        state=state,
        title="最小权限 helper",
        summary=(
            "最小权限 helper 与固定配置目标可用"
            if state is ReadinessState.READY
            else "最小权限 helper 或固定配置目标尚不可用"
        ),
        diagnostics="helper ready" if state is ReadinessState.READY else "sudo denied",
        guidance=(
            ""
            if state is ReadinessState.READY
            else "以 root 身份运行 sb-manager-install-policy --confirm，然后返回 TUI 重新检查。"
        ),
    )


def _core_readiness(state: ReadinessState) -> HostReadinessItem:
    return HostReadinessItem(
        code=HostReadinessItemCode.CORE,
        state=state,
        title="sing-box 核心",
        summary="sing-box 1.14.0 已可用" if state is ReadinessState.READY else "核心尚未安装",
        diagnostics="sing-box version 1.14.0" if state is ReadinessState.READY else "not found",
        guidance=(
            ""
            if state is ReadinessState.READY
            else "选择“安装或升级 sing-box 核心”，完成可信安装后重新检查。"
        ),
    )


class FixedProfileDetailsReader:
    def get_profile_details(self, profile_id: str) -> ProfileDetails:
        assert profile_id == "profile-1"
        return ProfileDetails(
            profile_id="profile-1",
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            status=ProfileStatus.APPLIED,
            listen_port=4433,
            server_address="vpn.example.com",
            connection_info=ProfileConnectionInfo(
                server_address="vpn.example.com",
                server_port=4433,
                share_uri="vless://saved-connection-link",
            ),
        )


class MissingProfileDetailsReader:
    def get_profile_details(self, profile_id: str) -> ProfileDetails:
        raise ProfileDetailsNotFoundError(profile_id)


class UnexpectedProfileDetailsReader:
    def get_profile_details(self, profile_id: str) -> ProfileDetails:
        raise RuntimeError("token=private-profile-details-error")


class UnexpectedProfilePlanningManager(Manager):
    def plan_profile(self, request: PlanProfileRequest) -> ProfilePlan:
        raise RuntimeError("token=private-profile-planning-error")


class RecordingConfigAdopter:
    def __init__(self) -> None:
        self.confirmations: list[tuple[ConfigAdoptionPlan, bool]] = []

    def plan(self) -> ConfigAdoptionPlan:
        return ConfigAdoptionPlan(base_revision=0, config_sha256="a" * 64)

    def adopt(
        self,
        plan: ConfigAdoptionPlan,
        *,
        confirmed: bool,
    ) -> ConfigAdoptionResult:
        self.confirmations.append((plan, confirmed))
        return ConfigAdoptionResult(committed_revision=1, config_sha256=plan.config_sha256)


class UnexpectedPlanningConfigAdopter(RecordingConfigAdopter):
    def plan(self) -> ConfigAdoptionPlan:
        raise RuntimeError("token=private-config-adoption-planning-error")


class UnexpectedConfigAdopter(RecordingConfigAdopter):
    def adopt(
        self,
        plan: ConfigAdoptionPlan,
        *,
        confirmed: bool,
    ) -> ConfigAdoptionResult:
        assert confirmed
        raise RuntimeError("token=private-config-adoption-worker-error")


async def test_operator_can_start_first_profile_from_empty_dashboard() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        empty_title = app.screen.query_one("#empty-state-title", Static)
        safety = app.screen.query_one("#dashboard-safety", Static)
        primary_action = app.screen.query_one("#dashboard-primary-action", Button)

        assert empty_title.content == "尚未创建代理配置"
        assert safety.content == (
            "当前页面只读：检查不会修改主机。任何变更都必须先审阅计划并明确确认。"
        )
        assert str(primary_action.label) == "创建第一个配置"
        assert list(app.screen.query("#create-first-profile")) == []

        await pilot.click("#dashboard-primary-action")

        purpose_title = app.screen.query_one("#profile-purpose-title", Static)
        general_option = app.screen.query_one("#purpose-general", Button)

        assert purpose_title.content == "你主要想优化什么?"
        assert str(general_option.label) == "通用搭建 · 推荐"


async def test_dashboard_recommendation_copy_comes_from_the_interface_catalog() -> None:
    app = ManagerApp(
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, DashboardRecommendationMarkerCatalog())
        )
    )

    async with app.run_test():
        recommendation = app.screen.query_one("#dashboard-next-action", Static)
        primary_action = app.screen.query_one("#dashboard-primary-action", Button)

        assert recommendation.content == "建议：从目录开始首个配置"
        assert str(primary_action.label) == "目录中的创建动作"


async def test_operator_can_review_and_confirm_existing_config_adoption() -> None:
    adopter = RecordingConfigAdopter()
    app = ManagerApp(host_tools=ManagerAppHostTools(config_adopter=adopter))

    async with app.run_test() as pilot:
        assert str(app.screen.query_one("#adopt-existing-config", Button).label) == (
            "检查并接管现有配置"
        )

        await pilot.click("#adopt-existing-config")
        await pilot.pause()

        assert app.screen.query_one("#config-adoption-title", Static).content == (
            "确认现有配置接管计划"
        )
        assert app.screen.query_one("#config-adoption-fingerprint", Static).content == (
            f"当前配置 SHA-256：{'a' * 64}"
        )
        assert app.screen.query_one("#config-adoption-safety", Static).content == (
            "接管不会修改服务器，也不会把现有 JSON 导入为 profile。"
        )

        await pilot.click("#confirm-config-adoption")
        await pilot.pause()

        assert adopter.confirmations == [
            (ConfigAdoptionPlan(base_revision=0, config_sha256="a" * 64), True)
        ]
        assert app.screen.query_one("#config-adoption-result-title", Static).content == (
            "现有配置已被记录为替换前置条件"
        )
        assert app.screen.query_one("#config-adoption-result-revision", Static).content == (
            "desired state revision 1"
        )


async def test_unexpected_config_adoption_planning_failure_is_safe_and_not_disclosed() -> None:
    app = ManagerApp(
        host_tools=ManagerAppHostTools(config_adopter=UnexpectedPlanningConfigAdopter())
    )

    async with app.run_test() as pilot:
        await pilot.click("#adopt-existing-config")
        await pilot.pause()

        assert app.screen.query_one("#config-adoption-planning-error-title", Static).content == (
            "无法检查现有配置"
        )
        assert app.screen.query_one("#config-adoption-planning-error-details", Static).content == (
            "读取配置接管计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#config-adoption-planning-error-safety", Static).content == (
            "尚未记录 replacement precondition，也未修改服务器配置。请重新打开诊断或仪表盘后再试。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-config-adoption-planning-error" not in rendered_text


async def test_unexpected_config_adoption_failure_is_unknown_and_not_disclosed() -> None:
    app = ManagerApp(host_tools=ManagerAppHostTools(config_adopter=UnexpectedConfigAdopter()))

    async with app.run_test() as pilot:
        await pilot.click("#adopt-existing-config")
        await pilot.pause()
        await pilot.click("#confirm-config-adoption")
        await pilot.pause()

        assert app.screen.query_one("#config-adoption-unknown-title", Static).content == (
            "无法确认配置接管结果"
        )
        assert app.screen.query_one("#config-adoption-unknown-details", Static).content == (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#config-adoption-unknown-safety", Static).content == (
            "此流程没有修改服务器配置。desired state 是否已记录 replacement precondition 未知。"
            "请先通过诊断中心重新检查 live configuration identity，再决定是否重试。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-config-adoption-worker-error" not in rendered_text


async def test_dashboard_answers_runtime_profile_and_next_action_questions() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=2,
        profiles=(
            ManagedProfile(
                profile_id="applied-profile",
                profile_name="现有配置",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
            ManagedProfile(
                profile_id="draft-profile",
                profile_name="待应用配置",
                protocol=ProtocolKind.SHADOWSOCKS,
                listen_port=8388,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.DRAFT,
            ),
        ),
    )
    app = ManagerApp(
        manager=Manager(state_store=MemoryStateStore(installation)),
        host_tools=ManagerAppHostTools(host_diagnostics=HealthyHostDiagnostics()),
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one("#runtime-status", Static).content == ("服务状态：运行正常")
        assert app.screen.query_one("#profile-summary", Static).content == (
            "配置：1 在线 · 0 已暂停 · 1 草案"
        )
        assert app.screen.query_one("#dashboard-next-action", Static).content == (
            "建议：先审阅并应用 1 个草案"
        )


async def test_dashboard_prioritizes_a_managed_certificate_requiring_action() -> None:
    app, certificate_diagnostics = app_with_certificate_report(
        CertificateDiagnosticsReport(
            condition=CertificateDiagnosticCondition.ACTION_REQUIRED,
            summary="1 个托管证书需要处理",
            diagnostics="vpn.example.com 已过期",
            guidance="打开诊断中心处理托管证书",
        )
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one("#certificate-maintenance-status", Static).content == (
            "证书维护：需要处理"
        )
        assert app.screen.query_one("#dashboard-next-action", Static).content == (
            "建议：先处理证书维护项，再进行配置变更"
        )
        assert certificate_diagnostics.inspections == 1


async def test_dashboard_surfaces_certificate_maintenance_attention() -> None:
    app, _ = app_with_certificate_report(
        CertificateDiagnosticsReport(
            condition=CertificateDiagnosticCondition.ATTENTION,
            summary="1 个托管证书将在 30 天内到期",
            diagnostics="vpn.example.com 剩余 20 天",
            guidance="安排托管证书续期检查",
        )
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one("#certificate-maintenance-status", Static).content == (
            "证书维护：建议关注"
        )
        assert app.screen.query_one("#dashboard-next-action", Static).content == (
            "建议：查看需要关注的证书维护项"
        )


async def test_failed_certificate_maintenance_probe_is_conservative_and_retryable() -> None:
    certificate_diagnostics = FlakyCertificateDiagnostics()
    app = ManagerApp(
        host_tools=ManagerAppHostTools(certificate_diagnostics=certificate_diagnostics)
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one("#certificate-maintenance-status", Static).content == (
            "证书维护：无法检查"
        )
        assert app.screen.query_one("#dashboard-next-action", Static).content == (
            "建议：先重新检查证书维护状态"
        )
        assert not app.screen.query_one("#refresh-certificate-maintenance", Button).disabled
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-certificate-dashboard-probe" not in rendered_text

        await pilot.click("#refresh-certificate-maintenance")
        await pilot.pause()

        assert app.screen.query_one("#certificate-maintenance-status", Static).content == (
            "证书维护：状态正常"
        )
        assert certificate_diagnostics.inspections == EXPECTED_REFRESH_INSPECTIONS


async def test_operator_can_drill_into_actionable_unhealthy_runtime_diagnostics() -> None:
    app = ManagerApp(host_tools=ManagerAppHostTools(host_diagnostics=UnhealthyHostDiagnostics()))

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one("#runtime-status", Static).content == ("服务状态：需要检查")
        assert app.screen.query_one("#dashboard-next-action", Static).content == (
            "建议：先检查 sing-box 服务，再进行配置变更"
        )
        assert str(app.screen.query_one("#view-diagnostics", Button).label) == "查看诊断"

        await pilot.click("#view-diagnostics")

        assert app.screen.query_one("#diagnostics-title", Static).content == "主机诊断"
        assert app.screen.query_one("#diagnostics-summary", Static).content == (
            "sing-box 服务未通过健康检查"
        )
        assert app.screen.query_one("#diagnostics-details", Static).content == (
            "sing-box.service is inactive"
        )
        assert app.screen.query_one("#diagnostics-recovery-0", Static).content == (
            "1. 运行 systemctl restart sing-box.service。"
        )


async def test_failed_runtime_inspection_is_conservative_and_retryable() -> None:
    diagnostics = FlakyHostDiagnostics()
    app = ManagerApp(host_tools=ManagerAppHostTools(host_diagnostics=diagnostics))

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one("#runtime-status", Static).content == "服务状态：无法检查"
        assert app.screen.query_one("#dashboard-next-action", Static).content == (
            "建议：先重新检查服务状态"
        )
        assert app.screen.query_one("#view-diagnostics", Button).disabled
        assert not app.screen.query_one("#refresh-runtime-status", Button).disabled
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private diagnostics" not in rendered_text

        await pilot.click("#refresh-runtime-status")
        await pilot.pause()

        expected_calls = 2
        assert diagnostics.calls == expected_calls
        assert app.screen.query_one("#runtime-status", Static).content == "服务状态：运行正常"
        assert not app.screen.query_one("#view-diagnostics", Button).disabled


async def test_first_run_dashboard_prioritizes_host_readiness_before_profile_apply() -> None:
    readiness = FixedHostReadiness(
        HostReadinessReport(
            items=(
                _helper_readiness(ReadinessState.ACTION_REQUIRED),
                _core_readiness(ReadinessState.ACTION_REQUIRED),
            )
        )
    )
    app = ManagerApp(
        core_updater=NeverCalledCoreUpdater(),
        host_tools=ManagerAppHostTools(host_readiness=readiness),
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one("#host-readiness-status", Static).content == (
            "主机准备度：需要完成 2 项"
        )
        assert app.screen.query_one("#dashboard-next-action", Static).content == (
            "建议：先完成主机准备项，再应用配置"
        )
        assert str(app.screen.query_one("#view-readiness", Button).label) == "查看准备度"

        await pilot.click("#view-readiness")

        assert app.screen.query_one("#host-readiness-title", Static).content == "主机准备度"
        assert app.screen.query_one("#host-readiness-summary", Static).content == (
            "应用前需要完成 2 项准备"
        )
        assert "sb-manager-install-policy --confirm" in str(
            app.screen.query_one("#readiness-privileged-helper-guidance", Static).content
        )
        assert len(app.screen.query("#readiness-manage-core")) == 0


async def test_readiness_screen_routes_core_install_after_helper_is_ready() -> None:
    readiness = FixedHostReadiness(
        HostReadinessReport(
            items=(
                _helper_readiness(ReadinessState.READY),
                _core_readiness(ReadinessState.ACTION_REQUIRED),
            )
        )
    )
    app = ManagerApp(
        core_updater=NeverCalledCoreUpdater(),
        host_tools=ManagerAppHostTools(host_readiness=readiness),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#view-readiness")

        assert str(app.screen.query_one("#readiness-manage-core", Button).label) == (
            "安装或升级 sing-box 核心"
        )

        await pilot.click("#readiness-manage-core")

        assert app.screen.query_one("#core-update-form-title", Static).content == (
            "安装或升级 sing-box 核心"
        )


async def test_operator_can_refresh_host_readiness_after_setup() -> None:
    readiness = FixedHostReadiness(
        HostReadinessReport(
            items=(
                _helper_readiness(ReadinessState.READY),
                _core_readiness(ReadinessState.ACTION_REQUIRED),
            )
        ),
        HostReadinessReport(
            items=(
                _helper_readiness(ReadinessState.READY),
                _core_readiness(ReadinessState.READY),
            )
        ),
    )
    app = ManagerApp(host_tools=ManagerAppHostTools(host_readiness=readiness))

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.query_one("#host-readiness-status", Static).content == (
            "主机准备度：需要完成 1 项"
        )

        await pilot.click("#refresh-readiness")
        await pilot.pause()

        assert readiness.calls == len(readiness.reports)
        assert app.screen.query_one("#host-readiness-status", Static).content == (
            "主机准备度：可以应用配置"
        )


async def test_failed_host_readiness_is_conservative_and_retryable() -> None:
    readiness = FlakyHostReadiness(
        HostReadinessReport(
            items=(
                _helper_readiness(ReadinessState.READY),
                _core_readiness(ReadinessState.READY),
            )
        )
    )
    app = ManagerApp(host_tools=ManagerAppHostTools(host_readiness=readiness))

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one("#host-readiness-status", Static).content == (
            "主机准备度：无法检查"
        )
        assert app.screen.query_one("#dashboard-next-action", Static).content == (
            "建议：先重新检查主机准备度"
        )
        primary_action = app.screen.query_one("#dashboard-primary-action", Button)
        assert str(primary_action.label) == "立即重新检查主机准备度"
        assert not primary_action.has_class("hidden")
        assert app.screen.query_one("#view-readiness", Button).disabled
        assert not app.screen.query_one("#refresh-readiness", Button).disabled
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private diagnostics" not in rendered_text

        await pilot.click("#dashboard-primary-action")
        await pilot.pause()

        expected_calls = 2
        assert readiness.calls == expected_calls
        assert app.screen.query_one("#host-readiness-status", Static).content == (
            "主机准备度：可以应用配置"
        )


async def test_operator_gets_a_guided_reality_form() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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


async def test_unexpected_profile_planning_failure_is_safe_and_not_disclosed() -> None:
    app = ManagerApp(manager=UnexpectedProfilePlanningManager(state_store=MemoryStateStore()))

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
        await pilot.click("#protocol-vless-reality")
        app.screen.query_one("#profile-name", Input).value = "手机"
        await pilot.click("#preview-plan")
        await pilot.pause()

        assert app.screen.query_one("#profile-planning-error-title", Static).content == (
            "无法准备配置计划"
        )
        assert app.screen.query_one("#profile-planning-error-details", Static).content == (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#profile-planning-error-safety", Static).content == (
            "尚未创建草案，也未修改服务器。请返回后重新填写，或先检查 desired state 文件访问。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-planning-error" not in rendered_text


async def test_operator_sees_which_field_needs_attention() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#listen-port")
        await pilot.press("4", "4", "3", "3")
        await pilot.click("#preview-plan")

        error = app.screen.query_one("#profile-name-error", Static)

        assert error.content == "请输入配置名称"


async def test_operator_can_leave_port_selection_to_apply_time() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#profile-name")
        await pilot.press("手", "机")
        await pilot.click("#preview-plan")

        port_summary = app.screen.query_one("#plan-port", Static)

        assert port_summary.content == "监听端口：自动选择可用端口"


async def test_operator_can_save_the_previewed_profile_as_a_draft() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")

        assert app.screen.query_one("#profiles-workspace-title", Static).content == "配置工作区"
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
        assert list(app.screen.query("#apply-profile-0")) == []
        assert str(app.screen.query_one("#dashboard-primary-action", Button).label) == (
            "审阅并应用草案"
        )
        await pilot.click("#dashboard-primary-action")

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


async def test_changed_live_configuration_is_reported_without_claiming_a_rollback() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(
            ManagedProfile(
                profile_id="saved-draft",
                profile_name="待应用手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.DRAFT,
            ),
        ),
    )
    app = ManagerApp(
        manager=Manager(state_store=MemoryStateStore(installation)),
        profile_applier=PreconditionFailingProfileApplier(),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#apply-profile-0")
        await pilot.click("#confirm-apply")

        assert app.screen.query_one("#apply-result-title", Static).content == ("服务器配置已变化")
        assert app.screen.query_one("#apply-result-details", Static).content == (
            "Live configuration fingerprint changed after review"
        )
        assert app.screen.query_one("#apply-result-safety", Static).content == (
            "本次尚未写入配置，请重新检查并确认接管状态。"
        )


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

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")

        assert app.screen.query_one("#profile-0", Static).content == (
            "手机 · VLESS Reality · 在线 · 端口 4433"
        )


async def test_operator_explicitly_reveals_a_persisted_profile_share_uri_once() -> None:
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
    app = ManagerApp(
        manager=Manager(state_store=MemoryStateStore(installation)),
        host_tools=ManagerAppHostTools(profile_details_reader=FixedProfileDetailsReader()),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        assert str(app.screen.query_one("#view-profile-0", Button).label) == "查看详情"
        await pilot.click("#view-profile-0")

        assert app.screen.query_one("#profile-details-title", Static).content == "配置详情"
        assert app.screen.query_one("#profile-details-name", Static).content == "名称：手机"
        assert app.screen.query_one("#connection-share-endpoint", Static).content == (
            "服务器：vpn.example.com:4433"
        )
        assert len(app.screen.query("#connection-share-uri")) == 0
        assert app.screen.query_one("#connection-share-warning", Static).content == (
            "连接链接包含完整访问凭据，默认隐藏。仅在私密终端中显示。"
        )
        assert str(app.screen.query_one("#reveal-connection-share", Button).label) == (
            "显示一次连接链接"
        )

        await pilot.click("#reveal-connection-share")

        assert app.screen.query_one("#connection-share-uri", TextArea).text == (
            "vless://saved-connection-link"
        )
        assert app.screen.query_one("#connection-share-uri", TextArea).read_only is True
        assert len(app.screen.query("#reveal-connection-share")) == 0
        assert str(app.screen.query_one("#hide-connection-share", Button).label) == (
            "立即隐藏连接链接"
        )

        await pilot.click("#hide-connection-share")

        assert len(app.screen.query("#connection-share-uri")) == 0
        assert len(app.screen.query("#reveal-connection-share")) == 0
        assert len(app.screen.query("#hide-connection-share")) == 0
        assert app.screen.query_one("#connection-share-warning", Static).content == (
            "连接链接已重新隐藏，本页面不会再次显示。返回详情后可重新选择显示。"
        )


async def test_profile_detail_lookup_failure_is_presented_without_crashing_the_tui() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(
            ManagedProfile(
                profile_id="profile-1",
                profile_name="已被其他会话删除",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
        ),
    )
    app = ManagerApp(
        manager=Manager(state_store=MemoryStateStore(installation)),
        host_tools=ManagerAppHostTools(profile_details_reader=MissingProfileDetailsReader()),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")

        assert app.screen.query_one("#profile-details-error-title", Static).content == (
            "无法打开配置详情"
        )
        assert app.screen.query_one("#profile-details-error-message", Static).content == (
            "配置可能已被另一个会话修改，请返回后重新打开列表。"
        )


async def test_unexpected_profile_detail_failure_is_safe_and_not_disclosed() -> None:
    installation = ManagedInstallation(
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
            ),
        ),
    )
    app = ManagerApp(
        manager=Manager(state_store=MemoryStateStore(installation)),
        host_tools=ManagerAppHostTools(profile_details_reader=UnexpectedProfileDetailsReader()),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.pause()

        assert app.screen.query_one("#profile-details-unexpected-title", Static).content == (
            "无法读取配置详情"
        )
        assert app.screen.query_one("#profile-details-unexpected-details", Static).content == (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#profile-details-unexpected-safety", Static).content == (
            "尚未修改任何配置。请返回列表后重新读取。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-details-error" not in rendered_text


async def test_operator_sees_an_inline_error_for_an_invalid_port() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
        await pilot.click("#protocol-vless-reality")
        await pilot.click("#profile-name")
        await pilot.press("手", "机")
        await pilot.click("#listen-port")
        await pilot.press("6", "5", "5", "3", "6")
        await pilot.click("#preview-plan")

        assert app.screen.query_one("#listen-port-error", Static).content == (
            "端口必须在 1 到 65535 之间"
        )


async def test_operator_confirms_apply_then_explicitly_reveals_the_share_uri() -> None:
    profile_applier = RecordingProfileApplier()
    app = ManagerApp(profile_applier=profile_applier)

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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
        assert len(app.screen.query("#apply-result-share-uri")) == 0
        assert app.screen.query_one("#connection-share-endpoint", Static).content == (
            "服务器：vpn.example.com:4433"
        )
        assert app.screen.query_one("#connection-share-warning", Static).content == (
            "连接链接包含完整访问凭据，默认隐藏。仅在私密终端中显示。"
        )

        await pilot.click("#reveal-connection-share")

        assert app.screen.query_one("#connection-share-uri", TextArea).text == (
            "vless://bf000d23-0752-40b4-affe-68f7707a9661@vpn.example.com:4433"
            "?encryption=none&flow=xtls-rprx-vision&security=reality"
            "&sni=www.cloudflare.com&fp=chrome&pbk=public-key-value"
            "&sid=0123456789abcdef&type=tcp#%E6%89%8B%E6%9C%BA"
        )


async def test_slow_apply_runs_in_background_and_prevents_duplicate_confirmation() -> None:
    app = ManagerApp(profile_applier=SlowProfileApplier())

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
        await pilot.click("#protocol-vless-reality")
        app.screen.query_one("#profile-name", Input).value = "后台应用"
        app.screen.query_one("#listen-port", Input).value = "4433"
        await pilot.click("#preview-plan")
        await pilot.click("#save-draft")
        await pilot.click("#apply-draft")
        await pilot.click("#confirm-apply")

        assert app.screen.query_one("#apply-progress", Static).content == (
            "操作已确认，正在校验、提交并检查服务健康状态。完成前无法返回。"
        )
        assert app.screen.query_one("#confirm-apply", Button).disabled is True
        assert app.screen.check_action("return_from_confirmation", ()) is None
        await pilot.press("escape")

        assert app.screen.query_one("#apply-confirm-title", Static).content == ("即将修改服务器")
        await pilot.pause(0.3)

        assert app.screen.query_one("#apply-result-title", Static).content == "应用成功"
        await pilot.press("escape")
        assert app.screen.query_one("#apply-confirm-title", Static).content == ("即将修改服务器")
        assert app.screen.check_action("return_from_confirmation", ()) is True

        await pilot.press("escape")
        assert app.screen.query_one("#draft-saved-title", Static).content == "草案已保存"


async def test_operator_sees_manual_recovery_steps_when_rollback_fails() -> None:
    app = ManagerApp(profile_applier=RollbackFailingProfileApplier())

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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


async def test_unexpected_apply_failure_reports_unknown_state_without_disclosure() -> None:
    app = ManagerApp(profile_applier=UnexpectedProfileApplier())

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
        await pilot.click("#protocol-vless-reality")
        app.screen.query_one("#profile-name", Input).value = "意外失败"
        app.screen.query_one("#listen-port", Input).value = "4433"
        await pilot.click("#preview-plan")
        await pilot.click("#save-draft")
        await pilot.click("#apply-draft")
        await pilot.click("#confirm-apply")
        await pilot.pause()

        assert app.screen.query_one("#apply-unexpected-error-title", Static).content == (
            "无法确认配置应用结果"
        )
        assert app.screen.query_one("#apply-unexpected-error-details", Static).content == (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#apply-unexpected-error-safety", Static).content == (
            "服务器配置、服务和 desired state 的结果均未知。"
            "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-apply-worker-error" not in rendered_text


async def test_operator_can_create_a_shadowsocks_2022_draft() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)

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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)

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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)

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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)

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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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
        await pilot.click("#dashboard-primary-action")
        await open_direct_protocol_selection(app, pilot)
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
