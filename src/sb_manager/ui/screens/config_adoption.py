"""Explicit existing-configuration adoption workflow behind one screen interface."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.config_adoption import (
    ConfigAdopter,
    ConfigAdoptionError,
    ConfigAdoptionPlan,
    ConfigAdoptionResult,
)
from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.seams.config_target import ConfigTargetInspectionError


class _ConfigAdoptionResultScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, result: ConfigAdoptionResult) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-adoption-result"):
            yield Static(
                "现有配置已被记录为替换前置条件",
                id="config-adoption-result-title",
            )
            yield Static(
                f"desired state revision {self.result.committed_revision}",
                id="config-adoption-result-revision",
            )
            yield Static(
                "服务器配置没有改变。下一次应用会先核对已记录指纹。",
                id="config-adoption-result-safety",
            )
        yield Footer()


class _ConfigAdoptionErrorScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, diagnostics: str) -> None:
        super().__init__()
        self.diagnostics = diagnostics

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-adoption-error"):
            yield Static("无法接管现有配置", id="config-adoption-error-title")
            yield Static(self.diagnostics, id="config-adoption-error-details")
            yield Static(
                "服务器配置和 desired state 均未改变。请重新检查后再试。",
                id="config-adoption-error-safety",
            )
        yield Footer()


class ConfigAdoptionScreen(Screen[None]):
    """Inspect, review, recheck, and record one exact live config identity."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "取消")]

    def __init__(self, config_adopter: ConfigAdopter) -> None:
        super().__init__()
        self.config_adopter = config_adopter
        self.plan: ConfigAdoptionPlan | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-adoption"):
            yield Static("正在检查现有配置…", id="config-adoption-title")
            yield Static("", id="config-adoption-fingerprint", classes="hidden")
            yield Static("", id="config-adoption-safety", classes="hidden")
            yield Button(
                "确认接管此配置",
                id="confirm-config-adoption",
                classes="hidden",
                variant="warning",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.load_plan()

    @work(thread=True, exclusive=True)
    def load_plan(self) -> None:
        try:
            plan = self.config_adopter.plan()
        except (ConfigAdoptionError, ConfigTargetInspectionError) as error:
            self.app.call_from_thread(
                self.app.push_screen,
                _ConfigAdoptionErrorScreen(str(error)),
            )
            return
        self.app.call_from_thread(self.show_plan, plan)

    def show_plan(self, plan: ConfigAdoptionPlan) -> None:
        self.plan = plan
        self.query_one("#config-adoption-title", Static).update("确认现有配置接管计划")
        fingerprint = self.query_one("#config-adoption-fingerprint", Static)
        fingerprint.update(f"当前配置 SHA-256：{plan.config_sha256}")
        fingerprint.remove_class("hidden")
        safety = self.query_one("#config-adoption-safety", Static)
        safety.update("接管不会修改服务器，也不会把现有 JSON 导入为 profile。")
        safety.remove_class("hidden")
        self.query_one("#confirm-config-adoption", Button).remove_class("hidden")

    @on(Button.Pressed, "#confirm-config-adoption")
    def confirm_adoption(self) -> None:
        if self.plan is None:
            return
        self.query_one("#confirm-config-adoption", Button).disabled = True
        self.execute_adoption(self.plan)

    @work(thread=True, exclusive=True)
    def execute_adoption(self, plan: ConfigAdoptionPlan) -> None:
        try:
            result = self.config_adopter.adopt(plan, confirmed=True)
        except (
            ConfigAdoptionError,
            ConfigTargetInspectionError,
            StateRevisionConflictError,
        ) as error:
            self.app.call_from_thread(
                self.app.push_screen,
                _ConfigAdoptionErrorScreen(str(error)),
            )
            return
        self.app.call_from_thread(self.app.push_screen, _ConfigAdoptionResultScreen(result))
