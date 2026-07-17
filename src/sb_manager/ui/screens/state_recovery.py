"""Explicit confirmation screen for restoring one reviewed desired-state backup."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.state_recovery import (
    RecoveryAvailability,
    StateRecoveryError,
    StateRecoveryManager,
    StateRecoveryPlan,
    StateRecoveryReport,
)
from sb_manager.seams.state_recovery import (
    StateRecoveryCommit,
    StateRecoverySourceError,
)
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen


class StateRecoveryPanel(Widget):
    """Render every non-healthy startup state without owning recovery policy."""

    def __init__(self, report: StateRecoveryReport) -> None:
        super().__init__(id="state-recovery")
        self.report = report

    def compose(self) -> ComposeResult:
        if self.report.availability is RecoveryAvailability.RECOVERY_AVAILABLE:
            assert self.report.plan is not None
            yield Static("desired state 无法读取", id="state-recovery-title")
            yield Static(
                f"可恢复备份：revision {self.report.plan.backup_revision} · "
                f"{self.report.plan.backup_profile_count} 个配置",
                id="state-recovery-backup",
            )
            yield Static(
                "恢复前会再次核对主文件和备份指纹，损坏原文件会被完整保留。",
                id="state-recovery-guidance",
            )
            yield Button(
                "审阅恢复计划",
                id="review-state-recovery",
                variant="warning",
            )
            return
        if self.report.availability is RecoveryAvailability.UNSUPPORTED_SCHEMA:
            yield Static("desired state 版本高于当前管理器", id="state-recovery-title")
            yield Static(
                f"检测到 schema {self.report.found_schema_version}。"
                "请使用兼容版本的管理器打开，当前版本不会覆盖该文件。",
                id="state-recovery-guidance",
            )
            return
        yield Static("desired state 无法读取", id="state-recovery-title")
        yield Static(
            "没有找到可验证的备份。当前版本不会覆盖主文件，请从外部备份恢复或检查文件权限。",
            id="state-recovery-guidance",
        )


class StateRecoveryInspectionErrorPanel(Widget):
    """Keep an unexpected startup inspection failure non-disclosing and read-only."""

    def __init__(self) -> None:
        super().__init__(id="state-recovery-inspection-error")

    def compose(self) -> ComposeResult:
        yield Static(
            "无法检查 desired state",
            id="state-recovery-inspection-error-title",
        )
        yield Static(
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。",
            id="state-recovery-inspection-error-details",
        )
        yield Static(
            "当前会话不会写入 desired state。请修复文件访问问题后重新启动 manager。",
            id="state-recovery-inspection-error-safety",
        )


class StateRecoveryConfirmationScreen(ConfirmedOperationScreen[StateRecoveryCommit | None]):
    """Keep destructive file replacement behind a second explicit action."""

    def __init__(
        self,
        recovery_manager: StateRecoveryManager,
        plan: StateRecoveryPlan,
    ) -> None:
        super().__init__()
        self.recovery_manager = recovery_manager
        self.plan = plan

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="state-recovery-confirmation"):
            yield Static("确认恢复 desired state", id="state-recovery-confirm-title")
            yield Static(
                f"备份：revision {self.plan.backup_revision} · "
                f"{self.plan.backup_profile_count} 个配置",
                id="state-recovery-confirm-backup",
            )
            yield Static(
                "将用已审阅备份替换损坏主文件，损坏原文件会被完整归档。",
                id="state-recovery-confirm-safety",
            )
            yield Static("", id="state-recovery-confirm-error", classes="hidden")
            yield Button(
                "确认并恢复",
                id="confirm-state-recovery",
                variant="warning",
            )
        yield Footer()

    @on(Button.Pressed, "#confirm-state-recovery")
    def confirm_recovery(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-state-recovery", Button).disabled = True
        self.query_one("#state-recovery-confirm-safety", Static).update(
            "操作已确认，正在恢复 desired state。完成前无法返回。"
        )
        self.execute_recovery()

    @work(thread=True, exclusive=True)
    def execute_recovery(self) -> None:
        try:
            result = self.recovery_manager.recover(self.plan, confirmed=True)
        except (StateRecoveryError, StateRecoverySourceError) as error:
            self.app.call_from_thread(self.show_error, str(error))
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                StateRecoveryOperationalErrorScreen(),
            )
            return
        self.app.call_from_thread(self.finish_recovery, result)

    def finish_recovery(self, result: StateRecoveryCommit) -> None:
        self.finish_confirmed_operation()
        self.dismiss(result)

    def show_error(self, diagnostics: str) -> None:
        self.finish_confirmed_operation()
        error = self.query_one("#state-recovery-confirm-error", Static)
        error.update(f"恢复未执行：{diagnostics}")
        error.remove_class("hidden")
        self.query_one("#confirm-state-recovery", Button).disabled = False


class StateRecoveryOperationalErrorScreen(Screen[None]):
    """Report an unknown desired-state recovery result without disclosure."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="state-recovery-operational-error"):
            yield Static(
                "无法确认 desired state 恢复结果",
                id="state-recovery-error-title",
            )
            yield Static(
                "发生意外错误。底层错误未显示，以避免泄露敏感信息。",
                id="state-recovery-error-details",
            )
            yield Static(
                "主文件、备份和损坏文件归档的结果均未知。"
                "请先只读检查这些文件的 SHA-256 和 revision，不要直接重试。",
                id="state-recovery-error-safety",
            )
        yield Footer()
