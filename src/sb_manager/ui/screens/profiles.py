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
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
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

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        installation: ManagedInstallation,
        *,
        details_available: bool,
        apply_available: bool,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.installation = installation
        self.details_available = details_available
        self.apply_available = apply_available
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profiles-workspace"):
            yield Static(
                self.copy.text(UiText.PROFILES_TITLE),
                id="profiles-workspace-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILES_SUMMARY),
                id="profiles-workspace-summary",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILES_SAFETY),
                id="profiles-workspace-safety",
                markup=False,
            )
            if not self.installation.profiles:
                yield Static(
                    self.copy.text(UiText.PROFILES_EMPTY),
                    id="profiles-workspace-empty",
                    markup=False,
                )
            for index, profile in enumerate(self.installation.profiles):
                port = (
                    self.copy.text(UiText.PROFILES_PORT_AUTOMATIC)
                    if profile.listen_port is None
                    else self.copy.text(UiText.PROFILES_PORT_FIXED, port=profile.listen_port)
                )
                status = (
                    (
                        self.copy.text(UiText.PROFILES_STATUS_ACTIVE)
                        if profile.enabled
                        else self.copy.text(UiText.PROFILES_STATUS_PAUSED)
                    )
                    if profile.status is ProfileStatus.APPLIED
                    else self.copy.text(UiText.PROFILES_STATUS_DRAFT)
                )
                yield Static(
                    self.copy.text(
                        UiText.PROFILES_ROW,
                        name=profile.profile_name,
                        protocol=PROTOCOL_LABELS[profile.protocol],
                        status=status,
                        port=port,
                    ),
                    id=f"profile-{index}",
                    markup=False,
                )
                if self.details_available:
                    yield Button(
                        self.copy.text(UiText.PROFILES_VIEW_DETAILS),
                        name=profile.profile_id,
                        id=f"view-profile-{index}",
                        classes="view-profile-action",
                    )
                if profile.status is ProfileStatus.DRAFT and self.apply_available:
                    yield Button(
                        self.copy.text(UiText.PROFILES_APPLY_DRAFT),
                        name=profile.profile_id,
                        id=f"apply-profile-{index}",
                        classes="apply-profile-action",
                        variant="warning",
                    )
            yield Button(self.copy.text(UiText.PROFILES_ADD), id="add-profile")
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
