from typing import cast

from textual.widgets import Button, Static

from sb_manager.application.apply_history import ApplyHistoryCondition, ApplyHistoryReport
from sb_manager.application.core_update import (
    CoreUpdatePlan,
    CoreUpdateResult,
    PlanCoreUpdateRequest,
)
from sb_manager.application.service_logs import ServiceLogCondition, ServiceLogReport
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools, ManagerAppInterfaceTools
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class NeverCalledCoreUpdater:
    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        raise AssertionError("opening operations must not create a core update plan")

    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
        raise AssertionError("opening operations must not activate a core release")


class NeverReadServiceLogs:
    def read_recent(self, *, limit: int = 200) -> ServiceLogReport:
        raise AssertionError("opening operations must not read service logs")


class NeverReadApplyHistory:
    def read_recent(self, *, limit: int = 20) -> ApplyHistoryReport:
        raise AssertionError("opening operations must not read apply history")


class RecordingServiceLogs:
    def __init__(self) -> None:
        self.calls = 0

    def read_recent(self, *, limit: int = 200) -> ServiceLogReport:
        self.calls += 1
        return ServiceLogReport(
            condition=ServiceLogCondition.EMPTY,
            source_label="systemd journal",
            lines=(),
            diagnostics="",
            redacted_occurrences=0,
            limit=limit,
        )


class RecordingApplyHistory:
    def __init__(self) -> None:
        self.calls = 0

    def read_recent(self, *, limit: int = 20) -> ApplyHistoryReport:
        self.calls += 1
        return ApplyHistoryReport(
            condition=ApplyHistoryCondition.HEALTHY,
            summary="尚无配置应用记录",
            entries=(),
            diagnostics="没有执行过 live configuration 应用",
            guidance="",
            limit=limit,
        )


class ApplyHistoryMarkerCatalog:
    """Mark the copy policy that must survive the Operations drill-down."""

    def text(self, key: UiText, /, **values: object) -> str:
        markers = {
            "apply_history.title": "目录应用历史",
            "apply_history.empty": "目录尚无应用记录",
        }
        if marker := markers.get(key.value):
            return marker
        return SIMPLIFIED_CHINESE.text(key, **values)


async def test_dashboard_routes_core_management_through_operations() -> None:
    app = ManagerApp(core_updater=NeverCalledCoreUpdater())

    async with app.run_test():
        assert list(app.screen.query("#manage-core")) == []
        assert str(app.screen.query_one("#open-operations", Button).label) == "打开运维中心"


async def test_operations_shortcut_opens_the_workspace_instead_of_a_mutation_form() -> None:
    app = ManagerApp(core_updater=NeverCalledCoreUpdater())

    async with app.run_test() as pilot:
        await pilot.press("c")

        assert app.screen.query_one("#empty-state-title", Static).content == "尚未创建代理配置"

        await pilot.press("o")

        assert app.screen.query_one("#operations-title", Static).content == "运维中心"


async def test_operator_opens_one_capability_aware_operations_workspace() -> None:
    app = ManagerApp(
        core_updater=NeverCalledCoreUpdater(),
        host_tools=ManagerAppHostTools(
            service_log_reader=NeverReadServiceLogs(),
            apply_history_reader=NeverReadApplyHistory(),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")

        assert app.screen.query_one("#operations-title", Static).content == "运维中心"
        assert app.screen.query_one("#operations-safety", Static).content == (
            "进入工具不会修改主机; 任何变更仍需先预览计划并明确确认。"
        )
        assert str(app.screen.query_one("#manage-core", Button).label) == (
            "安装或升级 sing-box 核心"
        )
        assert str(app.screen.query_one("#open-service-logs", Button).label) == ("查看近期服务日志")
        assert str(app.screen.query_one("#open-apply-history", Button).label) == (
            "查看配置应用历史"
        )


async def test_operations_explains_capabilities_missing_from_the_current_mode() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")

        assert list(app.screen.query("#manage-core")) == []
        assert list(app.screen.query("#open-service-logs")) == []
        assert list(app.screen.query("#open-apply-history")) == []
        assert app.screen.query_one("#operations-core-unavailable", Static).content == (
            "当前启动模式未提供可信核心更新能力。"
        )
        assert app.screen.query_one("#operations-service-logs-unavailable", Static).content == (
            "当前启动模式未提供服务日志读取能力。"
        )
        assert app.screen.query_one("#operations-apply-history-unavailable", Static).content == (
            "当前启动模式未提供配置应用历史。"
        )


async def test_operator_opens_core_planning_from_operations_without_mutation() -> None:
    app = ManagerApp(core_updater=NeverCalledCoreUpdater())

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")
        await pilot.click("#manage-core")

        assert app.screen.query_one("#core-update-form-title", Static).content == (
            "安装或升级 sing-box 核心"
        )


async def test_operator_reads_service_logs_on_demand_from_operations() -> None:
    logs = RecordingServiceLogs()
    app = ManagerApp(host_tools=ManagerAppHostTools(service_log_reader=logs))

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")

        assert logs.calls == 0

        await pilot.click("#open-service-logs")
        await pilot.pause()

        assert app.screen.query_one("#service-logs-title", Static).content == "近期服务日志"
        assert logs.calls == 1


async def test_operator_reads_apply_history_on_demand_from_operations() -> None:
    history = RecordingApplyHistory()
    app = ManagerApp(host_tools=ManagerAppHostTools(apply_history_reader=history))

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")

        assert history.calls == 0

        await pilot.click("#open-apply-history")
        await pilot.pause()

        assert app.screen.query_one("#apply-history-title", Static).content == "配置应用历史"
        assert history.calls == 1


async def test_operations_preserves_copy_policy_when_opening_apply_history() -> None:
    history = RecordingApplyHistory()
    app = ManagerApp(
        host_tools=ManagerAppHostTools(apply_history_reader=history),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, ApplyHistoryMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")
        await pilot.click("#open-apply-history")
        await pilot.pause()

        assert app.screen.query_one("#apply-history-title", Static).content == "目录应用历史"
        assert app.screen.query_one("#apply-history-content", Static).content == (
            "目录尚无应用记录"
        )
