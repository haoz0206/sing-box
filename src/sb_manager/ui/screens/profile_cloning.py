"""Guided review and confirmation for safe profile-template drafts."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_cloning import (
    PlanProfileCloneRequest,
    ProfileCloneError,
    ProfileCloneFacet,
    ProfileClonePlan,
    ProfileCloner,
    ProfileCloneResult,
)

FACET_LABELS = {
    ProfileCloneFacet.PROTOCOL: "协议",
    ProfileCloneFacet.SERVER_ADDRESS: "服务器地址",
    ProfileCloneFacet.TLS_STRATEGY: "TLS 方式",
    ProfileCloneFacet.TRANSPORT: "传输方式",
    ProfileCloneFacet.CREDENTIALS: "认证凭据",
    ProfileCloneFacet.LISTEN_PORT: "监听端口",
    ProfileCloneFacet.RUNTIME_STATUS: "运行状态",
}
MIN_JOINED_LABELS = 2


def _join_labels(facets: tuple[ProfileCloneFacet, ...]) -> str:
    labels = [FACET_LABELS[facet] for facet in facets]
    if len(labels) < MIN_JOINED_LABELS:
        return "".join(labels)
    return f"{'、'.join(labels[:-1])}和{labels[-1]}"


class ProfileCloneScreen(Screen[ProfileCloneResult | None]):
    """Edit a name, review reset semantics, then create one desired-state draft."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "取消")]

    def __init__(self, profile_cloner: ProfileCloner, *, source_profile_id: str) -> None:
        super().__init__()
        self.profile_cloner = profile_cloner
        self.plan = profile_cloner.plan(
            PlanProfileCloneRequest(source_profile_id=source_profile_id)
        )
        self.result: ProfileCloneResult | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-clone"):
            yield Static("以现有配置创建新草案", id="profile-clone-title")
            yield Static(
                f"模板：{self.plan.source_profile_name}",
                id="profile-clone-source",
            )
            yield Input(value=self.plan.profile_name, id="profile-clone-name")
            yield Static(
                f"将复用：{_join_labels(self.plan.copied_facets)}",
                id="profile-clone-copied",
            )
            yield Static(
                f"将重置：{_join_labels(self.plan.reset_facets)}，新配置保存为未应用草案。",
                id="profile-clone-reset",
            )
            yield Static("", id="profile-clone-summary", classes="hidden")
            yield Static("", id="profile-clone-error", classes="hidden")
            yield Static("", id="profile-clone-result", classes="hidden")
            yield Button("审阅草案", id="review-profile-clone", variant="primary")
            yield Button("修改名称", id="edit-profile-clone", classes="hidden")
            yield Button(
                "确认创建草案",
                id="confirm-profile-clone",
                classes="hidden",
                variant="warning",
            )
            yield Button(
                "返回配置列表",
                id="finish-profile-clone",
                classes="hidden",
                variant="primary",
            )
        yield Footer()

    @on(Button.Pressed, "#review-profile-clone")
    def review_clone(self) -> None:
        try:
            plan = self.profile_cloner.plan(
                PlanProfileCloneRequest(
                    source_profile_id=self.plan.source_profile_id,
                    profile_name=self.query_one("#profile-clone-name", Input).value,
                )
            )
        except ProfileCloneError as error:
            self.show_error(str(error))
            return
        self.plan = plan
        self.query_one("#profile-clone-title", Static).update("确认模板草案")
        name_input = self.query_one("#profile-clone-name", Input)
        name_input.value = plan.profile_name
        name_input.disabled = True
        summary = self.query_one("#profile-clone-summary", Static)
        summary.update(f"{plan.source_profile_name} → {plan.profile_name}")
        summary.remove_class("hidden")
        self.query_one("#profile-clone-error", Static).add_class("hidden")
        self.query_one("#review-profile-clone", Button).add_class("hidden")
        self.query_one("#edit-profile-clone", Button).remove_class("hidden")
        self.query_one("#confirm-profile-clone", Button).remove_class("hidden")

    @on(Button.Pressed, "#edit-profile-clone")
    def edit_clone(self) -> None:
        self.query_one("#profile-clone-title", Static).update("以现有配置创建新草案")
        self.query_one("#profile-clone-name", Input).disabled = False
        self.query_one("#profile-clone-summary", Static).add_class("hidden")
        self.query_one("#profile-clone-error", Static).add_class("hidden")
        self.query_one("#review-profile-clone", Button).remove_class("hidden")
        self.query_one("#edit-profile-clone", Button).add_class("hidden")
        self.query_one("#confirm-profile-clone", Button).add_class("hidden")

    @on(Button.Pressed, "#confirm-profile-clone")
    def confirm_clone(self) -> None:
        self.query_one("#confirm-profile-clone", Button).disabled = True
        self.query_one("#edit-profile-clone", Button).disabled = True
        self.execute_clone(self.plan)

    @work(thread=True, exclusive=True)
    def execute_clone(self, plan: ProfileClonePlan) -> None:
        try:
            result = self.profile_cloner.clone(plan, confirmed=True)
        except StateRevisionConflictError:
            self.app.call_from_thread(
                self.show_error,
                "desired state 已变化，请返回配置详情后重新审阅模板。",
            )
            return
        except ProfileCloneError as error:
            self.app.call_from_thread(self.show_error, str(error))
            return
        self.app.call_from_thread(self.show_success, result)

    def show_error(self, diagnostics: str) -> None:
        error = self.query_one("#profile-clone-error", Static)
        error.update(diagnostics)
        error.remove_class("hidden")
        self.query_one("#confirm-profile-clone", Button).disabled = False
        self.query_one("#edit-profile-clone", Button).disabled = False

    def show_success(self, result: ProfileCloneResult) -> None:
        self.result = result
        self.query_one("#profile-clone-title", Static).update("草案已创建")
        result_summary = self.query_one("#profile-clone-result", Static)
        result_summary.update(
            f"{result.profile_name} · desired state revision {result.committed_revision}"
        )
        result_summary.remove_class("hidden")
        for selector in (
            "#profile-clone-source",
            "#profile-clone-name",
            "#profile-clone-copied",
            "#profile-clone-reset",
            "#profile-clone-summary",
            "#profile-clone-error",
            "#review-profile-clone",
            "#edit-profile-clone",
            "#confirm-profile-clone",
        ):
            self.query_one(selector).add_class("hidden")
        self.query_one("#finish-profile-clone", Button).remove_class("hidden")

    @on(Button.Pressed, "#finish-profile-clone")
    def finish_clone(self) -> None:
        if self.result is not None:
            self.dismiss(self.result)
