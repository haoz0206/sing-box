"""Complete Textual workflow for editing operator-facing profile metadata."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_details import ProfileDetails
from sb_manager.application.profile_editing import (
    PlanProfileEditRequest,
    ProfileEditNoChangesError,
    ProfileEditNotFoundError,
    ProfileEditor,
    ProfileEditPlan,
    ProfileEditPlanChangedError,
    ProfileEditPortUnavailableError,
    ProfileEditResult,
    ProfileEditScope,
    ProfileEditValidationError,
)
from sb_manager.domain.installation import PortSelection
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.transactions.apply import ApplyOutcome
from sb_manager.ui.messages import DashboardRefreshRequested


class ProfileEditFormScreen(Screen[None]):
    """Collect editable metadata without creating a plan on navigation."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "取消")]

    def __init__(self, profile_editor: ProfileEditor, *, details: ProfileDetails) -> None:
        super().__init__()
        self.profile_editor = profile_editor
        self.details = details

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profile-edit"):
            yield Static("编辑配置", id="profile-edit-title")
            yield Static(
                "稳定 ID、协议和凭据保持不变。提交前会显示影响计划。",
                id="profile-edit-guidance",
            )
            yield Label("配置名称", id="profile-edit-name-label")
            yield Input(value=self.details.profile_name, id="profile-edit-name")
            yield Label("公开服务器地址 (可留空)", id="profile-edit-server-address-label")
            yield Input(
                value=self.details.server_address or "",
                id="profile-edit-server-address",
            )
            yield Label("监听端口 (可留空)", id="profile-edit-listen-port-label")
            yield Input(
                value=(
                    str(self.details.listen_port) if self.details.listen_port is not None else ""
                ),
                placeholder="留空自动选择",
                id="profile-edit-listen-port",
            )
            yield Static(
                "留空表示自动选择。已应用配置会在确认后选择端口并执行完整事务。",
                id="profile-edit-port-guidance",
            )
            yield Static("", id="profile-edit-error")
            yield Button("预览变更", id="preview-profile-edit", variant="primary")
        yield Footer()

    @on(Button.Pressed, "#preview-profile-edit")
    def preview_edit(self) -> None:
        listen_port_input = self.query_one("#profile-edit-listen-port", Input)
        listen_port_text = listen_port_input.value.strip()
        try:
            listen_port = int(listen_port_text) if listen_port_text else None
        except ValueError:
            self.query_one("#profile-edit-error", Static).update(
                "端口必须是 1 到 65535 之间的整数，或留空自动选择"
            )
            listen_port_input.focus()
            return
        try:
            plan = self.profile_editor.plan_edit(
                PlanProfileEditRequest(
                    profile_id=self.details.profile_id,
                    profile_name=self.query_one("#profile-edit-name", Input).value,
                    server_address=self.query_one("#profile-edit-server-address", Input).value,
                    listen_port=listen_port,
                )
            )
        except ProfileEditValidationError as error:
            self.query_one("#profile-edit-error", Static).update(error.message)
            self.query_one(f"#profile-edit-{error.field.removeprefix('profile_')}").focus()
            return
        except ProfileEditNoChangesError:
            self.query_one("#profile-edit-error", Static).update("没有可保存的变更")
            return
        except ProfileEditNotFoundError:
            self.query_one("#profile-edit-error", Static).update(
                "配置可能已被另一个会话移除，请返回后重新打开列表。"
            )
            return
        except Exception:
            self.app.push_screen(ProfileEditPlanningErrorScreen())
            return
        self.app.push_screen(ProfileEditPlanScreen(self.profile_editor, plan=plan))


