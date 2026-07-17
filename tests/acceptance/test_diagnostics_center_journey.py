from textual.widgets import Button, Static

from sb_manager.application.config_adoption import (
    ConfigAdoptionPlan,
    ConfigAdoptionResult,
)
from sb_manager.application.core_update import (
    CoreUpdatePlan,
    CoreUpdateResult,
    PlanCoreUpdateRequest,
)
from sb_manager.application.diagnostics_center import (
    DiagnosticAction,
    DiagnosticCode,
    DiagnosticCondition,
    DiagnosticItem,
    DiagnosticsCenterReport,
)
from sb_manager.application.host_diagnostics import (
    HostCondition,
    HostDiagnosticsReport,
)
from sb_manager.application.service_logs import (
    ServiceLogCondition,
    ServiceLogReport,
)
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools

REFRESHED_INSPECTION_COUNT = 2
REFRESHED_SERVICE_LOG_COUNT = 2


class FixedDiagnosticsCenter:
    def __init__(self, *reports: DiagnosticsCenterReport) -> None:
        self.reports = reports
        self.calls = 0

    def inspect(self) -> DiagnosticsCenterReport:
        report = self.reports[min(self.calls, len(self.reports) - 1)]
        self.calls += 1
        return report


class FailingDiagnosticsCenter:
    def inspect(self) -> DiagnosticsCenterReport:
        raise RuntimeError("unexpected diagnostics failure")


class RecordingServiceLogReader:
    def __init__(self, *reports: ServiceLogReport) -> None:
        self.reports = reports
        self.calls = 0
        self.limits: list[int] = []

    def read_recent(self, *, limit: int = 200) -> ServiceLogReport:
        self.limits.append(limit)
        report = self.reports[min(self.calls, len(self.reports) - 1)]
        self.calls += 1
        return report


class HealthyHostDiagnostics:
    def inspect(self) -> HostDiagnosticsReport:
        return HostDiagnosticsReport(
            condition=HostCondition.HEALTHY,
            summary="sing-box 服务运行正常",
            diagnostics="active",
            recovery_instructions=(),
        )


class RecordingConfigAdopter:
    def plan(self) -> ConfigAdoptionPlan:
        return ConfigAdoptionPlan(base_revision=0, config_sha256="b" * 64)

    def adopt(
        self,
        plan: ConfigAdoptionPlan,
        *,
        confirmed: bool,
    ) -> ConfigAdoptionResult:
        raise AssertionError("opening the review must not confirm adoption")


class NeverCalledCoreUpdater:
    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        raise AssertionError("opening the form must not plan an update")

    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
        raise AssertionError("opening the form must not activate a core")


def report_with_actions() -> DiagnosticsCenterReport:
    return DiagnosticsCenterReport(
        items=(
            DiagnosticItem(
                code=DiagnosticCode.DESIRED_STATE,
                condition=DiagnosticCondition.HEALTHY,
                title="manager desired state",
                summary="revision 4 可读取",
                diagnostics="1 个已应用配置",
                guidance="",
            ),
            DiagnosticItem(
                code=DiagnosticCode.PRIVILEGED_HELPER,
                condition=DiagnosticCondition.ATTENTION,
                title="最小权限 helper",
                summary="直接模式可用，但 helper 尚未安装",
                diagnostics="sudo policy not found",
                guidance="安装最小权限策略以启用核心升级",
            ),
            DiagnosticItem(
                code=DiagnosticCode.RUNTIME,
                condition=DiagnosticCondition.ACTION_REQUIRED,
                title="sing-box 运行状态",
                summary="sing-box 服务未通过健康检查",
                diagnostics="inactive",
                guidance="运行 systemctl restart sing-box.service。",
            ),
        )
    )


def healthy_report() -> DiagnosticsCenterReport:
    return DiagnosticsCenterReport(
        items=(
            DiagnosticItem(
                code=DiagnosticCode.DESIRED_STATE,
                condition=DiagnosticCondition.HEALTHY,
                title="manager desired state",
                summary="revision 4 可读取",
                diagnostics="1 个已应用配置",
                guidance="",
            ),
            DiagnosticItem(
                code=DiagnosticCode.RUNTIME,
                condition=DiagnosticCondition.HEALTHY,
                title="sing-box 运行状态",
                summary="sing-box 服务运行正常",
                diagnostics="active",
                guidance="",
            ),
        )
    )


