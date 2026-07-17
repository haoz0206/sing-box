from textual.widgets import Static

from sb_manager.application.core_update import (
    CoreUpdatePlan,
    CoreUpdateResult,
    PlanCoreUpdateRequest,
)
from sb_manager.application.diagnostics_center import DiagnosticsCenterReport
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools


class RecordingDiagnosticsCenter:
    def __init__(self) -> None:
        self.calls = 0

    def inspect(self) -> DiagnosticsCenterReport:
        self.calls += 1
        return DiagnosticsCenterReport(items=())


class NeverCalledCoreUpdater:
    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        raise AssertionError("opening the core form must not create a plan")

    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
        raise AssertionError("opening the core form must not activate a release")


async def test_operator_opens_keyboard_help_and_returns_to_the_dashboard() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.press("?")

        assert app.screen.query_one("#keyboard-help-title", Static).content == "键盘操作帮助"
        assert app.screen.query_one("#keyboard-help-safety", Static).content == (
            "快捷键只负责导航。应用配置、移除和升级仍需预览与明确确认。"
        )
        assert app.screen.query_one("#keyboard-help-dashboard", Static).content == (
            "a  添加配置\np  管理配置\nn  查看网络概览\nd  打开诊断中心\no  打开运维中心\nq  退出"
        )

        await pilot.press("escape")

        assert app.query_one("#empty-state-title", Static).content == "尚未创建代理配置"


async def test_dashboard_shortcuts_navigate_only_when_their_context_is_available() -> None:
    diagnostics = RecordingDiagnosticsCenter()
    app = ManagerApp(
        host_tools=ManagerAppHostTools(diagnostics_center=diagnostics),
    )

    async with app.run_test() as pilot:
        await pilot.press("a")

        assert app.screen.query_one("#profile-purpose-title", Static).content == "你主要想优化什么?"

        await pilot.press("d")

        assert app.screen.query_one("#profile-purpose-title", Static).content == "你主要想优化什么?"
        assert diagnostics.calls == 0

        await pilot.press("n")

        assert app.screen.query_one("#profile-purpose-title", Static).content == "你主要想优化什么?"

        await pilot.press("escape")
        await pilot.press("d")
        await pilot.pause()

        assert app.screen.query_one("#diagnostics-center-title", Static).content == "诊断中心"
        assert diagnostics.calls == 1


async def test_operations_shortcut_opens_the_non_mutating_workspace() -> None:
    app = ManagerApp(core_updater=NeverCalledCoreUpdater())

    async with app.run_test() as pilot:
        await pilot.press("o")

        assert app.screen.query_one("#operations-title", Static).content == "运维中心"


async def test_quit_shortcut_is_reserved_for_the_root_dashboard() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.press("q")

        assert app.is_running
        assert app.screen.query_one("#profile-purpose-title", Static).content == "你主要想优化什么?"

        await pilot.press("escape")
        await pilot.press("q")
        await pilot.pause()

        assert not app.is_running