class ProfileEditPlanningErrorScreen(Screen[None]):
    """Report an unexpected read-only edit-planning failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-edit-planning-error"):
            yield Static("无法准备配置编辑", id="profile-edit-planning-error-title")
            yield Static(
                "读取配置编辑计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。",
                id="profile-edit-planning-error-details",
            )
            yield Static(
                "尚未执行任何操作。请返回配置列表，重新打开详情后再试。",
                id="profile-edit-planning-error-safety",
            )
        yield Footer()


class ProfileEditPlanScreen(Screen[None]):
    """Present exact normalized changes and their host impact."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "取消")]

    def __init__(self, profile_editor: ProfileEditor, *, plan: ProfileEditPlan) -> None:
        super().__init__()
        self.profile_editor = profile_editor
        self.plan = plan

    def compose(self) -> ComposeResult:
        changes: list[str] = []
        if "profile_name" in self.plan.changed_fields:
            changes.append(f"名称：{self.plan.previous_profile_name} → {self.plan.profile_name}")
        if "server_address" in self.plan.changed_fields:
            changes.append(
                "公开地址："
                f"{self.plan.previous_server_address or '未设置'} → "
                f"{self.plan.server_address or '未设置'}"
            )
        if "listen_port" in self.plan.changed_fields:
            changes.append(
                "监听端口："
                f"{self.plan.previous_listen_port or '自动选择'} → "
                f"{self.plan.listen_port or '自动选择 - 确认时'}"
            )
        if "port_selection" in self.plan.changed_fields:
            changes.append(
                "端口策略："
                f"{self._port_selection_label(self.plan.previous_port_selection)}"
                " → "
                f"{self._port_selection_label(self.plan.port_selection)}"
            )
        desired_only = self.plan.scope is ProfileEditScope.DESIRED_STATE_ONLY
        yield Header()
        with Vertical(id="profile-edit-plan"):
            yield Static("确认配置变更", id="profile-edit-plan-title")
            yield Static("\n".join(changes), id="profile-edit-plan-changes")
            yield Static(
                (
                    "只更新 manager desired state，不会写入 sing-box 配置或刷新服务。"
                    if desired_only
                    else "将生成完整 sing-box 配置，校验并刷新服务，失败时自动回滚。"
                ),
                id="profile-edit-plan-impact",
            )
            yield Static("当前仅预览，尚未修改任何内容。", id="profile-edit-plan-safety")
            yield Button(
                "确认保存" if desired_only else "确认修改并应用",
                id="confirm-profile-edit",
                variant="warning" if desired_only else "error",
            )
        yield Footer()

    @staticmethod
    def _port_selection_label(selection: PortSelection) -> str:
        return "自动选择" if selection is PortSelection.AUTOMATIC else "固定"

    @on(Button.Pressed, "#confirm-profile-edit")
    def confirm_edit(self) -> None:
        self.query_one("#confirm-profile-edit", Button).disabled = True
        self.query_one("#profile-edit-plan-safety", Static).update(
            "正在执行已确认的配置变更，请勿关闭程序。"
        )
        self.execute_edit()

    @work(thread=True, exclusive=True)
    def execute_edit(self) -> None:
        try:
            result = self.profile_editor.apply_edit(self.plan, confirmed=True)
        except ProfileEditPortUnavailableError as error:
            self.app.call_from_thread(
                self.app.push_screen,
                ProfileEditPortConflictScreen(str(error)),
            )
            return
        except (
            ProfileEditNoChangesError,
            ProfileEditNotFoundError,
            ProfileEditPlanChangedError,
            StateRevisionConflictError,
        ) as error:
            self.app.call_from_thread(
                self.app.push_screen,
                ProfileEditConflictScreen(str(error)),
            )
            return
        except (
            ConfigurationApplyError,
            OSError,
            ProfileEditValidationError,
        ) as error:
            self.app.call_from_thread(
                self.app.push_screen,
                ProfileEditOperationalErrorScreen(str(error)),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.app.push_screen,
                ProfileEditOperationalErrorScreen(),
            )
            return
        self.app.call_from_thread(
            self.app.push_screen,
            ProfileEditResultScreen(result),
        )


