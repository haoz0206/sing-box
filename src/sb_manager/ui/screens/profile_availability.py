"""Textual plan, confirmation, and result workflow for pause/resume."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_availability import (
    ProfileAvailability,
    ProfileAvailabilityManager,
    ProfileAvailabilityNotFoundError,
    ProfileAvailabilityPlan,
    ProfileAvailabilityPlanChangedError,
    ProfileAvailabilityResult,
    ProfileResumePortUnavailableError,
)
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.transactions.apply import ApplyOutcome
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.messages import DashboardRefreshRequested


class ProfileAvailabilityPlanScreen(ConfirmedOperationScreen[None]):
    """Present the exact pause/resume impact before one explicit confirmation."""

    def __init__(
        self,
        manager: ProfileAvailabilityManager,
        *,
        plan: ProfileAvailabilityPlan,
    ) -> None:
        super().__init__()
        self.manager = manager
        self.plan = plan

    def compose(self) -> ComposeResult:
        pausing = self.plan.target is ProfileAvailability.PAUSED
        yield Header()
        with Vertical(id="profile-availability-plan"):
            yield Static(
                "确认暂停配置" if pausing else "确认恢复配置",
                id="profile-availability-plan-title",
            )
            yield Static(
                f"配置：{self.plan.profile_name}",
                id="profile-availability-plan-profile",
            )
            yield Static(
                (
                    "将从完整 sing-box 配置中移除此 inbound，保留 profile、端口和凭据。"
                    if pausing
                    else "将把此 inbound 恢复到完整 sing-box 配置，校验并刷新服务。"
                ),
                id="profile-availability-plan-impact",
            )
            yield Static(
                f"完成后在线配置数：{self.plan.remaining_active_profile_count}",
                id="profile-availability-plan-count",
            )
            yield Static("当前仅预览，尚未修改任何内容。", id="profile-availability-plan-safety")
            yield Button(
                "确认暂停" if pausing else "确认恢复",
                id="confirm-profile-availability",
                variant="warning",
            )
        yield Footer()

    @on(Button.Pressed, "#confirm-profile-availability")
    def confirm_change(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-profile-availability", Button).disabled = True
        self.query_one("#profile-availability-plan-safety", Static).update(
            "操作已确认，正在执行完整配置事务。完成前无法返回。"
        )
        self.execute_change()

    @work(thread=True, exclusive=True)
    def execute_change(self) -> None:
        try:
            result = self.manager.apply_change(self.plan, confirmed=True)
        except (
            ConfigurationApplyError,
            OSError,
            ProfileAvailabilityNotFoundError,
            ProfileAvailabilityPlanChangedError,
            ProfileResumePortUnavailableError,
            StateRevisionConflictError,
        ) as error:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileAvailabilityErrorScreen(str(error)),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileAvailabilityErrorScreen(),
            )
            return
        self.app.call_from_thread(
            self.push_terminal_screen,
            ProfileAvailabilityResultScreen(result),
        )


class ProfileAvailabilityResultScreen(Screen[None]):
    """Present committed availability or a transaction outcome without guessing."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, result: ProfileAvailabilityResult) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        committed = (
            self.result.committed_revision is not None
            and self.result.transaction.outcome is ApplyOutcome.APPLIED
        )
        yield Header()
        with Vertical(id="profile-availability-result"):
            if committed:
                yield Static(
                    (
                        "配置已暂停"
                        if self.result.availability is ProfileAvailability.PAUSED
                        else "配置已恢复"
                    ),
                    id="profile-availability-result-title",
                )
                yield Static(
                    f"desired state 已提交 revision {self.result.committed_revision}。",
                    id="profile-availability-result-details",
                )
                yield Static(
                    "完整配置已通过校验，服务刷新和健康检查已完成。",
                    id="profile-availability-result-safety",
                )
                yield Button(
                    "返回仪表盘",
                    id="profile-availability-return-dashboard",
                    variant="primary",
                )
            else:
                yield from self._compose_failed_result()
        yield Footer()

    def _compose_failed_result(self) -> ComposeResult:
        transaction = self.result.transaction
        if transaction.outcome is ApplyOutcome.VALIDATION_FAILED:
            yield Static(
                "配置校验失败，状态未改变",
                id="profile-availability-result-title",
            )
            yield Static(
                transaction.validation.diagnostics,
                id="profile-availability-result-details",
            )
            yield Static(
                "原有配置、服务和 desired state 均未改变。",
                id="profile-availability-result-safety",
            )
            return
        if transaction.outcome is ApplyOutcome.PRECONDITION_FAILED:
            yield Static(
                "服务器配置已变化，状态未改变",
                id="profile-availability-result-title",
            )
            yield Static(
                transaction.commit.diagnostics
                if transaction.commit is not None
                else "live configuration 不再匹配已确认的版本",
                id="profile-availability-result-details",
            )
            yield Static(
                "本次尚未写入配置，请重新检查后再确认。",
                id="profile-availability-result-safety",
            )
            return
        if transaction.outcome is ApplyOutcome.COMMIT_FAILED:
            yield Static(
                "无法写入状态变更后的配置",
                id="profile-availability-result-title",
            )
            yield Static(
                transaction.commit.diagnostics
                if transaction.commit is not None
                else "配置提交失败",
                id="profile-availability-result-details",
            )
            yield Static(
                "尚未刷新服务，原有配置和 desired state 保持不变。",
                id="profile-availability-result-safety",
            )
            return
        rollback = transaction.rollback
        if transaction.outcome is ApplyOutcome.ROLLED_BACK:
            yield Static(
                "状态变更失败，已自动回滚",
                id="profile-availability-result-title",
            )
            yield Static(
                rollback.diagnostics if rollback is not None else "旧配置已恢复。",
                id="profile-availability-result-details",
            )
            yield Static(
                "原有配置、服务和 desired state 已保留。",
                id="profile-availability-result-safety",
            )
            return
        yield Static("回滚未完成，需要人工恢复", id="profile-availability-result-title")
        yield Static(
            rollback.diagnostics if rollback is not None else "回滚状态未知",
            id="profile-availability-result-details",
        )
        yield Static(
            "desired state 未提交。完成恢复前不要再次修改配置。",
            id="profile-availability-result-safety",
        )
        if rollback is not None:
            for index, instruction in enumerate(rollback.recovery_instructions):
                yield Static(
                    f"{index + 1}. {instruction}",
                    id=f"profile-availability-recovery-step-{index}",
                )

    @on(Button.Pressed, "#profile-availability-return-dashboard")
    def return_to_dashboard(self) -> None:
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        self.app.post_message(DashboardRefreshRequested())


