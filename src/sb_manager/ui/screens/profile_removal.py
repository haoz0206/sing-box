"""Complete Textual workflow for planned profile removal."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_removal import (
    ProfileRemovalNotFoundError,
    ProfileRemovalPlan,
    ProfileRemovalResult,
    ProfileRemovalScope,
    ProfileRemover,
)
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.transactions.apply import ApplyOutcome


class ProfileRemovalScreen(Screen[None]):
    """Show exact removal impact before exposing the destructive action."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "取消")]

    def __init__(self, profile_remover: ProfileRemover, *, profile_id: str) -> None:
        super().__init__()
        self.profile_remover = profile_remover
        self.plan: ProfileRemovalPlan = profile_remover.plan_removal(profile_id)

    def compose(self) -> ComposeResult:
        draft_only = self.plan.scope is ProfileRemovalScope.DESIRED_STATE_ONLY
        yield Header()
        with Vertical(id="profile-removal"):
            yield Static("确认移除配置", id="profile-removal-title")
            yield Static(f"配置：{self.plan.profile_name}", id="profile-removal-profile")
            yield Static(
                (
                    "只删除 manager 中的草案，不会修改 sing-box 配置或刷新服务。"
                    if draft_only
                    else "将生成不含此配置的完整 sing-box 配置，校验并刷新服务。失败时自动回滚。"
                ),
                id="profile-removal-impact",
            )
            yield Static(
                f"移除后保留 {self.plan.remaining_profile_count} 个配置，"
                f"其中 {self.plan.remaining_applied_count} 个已应用。",
                id="profile-removal-remaining",
            )
            yield Static("当前仅预览，尚未删除任何内容。", id="profile-removal-safety")
            yield Button(
                "确认移除草案" if draft_only else "确认下线并移除",
                id="confirm-profile-removal",
                variant="error",
            )
        yield Footer()

    @on(Button.Pressed, "#confirm-profile-removal")
    def confirm_removal(self) -> None:
        self.query_one("#confirm-profile-removal", Button).disabled = True
        self.query_one("#profile-removal-safety", Static).update(
            "正在执行已确认的移除计划，请勿关闭程序。"
        )
        self.execute_removal()

    @work(thread=True, exclusive=True)
    def execute_removal(self) -> None:
        try:
            result = self.profile_remover.remove_profile(self.plan, confirmed=True)
        except (
            ConfigurationApplyError,
            OSError,
            ProfileRemovalNotFoundError,
            StateRevisionConflictError,
        ) as error:
            self.app.call_from_thread(
                self.app.push_screen,
                ProfileRemovalOperationalErrorScreen(str(error)),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.app.push_screen,
                ProfileRemovalOperationalErrorScreen(),
            )
            return
        self.app.call_from_thread(
            self.app.push_screen,
            ProfileRemovalResultScreen(result),
        )


