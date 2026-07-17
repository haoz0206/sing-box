"""Review-only confirmation for resetting unreadable interface preferences."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.interface_preferences import (
    InterfacePreferenceService,
    PreferenceResetConflictError,
    PreferenceResetPlan,
    PreferenceResetResult,
    PreferenceStoreError,
)
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen


class PreferenceResetConfirmationScreen(ConfirmedOperationScreen[PreferenceResetResult | None]):
    """Show one hash-bound preference reset before any filesystem write."""

    def __init__(
        self,
        preference_service: InterfacePreferenceService,
        plan: PreferenceResetPlan,
    ) -> None:
        super().__init__()
        self.preference_service = preference_service
        self.plan = plan

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="preference-reset-confirmation"):
            yield Static("确认重置界面偏好", id="preference-reset-title", markup=False)
            yield Static(
                f"待替换文件 SHA-256：{self.plan.expected_sha256}",
                id="preference-reset-fingerprint",
                markup=False,
            )
            yield Static(
                "重置结果：schema v1 · 深色外观",
                id="preference-reset-default",
                markup=False,
            )
            yield Static(
                "确认后会先归档原字节，再只替换当前用户的界面偏好。"
                "不会修改 desired state、live configuration 或主机。",
                id="preference-reset-safety",
                markup=False,
            )
            yield Static("", id="preference-reset-error", classes="hidden", markup=False)
            yield Button(
                "确认并重置",
                id="confirm-preference-reset",
                variant="warning",
            )
        yield Footer()

    @on(Button.Pressed, "#confirm-preference-reset")
    def confirm_reset(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-preference-reset", Button).disabled = True
        self.query_one("#preference-reset-safety", Static).update(
            "操作已确认，正在归档并重置界面偏好。完成前无法返回。"
        )
        self.execute_reset()

    @work(thread=True, exclusive=True)
    def execute_reset(self) -> None:
        try:
            result = self.preference_service.reset(self.plan, confirmed=True)
        except PreferenceResetConflictError:
            self.app.call_from_thread(self.show_conflict)
            return
        except PreferenceStoreError:
            self.app.call_from_thread(self.show_error)
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                PreferenceResetOperationalErrorScreen(),
            )
            return
        self.app.call_from_thread(self.finish_reset, result)

    def finish_reset(self, result: PreferenceResetResult) -> None:
        self.finish_confirmed_operation()
        self.dismiss(result)

    def show_conflict(self) -> None:
        self.finish_confirmed_operation()
        error = self.query_one("#preference-reset-error", Static)
        error.update("偏好文件在审阅后已变化，未覆盖任何内容。请返回设置重新审查。")
        error.remove_class("hidden")

    def show_error(self) -> None:
        self.finish_confirmed_operation()
        error = self.query_one("#preference-reset-error", Static)
        error.update("无法安全归档或写入偏好文件。请检查路径和权限后重新审查。")
        error.remove_class("hidden")
        self.query_one("#confirm-preference-reset", Button).disabled = False


class PreferenceResetPlanningErrorScreen(Screen[None]):
    """Keep an unexpected or unsafe reset candidate non-disclosing."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="preference-reset-planning-error"):
            yield Static("无法准备界面偏好重置", id="preference-reset-planning-error-title")
            yield Static(
                "偏好文件无法安全读取或不是普通文件，底层错误和文件内容均未显示。",
                id="preference-reset-planning-error-details",
                markup=False,
            )
            yield Static(
                "尚未替换或删除任何内容。请检查偏好路径、权限或符号链接后重新打开设置。",
                id="preference-reset-planning-error-safety",
                markup=False,
            )
        yield Footer()


class PreferenceResetOperationalErrorScreen(Screen[None]):
    """Report an unknown local preference-reset result without disclosure."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="preference-reset-operational-error"):
            yield Static("无法确认界面偏好重置结果", id="preference-reset-operational-title")
            yield Static(
                "发生意外错误，底层错误和偏好文件内容均未显示。",
                id="preference-reset-operational-details",
                markup=False,
            )
            yield Static(
                "当前偏好文件或归档可能已经写入。请重新启动 manager 只读检查后再决定是否重试。",
                id="preference-reset-operational-safety",
                markup=False,
            )
        yield Footer()