class ProfileAvailabilityErrorScreen(Screen[None]):
    """Conservatively report an unavailable or stale availability transition."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, diagnostics: str | None = None) -> None:
        super().__init__()
        self.diagnostics = diagnostics

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-availability-error"):
            yield Static("无法确认配置状态变更", id="profile-availability-error-title")
            yield Static(
                self.diagnostics or "发生意外错误。底层错误未显示，以避免泄露敏感信息。",
                id="profile-availability-error-details",
            )
            yield Static(
                (
                    "desired state 未提交。请重新打开配置详情并检查当前服务状态。"
                    if self.diagnostics is not None
                    else "服务器配置、服务和 desired state 的结果均未知。"
                    "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
                ),
                id="profile-availability-error-safety",
            )
        yield Footer()


class ProfileAvailabilityPlanningErrorScreen(Screen[None]):
    """Report an unexpected read-only availability-planning failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-availability-planning-error"):
            yield Static(
                "无法准备配置状态变更",
                id="profile-availability-planning-error-title",
            )
            yield Static(
                "读取暂停/恢复计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。",
                id="profile-availability-planning-error-details",
            )
            yield Static(
                "尚未执行任何操作。请返回配置列表，重新打开详情后再试。",
                id="profile-availability-planning-error-safety",
            )
        yield Footer()
