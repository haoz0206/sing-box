"""Task-oriented workspace for profiles in one desired-state snapshot."""

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.domain.installation import ManagedInstallation, ProfileStatus
from sb_manager.ui.labels import PROTOCOL_LABELS


class ProfileWorkspaceActionKind(str, Enum):
    """Stable navigation identities emitted by the profiles workspace."""

    ADD_PROFILE = "add-profile"
    VIEW_DETAILS = "view-details"
    APPLY_DRAFT = "apply-draft"


@dataclass
class ProfileWorkspaceActionRequested(Message):
    """Request one existing profile workflow without encoding it in UI text."""

    kind: ProfileWorkspaceActionKind
    profile_id: str | None = None


class ProfilesScreen(Screen[None]):
    """Present complete profile inventory away from the service dashboard."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(
        self,
        installation: ManagedInstallation,
        *,
        details_available: bool,
        apply_available: bool,
    ) -> None:
        super().__init__()
        self.installation = installation
        self.details_available = details_available
        self.apply_available = apply_available

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profiles-workspace"):
            yield Static("配置工作区", id="profiles-workspace-title", markup=False)
            yield Static(
                "浏览 desired state 中的完整配置，并从这里开始生命周期操作。",
                id="profiles-workspace-summary",
                markup=False,
            )
            if not self.installation.profiles:
                yield Static(
                    "尚未创建代理配置。先说明使用目的，再选择合适的协议。",
                    id="profiles-workspace-empty",
                    markup=False,
                )
            for index, profile in enumerate(self.installation.profiles):
                port = (
                    "自动选择端口" if profile.listen_port is None else f"端口 {profile.listen_port}"
                )
                status = (
                    ("在线" if profile.enabled else "已暂停")
                    if profile.status is ProfileStatus.APPLIED
                    else "草案"
                )
                yield Static(
                    " · ".join(
                        (
                            profile.profile_name,
                            PROTOCOL_LABELS[profile.protocol],
                            status,
                            port,
                        )
                    ),
                    id=f"profile-{index}",
                    markup=False,
                )
                if self.details_available:
                    yield Button(
                        "查看详情",
                        name=profile.profile_id,
                        id=f"view-profile-{index}",
                        classes="view-profile-action",
                    )
                if profile.status is ProfileStatus.DRAFT and self.apply_available:
                    yield Button(
                        "应用草案",
                        name=profile.profile_id,
                        id=f"apply-profile-{index}",
                        classes="apply-profile-action",
                        variant="warning",
                    )
            yield Button("添加配置", id="add-profile")
        yield Footer()

    @on(Button.Pressed, "#add-profile")
    def request_add_profile(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(ProfileWorkspaceActionRequested(ProfileWorkspaceActionKind.ADD_PROFILE))

    @on(Button.Pressed, ".view-profile-action")
    def request_profile_details(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.name is not None:
            self.post_message(
                ProfileWorkspaceActionRequested(
                    ProfileWorkspaceActionKind.VIEW_DETAILS,
                    profile_id=event.button.name,
                )
            )

    @on(Button.Pressed, ".apply-profile-action")
    def request_draft_apply(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.name is not None:
            self.post_message(
                ProfileWorkspaceActionRequested(
                    ProfileWorkspaceActionKind.APPLY_DRAFT,
                    profile_id=event.button.name,
                )
            )
