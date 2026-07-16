"""Complete exact-version core update workflow behind one screen interface."""

from typing import ClassVar, cast

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select, Static

from sb_manager.application.core_update import (
    CoreArtifactAcquisitionError,
    CorePrereleaseConsentRequiredError,
    CoreUpdatePlan,
    CoreUpdater,
    CoreUpdateResult,
    PlanCoreUpdateRequest,
)
from sb_manager.seams.artifact_source import ArtifactArchitecture
from sb_manager.seams.core_activator import CoreActivationError


class _CoreUpdateResultScreen(Screen[None]):
    """Present the complete evidence returned by a successful activation."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, result: CoreUpdateResult) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        activation = self.result.activation
        yield Header()
        with Vertical(id="core-update-result"):
            yield Static("sing-box 核心已激活", id="core-update-result-title")
            yield Static(f"版本：{activation.version}", id="core-update-result-version")
            yield Static(f"当前二进制：{activation.binary_path}", id="core-update-result-binary")
            yield Static(
                f"激活目标：{activation.activated_target}",
                id="core-update-result-target",
            )
            yield Static(
                f"上一个激活目标：{activation.previous_target or '无'}",
                id="core-update-result-previous",
            )
        yield Footer()


class _CoreUpdateErrorScreen(Screen[None]):
    """Distinguish acquisition failure from an unknown privileged host result."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, diagnostics: str, *, host_result_unknown: bool) -> None:
        super().__init__()
        self.diagnostics = diagnostics
        self.host_result_unknown = host_result_unknown

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-update-error"):
            yield Static(
                "无法确认核心激活结果" if self.host_result_unknown else "核心下载或校验失败",
                id="core-update-error-title",
            )
            yield Static(self.diagnostics, id="core-update-error-details")
            yield Static(
                (
                    "请检查 current 链接、helper 日志和 sing-box 版本，再决定是否重试。"
                    if self.host_result_unknown
                    else "尚未请求特权激活，当前核心保持不变。"
                ),
                id="core-update-error-safety",
            )
        yield Footer()


class _CoreUpdatePlanScreen(Screen[None]):
    """Show an immutable artifact plan and require explicit host-mutation consent."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回修改")]

    def __init__(self, core_updater: CoreUpdater, plan: CoreUpdatePlan) -> None:
        super().__init__()
        self.core_updater = core_updater
        self.plan = plan

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-update-plan"):
            yield Static("确认核心更新计划", id="core-update-plan-title")
            yield Static(f"版本：{self.plan.version}", id="core-update-plan-version")
            yield Static(
                f"架构：{self.plan.architecture.value}",
                id="core-update-plan-architecture",
            )
            yield Static(f"发行资产：{self.plan.asset_name}", id="core-update-plan-asset")
            yield Static(f"来源：{self.plan.source}", id="core-update-plan-source")
            for index, warning in enumerate(self.plan.warnings):
                yield Static(warning, id=f"core-update-warning-{index}")
            yield Static(
                "当前仅预览; 尚未下载文件，也不会修改服务器。",
                id="core-update-plan-safety",
            )
            yield Static("", id="core-update-progress")
            yield Button("确认下载并激活", id="confirm-core-update", variant="error")
        yield Footer()

    @on(Button.Pressed, "#confirm-core-update")
    def confirm_core_update(self) -> None:
        self.query_one("#confirm-core-update", Button).disabled = True
        self.query_one("#core-update-progress", Static).update(
            "正在下载、校验并激活; 请勿关闭程序。"
        )
        self.execute_core_update()

    @work(thread=True, exclusive=True)
    def execute_core_update(self) -> None:
        try:
            result = self.core_updater.execute(self.plan, confirmed=True)
        except CoreArtifactAcquisitionError as error:
            self.app.call_from_thread(
                self.app.push_screen,
                _CoreUpdateErrorScreen(str(error), host_result_unknown=False),
            )
            return
        except CoreActivationError as error:
            self.app.call_from_thread(
                self.app.push_screen,
                _CoreUpdateErrorScreen(str(error), host_result_unknown=True),
            )
            return
        self.app.call_from_thread(self.app.push_screen, _CoreUpdateResultScreen(result))


class CoreUpdateFormScreen(Screen[None]):
    """Collect, plan, confirm, and execute one exact core version update."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, core_updater: CoreUpdater) -> None:
        super().__init__()
        self.core_updater = core_updater

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-update-form"):
            yield Static("安装或升级 sing-box 核心", id="core-update-form-title")
            yield Static("只接受官方 immutable release 的精确版本。")
            yield Label("精确版本", classes="field-label")
            yield Input(
                placeholder="精确版本，例如 1.14.0-alpha.45",
                id="core-version",
            )
            yield Label("服务器架构", classes="field-label")
            yield Select(
                (
                    ("x86-64 (amd64)", ArtifactArchitecture.AMD64),
                    ("ARM64 (arm64)", ArtifactArchitecture.ARM64),
                ),
                value=ArtifactArchitecture.AMD64,
                allow_blank=False,
                id="core-architecture",
            )
            yield Checkbox("我接受预发布版本的兼容性风险", id="allow-prerelease")
            yield Static("", id="core-update-form-error", classes="field-error")
            yield Button("预览核心更新计划", id="preview-core-update", variant="primary")
        yield Footer()

    @on(Button.Pressed, "#preview-core-update")
    def preview_core_update(self) -> None:
        version = self.query_one("#core-version", Input).value.strip()
        architecture = cast(
            Select[ArtifactArchitecture],
            self.query_one("#core-architecture", Select),
        ).value
        error = self.query_one("#core-update-form-error", Static)
        error.update("")
        if not isinstance(architecture, ArtifactArchitecture):
            error.update("请选择服务器架构")
            return
        try:
            plan = self.core_updater.plan(
                PlanCoreUpdateRequest(
                    version=version,
                    architecture=architecture,
                    allow_prerelease=self.query_one("#allow-prerelease", Checkbox).value,
                )
            )
        except (ValueError, CorePrereleaseConsentRequiredError) as plan_error:
            error.update(str(plan_error))
            return
        self.app.push_screen(_CoreUpdatePlanScreen(self.core_updater, plan))