class ProfileRemovalResultScreen(Screen[None]):
    """Present the committed desired-state result of profile removal."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, result: ProfileRemovalResult) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        draft_only = self.result.scope is ProfileRemovalScope.DESIRED_STATE_ONLY
        yield Header()
        with Vertical(id="profile-removal-result"):
            if draft_only:
                yield Static("草案已移除", id="profile-removal-result-title")
                yield Static(
                    f"desired state 已提交 revision {self.result.committed_revision}。",
                    id="profile-removal-result-details",
                )
                yield Static(
                    "未修改 sing-box 配置，也未刷新服务。",
                    id="profile-removal-result-safety",
                )
            else:
                yield from self._compose_live_result()
            if self.result.committed_revision is not None:
                yield Button(
                    "返回仪表盘",
                    id="profile-removal-return-dashboard",
                    variant="primary",
                )
        yield Footer()

    @on(Button.Pressed, "#profile-removal-return-dashboard")
    async def return_to_dashboard(self) -> None:
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        await self.app.recompose()

    def _compose_live_result(self) -> ComposeResult:
        transaction = self.result.transaction
        if transaction is None:
            yield Static("无法确认移除结果", id="profile-removal-result-title")
            yield Static("未收到可信的 host transaction。", id="profile-removal-result-details")
            yield Static(
                "desired state 未提交，请先检查服务状态。",
                id="profile-removal-result-safety",
            )
            return
        if transaction.outcome is ApplyOutcome.APPLIED:
            yield Static("配置已下线并移除", id="profile-removal-result-title")
            yield Static(
                f"desired state 已提交 revision {self.result.committed_revision}。",
                id="profile-removal-result-details",
            )
            yield Static(
                "新配置已通过校验，服务刷新和健康检查已完成。",
                id="profile-removal-result-safety",
            )
            return
        if transaction.outcome is ApplyOutcome.VALIDATION_FAILED:
            yield Static("配置校验失败，未移除", id="profile-removal-result-title")
            yield Static(
                transaction.validation.diagnostics,
                id="profile-removal-result-details",
            )
            yield Static(
                "原有配置、服务和 desired state 均未改变。",
                id="profile-removal-result-safety",
            )
            return
        if transaction.outcome is ApplyOutcome.PRECONDITION_FAILED:
            yield Static("服务器配置已变化，未移除", id="profile-removal-result-title")
            yield Static(
                transaction.commit.diagnostics
                if transaction.commit is not None
                else "live configuration 不再匹配已确认的版本",
                id="profile-removal-result-details",
            )
            yield Static(
                "本次尚未写入配置，请重新检查后再确认。",
                id="profile-removal-result-safety",
            )
            return
        if transaction.outcome is ApplyOutcome.COMMIT_FAILED:
            yield Static("无法写入移除后的配置", id="profile-removal-result-title")
            yield Static(
                transaction.commit.diagnostics
                if transaction.commit is not None
                else "配置提交失败",
                id="profile-removal-result-details",
            )
            yield Static(
                "尚未刷新服务，原有配置和 desired state 保持不变。",
                id="profile-removal-result-safety",
            )
            return
        rollback = transaction.rollback
        if transaction.outcome is ApplyOutcome.ROLLED_BACK:
            yield Static("移除失败，已自动回滚", id="profile-removal-result-title")
            yield Static(
                rollback.diagnostics if rollback is not None else "旧配置已恢复。",
                id="profile-removal-result-details",
            )
            yield Static(
                "原有配置、服务和 desired state 已保留。",
                id="profile-removal-result-safety",
            )
            return
        yield Static("回滚未完成，需要人工恢复", id="profile-removal-result-title")
        yield Static(
            rollback.diagnostics if rollback is not None else "回滚状态未知",
            id="profile-removal-result-details",
        )
        yield Static(
            "desired state 未提交。完成恢复前不要再次修改配置。",
            id="profile-removal-result-safety",
        )
        if rollback is not None:
            for index, instruction in enumerate(rollback.recovery_instructions):
                yield Static(
                    f"{index + 1}. {instruction}",
                    id=f"profile-removal-recovery-step-{index}",
                )


class ProfileRemovalOperationalErrorScreen(Screen[None]):
    """Explain an unknown host result without claiming profile removal."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, diagnostics: str | None = None) -> None:
        super().__init__()
        self.diagnostics = diagnostics

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-removal-error"):
            yield Static("无法确认配置移除结果", id="profile-removal-error-title")
            yield Static(
                self.diagnostics or "发生意外错误。底层错误未显示，以避免泄露敏感信息。",
                id="profile-removal-error-details",
            )
            yield Static(
                (
                    "desired state 未提交。请检查 sing-box 服务和 helper 日志后再决定是否重试。"
                    if self.diagnostics is not None
                    else "服务器配置、服务和 desired state 的结果均未知。"
                    "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
                ),
                id="profile-removal-error-safety",
            )
        yield Footer()