class ProfileEditResultScreen(Screen[None]):
    """Present the committed desired-state result of profile editing."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, result: ProfileEditResult) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-edit-result"):
            if self.result.scope is ProfileEditScope.DESIRED_STATE_ONLY:
                yield Static("配置已更新", id="profile-edit-result-title")
                yield Static(
                    f"desired state 已提交 revision {self.result.committed_revision}。",
                    id="profile-edit-result-details",
                )
                yield Static(
                    "未写入 sing-box 配置，也未刷新服务。",
                    id="profile-edit-result-safety",
                )
            elif (
                self.result.transaction is not None
                and self.result.transaction.outcome is ApplyOutcome.APPLIED
            ):
                yield Static("配置已应用并更新", id="profile-edit-result-title")
                yield Static(
                    f"desired state 已提交 revision {self.result.committed_revision}。",
                    id="profile-edit-result-details",
                )
                yield Static(
                    "新配置已通过校验，服务刷新和健康检查已完成。",
                    id="profile-edit-result-safety",
                )
            elif (
                self.result.transaction is not None
                and self.result.transaction.outcome is ApplyOutcome.VALIDATION_FAILED
            ):
                yield Static("配置校验失败，未更新", id="profile-edit-result-title")
                yield Static(
                    self.result.transaction.validation.diagnostics,
                    id="profile-edit-result-details",
                )
                yield Static(
                    "原有配置、服务和 desired state 均未改变。",
                    id="profile-edit-result-safety",
                )
            elif (
                self.result.transaction is not None
                and self.result.transaction.outcome is ApplyOutcome.PRECONDITION_FAILED
            ):
                yield Static("服务器配置已变化，未更新", id="profile-edit-result-title")
                yield Static(
                    (
                        self.result.transaction.commit.diagnostics
                        if self.result.transaction.commit is not None
                        else "live configuration 不再匹配已确认的版本"
                    ),
                    id="profile-edit-result-details",
                )
                yield Static(
                    "本次尚未写入配置，请重新检查后再确认。",
                    id="profile-edit-result-safety",
                )
            elif (
                self.result.transaction is not None
                and self.result.transaction.outcome is ApplyOutcome.COMMIT_FAILED
            ):
                yield Static("无法写入编辑后的配置", id="profile-edit-result-title")
                yield Static(
                    (
                        self.result.transaction.commit.diagnostics
                        if self.result.transaction.commit is not None
                        else "配置提交失败"
                    ),
                    id="profile-edit-result-details",
                )
                yield Static(
                    "尚未刷新服务，原有配置和 desired state 保持不变。",
                    id="profile-edit-result-safety",
                )
            elif (
                self.result.transaction is not None
                and self.result.transaction.outcome is ApplyOutcome.ROLLED_BACK
            ):
                rollback = self.result.transaction.rollback
                yield Static("编辑失败，已自动回滚", id="profile-edit-result-title")
                yield Static(
                    rollback.diagnostics if rollback is not None else "旧配置已恢复。",
                    id="profile-edit-result-details",
                )
                yield Static(
                    "原有配置、服务和 desired state 已保留。",
                    id="profile-edit-result-safety",
                )
            elif self.result.transaction is not None:
                rollback = self.result.transaction.rollback
                yield Static("回滚未完成，需要人工恢复", id="profile-edit-result-title")
                yield Static(
                    rollback.diagnostics if rollback is not None else "回滚状态未知",
                    id="profile-edit-result-details",
                )
                yield Static(
                    "desired state 未提交。完成恢复前不要再次修改配置。",
                    id="profile-edit-result-safety",
                )
                if rollback is not None:
                    for index, instruction in enumerate(rollback.recovery_instructions):
                        yield Static(
                            f"{index + 1}. {instruction}",
                            id=f"profile-edit-recovery-step-{index}",
                        )
            if self.result.committed_revision is not None and self.result.listen_port is not None:
                yield Static(
                    f"当前监听端口：{self.result.listen_port}",
                    id="profile-edit-result-listen-port",
                )
            if self.result.committed_revision is not None:
                yield Button(
                    "返回仪表盘",
                    id="profile-edit-return-dashboard",
                    variant="primary",
                )
        yield Footer()

    @on(Button.Pressed, "#profile-edit-return-dashboard")
    def return_to_dashboard(self) -> None:
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        self.app.post_message(DashboardRefreshRequested())


class ProfileEditOperationalErrorScreen(Screen[None]):
    """Explain an unknown host result without claiming profile changes."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, diagnostics: str | None = None) -> None:
        super().__init__()
        self.diagnostics = diagnostics

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-edit-operational-error"):
            yield Static("无法确认配置编辑结果", id="profile-edit-error-title")
            yield Static(
                self.diagnostics or "发生意外错误。底层错误未显示，以避免泄露敏感信息。",
                id="profile-edit-error-details",
            )
            yield Static(
                (
                    "desired state 未提交。请检查 sing-box 服务和 helper 日志后再决定是否重试。"
                    if self.diagnostics is not None
                    else "服务器配置、服务和 desired state 的结果均未知。"
                    "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
                ),
                id="profile-edit-error-safety",
            )
        yield Footer()


class ProfileEditPortConflictScreen(Screen[None]):
    """Explain a safe confirmation-time port conflict without implying host mutation."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, diagnostics: str) -> None:
        super().__init__()
        self.diagnostics = diagnostics

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-edit-port-conflict"):
            yield Static("监听端口已不可用", id="profile-edit-port-conflict-title")
            yield Static(self.diagnostics, id="profile-edit-port-conflict-details")
            yield Static(
                "尚未调用配置 applier，实时配置、服务和 desired state 均未改变。",
                id="profile-edit-port-conflict-safety",
            )
        yield Footer()


class ProfileEditConflictScreen(Screen[None]):
    """Explain that a reviewed edit plan is no longer current."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, diagnostics: str) -> None:
        super().__init__()
        self.diagnostics = diagnostics

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-edit-conflict"):
            yield Static("配置已被其他会话修改", id="profile-edit-conflict-title")
            yield Static(self.diagnostics, id="profile-edit-conflict-details")
            yield Static(
                "本次变更未执行。请返回列表，重新打开详情并预览最新计划。",
                id="profile-edit-conflict-safety",
            )
        yield Footer()