def untracked_configuration_report() -> DiagnosticsCenterReport:
    return DiagnosticsCenterReport(
        items=(
            DiagnosticItem(
                code=DiagnosticCode.LIVE_CONFIGURATION,
                condition=DiagnosticCondition.ACTION_REQUIRED,
                title="实时配置身份",
                summary="发现尚未由 manager 接管的现有配置",
                diagnostics=f"当前配置 SHA-256：{'b' * 64}",
                guidance=(
                    "打开现有配置接管流程，先审查并确认这个精确指纹。接管不会导入或改写配置。"
                ),
                action=DiagnosticAction.REVIEW_CONFIG_ADOPTION,
            ),
        )
    )


def missing_core_report() -> DiagnosticsCenterReport:
    return DiagnosticsCenterReport(
        items=(
            DiagnosticItem(
                code=DiagnosticCode.CORE,
                condition=DiagnosticCondition.ACTION_REQUIRED,
                title="sing-box 核心",
                summary="sing-box 核心尚不可用",
                diagnostics="sing-box not found",
                guidance="选择可信版本并安装 sing-box 核心",
                action=DiagnosticAction.MANAGE_CORE,
            ),
        )
    )


def invalid_generated_configuration_report() -> DiagnosticsCenterReport:
    return DiagnosticsCenterReport(
        items=(
            DiagnosticItem(
                code=DiagnosticCode.GENERATED_CONFIGURATION,
                condition=DiagnosticCondition.ACTION_REQUIRED,
                title="生成配置语义检查",
                summary="当前 desired state 生成的 sing-box 配置无效",
                diagnostics="inbound[0].tls: missing certificate provider",
                guidance="不要应用。修复受影响配置或恢复 desired-state 备份后重新检查。",
            ),
        )
    )


def unresolved_domain_report() -> DiagnosticsCenterReport:
    return DiagnosticsCenterReport(
        items=(
            DiagnosticItem(
                code=DiagnosticCode.DOMAIN_RESOLUTION,
                condition=DiagnosticCondition.ATTENTION,
                title="公开域名解析",
                summary="1 个公开域名无法解析",
                diagnostics="proxy.example.com：Name or service not known",
                guidance=("检查域名拼写、A/AAAA 记录和本机 DNS。解析恢复后再签发证书或分享连接。"),
            ),
        )
    )


def unknown_listener_owner_report() -> DiagnosticsCenterReport:
    return DiagnosticsCenterReport(
        items=(
            DiagnosticItem(
                code=DiagnosticCode.LISTENER_OWNERSHIP,
                condition=DiagnosticCondition.ATTENTION,
                title="监听端口与进程归属",
                summary="1 个监听端点的进程归属无法确认",
                diagnostics="TCP 4433：[red]归属未知[/red]",
                guidance="以能读取相关 /proc 进程描述符的权限重新检查。",
            ),
        )
    )


def expiring_certificate_report() -> DiagnosticsCenterReport:
    return DiagnosticsCenterReport(
        items=(
            DiagnosticItem(
                code=DiagnosticCode.CERTIFICATE_CONDITION,
                condition=DiagnosticCondition.ATTENTION,
                title="托管证书有效期",
                summary="1 个托管证书将在 30 天内过期",
                diagnostics=(
                    "TLS [red]production[/red]：proxy.example.com，有效至 2026-08-01 (剩余 15 天)"
                ),
                guidance="检查 ACME 自动续期并在 7 天阈值前复检。",
            ),
        )
    )


