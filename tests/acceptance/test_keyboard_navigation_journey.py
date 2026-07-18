from threading import Event
from typing import cast

from textual.widgets import Input, Static

from sb_manager.application.core_update import (
    CoreUpdatePlan,
    CoreUpdateResult,
    PlanCoreUpdateRequest,
)
from sb_manager.application.diagnostics_center import DiagnosticsCenterReport
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    CoreArtifactTrustMode,
    PlannedCoreArtifact,
)
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools, ManagerAppInterfaceTools
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class KeyboardHelpMarkerCatalog:
    """Render markers for Keyboard Help while delegating established copy."""

    def text(self, key: UiText, /, **values: object) -> str:
        markers = {
            "keyboard_help.title": "目录键盘帮助",
            "keyboard_help.navigation.title": "目录通用导航",
            "keyboard_help.navigation": "目录全局帮助入口",
            "keyboard_help.dashboard.title": "目录仪表盘快捷键",
            "keyboard_help.dashboard": "目录上下文动作",
            "keyboard_help.context": "目录输入焦点说明",
            "keyboard_help.safety": "目录导航不执行变更",
        }
        if marker := markers.get(key.value):
            return marker
        return SIMPLIFIED_CHINESE.text(key, **values)


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


class BlockingCoreUpdater:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        asset_name = f"sing-box-{request.version}-linux-amd64.tar.gz"
        return CoreUpdatePlan(
            artifact=PlannedCoreArtifact(
                version=request.version,
                architecture=ArtifactArchitecture.AMD64,
                asset_name=asset_name,
                download_url=(
                    "https://github.com/SagerNet/sing-box/releases/download/"
                    f"v{request.version}/{asset_name}"
                ),
                sha256="a" * 64,
                trust_mode=CoreArtifactTrustMode.IMMUTABLE_RELEASE,
                release_immutable=True,
                prerelease=False,
            ),
            mutates_host=False,
            warnings=(),
            expected_state_revision=3,
        )

    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
        assert confirmed
        self.started.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test did not release the core update")
        raise RuntimeError("synthetic terminal result")


async def test_operator_opens_keyboard_help_and_returns_to_the_dashboard() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.press("?")

        assert app.screen.query_one("#keyboard-help-title", Static).content == "键盘操作帮助"
        assert app.screen.query_one("#keyboard-help-safety", Static).content == (
            "快捷键只负责导航。应用配置、移除和升级仍需预览与明确确认。"
        )
        assert app.screen.query_one("#keyboard-help-dashboard", Static).content == (
            "a  添加配置\np  管理配置\nn  查看网络概览\ns  打开设置\n"
            "d  打开诊断中心\no  打开运维中心\nq  退出"
        )

        await pilot.press("escape")

        assert app.query_one("#empty-state-title", Static).content == "尚未创建代理配置"


async def test_keyboard_help_copy_comes_from_the_interface_catalog() -> None:
    app = ManagerApp(
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, KeyboardHelpMarkerCatalog()),
        )
    )

    async with app.run_test() as pilot:
        await pilot.press("?")

        assert app.screen.query_one("#keyboard-help-title", Static).content == "目录键盘帮助"
        assert app.screen.query_one("#keyboard-help-safety", Static).content == (
            "目录导航不执行变更"
        )
        assert app.screen.query_one("#keyboard-help-navigation-title", Static).content == (
            "目录通用导航"
        )
        assert app.screen.query_one("#keyboard-help-navigation", Static).content == (
            "目录全局帮助入口"
        )
        assert app.screen.query_one("#keyboard-help-dashboard-title", Static).content == (
            "目录仪表盘快捷键"
        )
        assert app.screen.query_one("#keyboard-help-dashboard", Static).content == (
            "目录上下文动作"
        )
        assert app.screen.query_one("#keyboard-help-context", Static).content == (
            "目录输入焦点说明"
        )


async def test_f1_opens_help_from_a_focused_form_and_returns_to_the_same_input() -> None:
    app = ManagerApp(core_updater=NeverCalledCoreUpdater())

    async with app.run_test() as pilot:
        await pilot.press("o")
        await pilot.click("#manage-core")
        await pilot.click("#core-version")
        await pilot.press("1", ".", "1", "4", ".", "0")

        await pilot.press("?")

        version = app.screen.query_one("#core-version", Input)
        assert version.value == "1.14.0?"
        await pilot.press("backspace")

        await pilot.press("f1")

        assert app.screen.query_one("#keyboard-help-title", Static).content == "键盘操作帮助"

        await pilot.press("escape")

        version = app.screen.query_one("#core-version", Input)
        assert version.value == "1.14.0"
        assert version.has_focus


async def test_help_shortcuts_do_not_stack_duplicate_help_screens() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.press("f1")
        await pilot.press("?")
        await pilot.press("escape")

        assert app.screen.query_one("#empty-state-title", Static).content == ("尚未创建代理配置")


async def test_f1_does_not_hide_confirmed_operation_progress() -> None:
    updater = BlockingCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await pilot.press("o")
        await pilot.click("#manage-core")
        await pilot.click("#core-version")
        await pilot.press("1", ".", "1", "4", ".", "0")
        await pilot.click("#preview-core-update")
        await pilot.click("#confirm-core-update")
        assert updater.started.wait(timeout=1)

        try:
            await pilot.press("f1")

            assert app.screen.query_one("#core-update-plan-title", Static).content == (
                "确认核心更新计划"
            )
        finally:
            updater.release.set()
            await pilot.pause()


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

        await pilot.press("s")

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
