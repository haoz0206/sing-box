from textual.widgets import Button, Static

from sb_manager.application.diagnostics_center import (
    DiagnosticCode,
    DiagnosticCondition,
    DiagnosticItem,
    DiagnosticsCenterReport,
)
from sb_manager.application.host_diagnostics import (
    HostCondition,
    HostDiagnosticsReport,
)
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools

REFRESHED_INSPECTION_COUNT = 2


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


class HealthyHostDiagnostics:
    def inspect(self) -> HostDiagnosticsReport:
        return HostDiagnosticsReport(
            condition=HostCondition.HEALTHY,
            summary="sing-box 服务运行正常",
            diagnostics="active",
            recovery_instructions=(),
        )


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