async def test_operator_sees_generated_configuration_failure_and_recovery_guidance() -> None:
    app = ManagerApp(
        host_tools=ManagerAppHostTools(
            diagnostics_center=FixedDiagnosticsCenter(invalid_generated_configuration_report())
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-diagnostics-center")
        await pilot.pause()

        assert (
            app.screen.query_one("#diagnostic-generated-configuration-title", Static).content
            == "[需处理] 生成配置语义检查"
        )
        assert (
            app.screen.query_one("#diagnostic-generated-configuration-details", Static).content
            == "inbound[0].tls: missing certificate provider"
        )
        assert (
            app.screen.query_one("#diagnostic-generated-configuration-guidance", Static).content
            == "下一步：不要应用。修复受影响配置或恢复 desired-state 备份后重新检查。"
        )


async def test_operator_sees_unresolved_domain_and_recovery_guidance() -> None:
    app = ManagerApp(
        host_tools=ManagerAppHostTools(
            diagnostics_center=FixedDiagnosticsCenter(unresolved_domain_report())
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-diagnostics-center")
        await pilot.pause()

        assert (
            app.screen.query_one("#diagnostic-domain-resolution-title", Static).content
            == "[注意] 公开域名解析"
        )
        assert (
            app.screen.query_one("#diagnostic-domain-resolution-details", Static).content
            == "proxy.example.com：Name or service not known"
        )
        assert app.screen.query_one("#diagnostic-domain-resolution-guidance", Static).content == (
            "下一步：检查域名拼写、A/AAAA 记录和本机 DNS。解析恢复后再签发证书或分享连接。"
        )


async def test_operator_sees_unknown_listener_owner_without_a_false_healthy_claim() -> None:
    app = ManagerApp(
        host_tools=ManagerAppHostTools(
            diagnostics_center=FixedDiagnosticsCenter(unknown_listener_owner_report())
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-diagnostics-center")
        await pilot.pause()

        assert (
            app.screen.query_one("#diagnostic-listener-ownership-title", Static).content
            == "[注意] 监听端口与进程归属"
        )
        assert (
            app.screen.query_one("#diagnostic-listener-ownership-details", Static).content
            == "TCP 4433：[red]归属未知[/red]"
        )
        assert (
            app.screen.query_one("#diagnostic-listener-ownership-details", Static).render().plain
            == "TCP 4433：[red]归属未知[/red]"
        )


async def test_operator_sees_expiring_certificate_as_literal_actionable_evidence() -> None:
    app = ManagerApp(
        host_tools=ManagerAppHostTools(
            diagnostics_center=FixedDiagnosticsCenter(expiring_certificate_report())
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-diagnostics-center")
        await pilot.pause()

        assert (
            app.screen.query_one("#diagnostic-certificate-condition-title", Static).content
            == "[注意] 托管证书有效期"
        )
        details = app.screen.query_one("#diagnostic-certificate-condition-details", Static)
        assert details.content == (
            "TLS [red]production[/red]：proxy.example.com，有效至 2026-08-01 (剩余 15 天)"
        )
        assert details.render().plain == details.content
        assert (
            app.screen.query_one("#diagnostic-certificate-condition-guidance", Static).content
            == "下一步：检查 ACME 自动续期并在 7 天阈值前复检。"
        )


async def test_operator_opens_config_adoption_from_diagnostics_recommendation() -> None:
    adopter = RecordingConfigAdopter()
    app = ManagerApp(
        host_tools=ManagerAppHostTools(
            diagnostics_center=FixedDiagnosticsCenter(untracked_configuration_report()),
            config_adopter=adopter,
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-diagnostics-center")
        await pilot.pause()

        action = app.screen.query_one("#diagnostics-center-action", Button)
        assert str(action.label) == "审查并接管现有配置"
        assert not action.has_class("hidden")

        await pilot.click("#diagnostics-center-action")
        await pilot.pause()

        assert app.screen.query_one("#config-adoption-title", Static).content == (
            "确认现有配置接管计划"
        )
        assert app.screen.query_one("#config-adoption-fingerprint", Static).content == (
            f"当前配置 SHA-256：{'b' * 64}"
        )


async def test_operator_opens_trusted_core_update_from_diagnostics_recommendation() -> None:
    updater = NeverCalledCoreUpdater()
    app = ManagerApp(
        core_updater=updater,
        host_tools=ManagerAppHostTools(
            diagnostics_center=FixedDiagnosticsCenter(missing_core_report()),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-diagnostics-center")
        await pilot.pause()

        action = app.screen.query_one("#diagnostics-center-action", Button)
        assert str(action.label) == "安装或升级 sing-box 核心"
        assert not action.has_class("hidden")

        await pilot.click("#diagnostics-center-action")

        assert app.screen.query_one("#core-update-form-title", Static).content == (
            "安装或升级 sing-box 核心"
        )


async def test_operator_opens_one_prioritized_diagnostics_report_from_dashboard() -> None:
    center = FixedDiagnosticsCenter(report_with_actions())
    app = ManagerApp(host_tools=ManagerAppHostTools(diagnostics_center=center))

    async with app.run_test() as pilot:
        assert str(app.query_one("#open-diagnostics-center", Button).label) == ("打开诊断中心")

        await pilot.click("#open-diagnostics-center")
        await pilot.pause()

        assert center.calls == 1
        assert app.screen.query_one("#diagnostics-center-title", Static).content == ("诊断中心")
        assert app.screen.query_one("#diagnostics-center-summary", Static).content == (
            "整体状态：需要处理 1 项，注意 1 项"
        )
        assert (
            app.screen.query_one("#diagnostics-center-recommended-action", Static).content
            == "建议：运行 systemctl restart sing-box.service。"
        )
        assert app.screen.query_one("#diagnostic-runtime-title", Static).content == (
            "[需处理] sing-box 运行状态"
        )
        assert app.screen.query_one("#diagnostic-runtime-guidance", Static).content == (
            "下一步：运行 systemctl restart sing-box.service。"
        )


async def test_operator_rechecks_diagnostics_after_host_recovery() -> None:
    center = FixedDiagnosticsCenter(report_with_actions(), healthy_report())
    app = ManagerApp(host_tools=ManagerAppHostTools(diagnostics_center=center))

    async with app.run_test() as pilot:
        await pilot.click("#open-diagnostics-center")
        await pilot.pause()
        assert app.screen.query_one("#diagnostics-center-summary", Static).content == (
            "整体状态：需要处理 1 项，注意 1 项"
        )

        await pilot.click("#refresh-diagnostics-center")
        await pilot.pause()

        assert center.calls == REFRESHED_INSPECTION_COUNT
        assert app.screen.query_one("#diagnostics-center-summary", Static).content == (
            "整体状态：所有检查均正常"
        )
        assert app.screen.query_one("#diagnostic-runtime-title", Static).content == (
            "[正常] sing-box 运行状态"
        )
        assert (
            app.screen.query_one("#diagnostics-center-recommended-action", Static).content
            == "建议：当前无需处理，可以安全继续操作"
        )


async def test_diagnostics_center_keeps_retry_available_after_unexpected_failure() -> None:
    app = ManagerApp(host_tools=ManagerAppHostTools(diagnostics_center=FailingDiagnosticsCenter()))

    async with app.run_test() as pilot:
        await pilot.click("#open-diagnostics-center")
        await pilot.pause()

        assert app.screen.query_one("#diagnostics-center-loading", Static).content == (
            "无法完成诊断检查：unexpected diagnostics failure"
        )
        assert app.screen.query_one("#refresh-diagnostics-center", Button).disabled is False


async def test_dashboard_runtime_summary_uses_single_diagnostics_action() -> None:
    app = ManagerApp(
        host_tools=ManagerAppHostTools(
            host_diagnostics=HealthyHostDiagnostics(),
            diagnostics_center=FixedDiagnosticsCenter(healthy_report()),
        )
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.query_one("#runtime-status", Static).content == "服务状态：运行正常"
        assert len(app.query("#open-diagnostics-center")) == 1
        assert len(app.query("#view-diagnostics")) == 0


async def test_operator_drills_into_bounded_redacted_service_logs_and_refreshes() -> None:
    logs = RecordingServiceLogReader(
        ServiceLogReport(
            condition=ServiceLogCondition.AVAILABLE,
            source_label="systemd journal",
            lines=(
                "2026-07-17 sing-box started",
                "2026-07-17 rejected uuid=[已脱敏]",
            ),
            diagnostics="",
            redacted_occurrences=1,
            limit=200,
        ),
        ServiceLogReport(
            condition=ServiceLogCondition.EMPTY,
            source_label="systemd journal",
            lines=(),
            diagnostics="",
            redacted_occurrences=0,
            limit=200,
        ),
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(
            diagnostics_center=FixedDiagnosticsCenter(healthy_report()),
            service_log_reader=logs,
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-diagnostics-center")
        await pilot.pause()

        log_action = app.screen.query_one("#open-service-logs", Button)
        assert str(log_action.label) == "查看近期服务日志"
        await pilot.click("#open-service-logs")
        await pilot.pause()

        assert app.screen.query_one("#service-logs-title", Static).content == "近期服务日志"
        assert app.screen.query_one("#service-logs-safety", Static).content == (
            "只读 · 最多 200 行 · 自动清理控制字符并脱敏"
        )
        assert app.screen.query_one("#service-logs-source", Static).content == (
            "来源：systemd journal · 已脱敏 1 处"
        )
        assert app.screen.query_one("#service-logs-content", Static).content == (
            "2026-07-17 sing-box started\n2026-07-17 rejected uuid=[已脱敏]"
        )

        await pilot.click("#refresh-service-logs")
        await pilot.pause()

        assert logs.calls == REFRESHED_SERVICE_LOG_COUNT
        assert logs.limits == [200, 200]
        assert app.screen.query_one("#service-logs-content", Static).content == (
            "近期没有可显示的 sing-box 服务日志。"
        )


async def test_service_log_drill_down_explains_unavailable_source_and_keeps_retry() -> None:
    logs = RecordingServiceLogReader(
        ServiceLogReport(
            condition=ServiceLogCondition.UNAVAILABLE,
            source_label="OpenRC syslog",
            lines=(),
            diagnostics="logread: permission denied",
            redacted_occurrences=0,
            limit=200,
        )
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(
            diagnostics_center=FixedDiagnosticsCenter(healthy_report()),
            service_log_reader=logs,
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-diagnostics-center")
        await pilot.pause()
        await pilot.click("#open-service-logs")
        await pilot.pause()

        assert app.screen.query_one("#service-logs-source", Static).content == "来源：OpenRC syslog"
        assert app.screen.query_one("#service-logs-content", Static).content == (
            "无法读取服务日志：logread: permission denied"
        )
        assert app.screen.query_one("#refresh-service-logs", Button).disabled is False
