from dataclasses import dataclass
from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.profile_availability import (
    PlanProfileAvailabilityRequest,
    ProfileAvailability,
    ProfileAvailabilityDraftError,
    ProfileAvailabilityManager,
    ProfileAvailabilityNoChangeError,
    ProfileAvailabilityNotFoundError,
    ProfileResumePortUnavailableError,
)
from sb_manager.application.profile_cloning import (
    ProfileCloneError,
    ProfileCloner,
    ProfileCloneResult,
)
from sb_manager.application.profile_details import ProfileDetails
from sb_manager.application.profile_editing import ProfileEditor
from sb_manager.application.profile_removal import (
    ProfileRemovalNotFoundError,
    ProfileRemover,
)
from sb_manager.domain.installation import ProfileStatus
from sb_manager.ui.connection_share import ConnectionSharePanel
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.labels import PROTOCOL_LABELS
from sb_manager.ui.messages import DashboardRefreshRequested
from sb_manager.ui.screens.profile_availability import (
    ProfileAvailabilityErrorScreen,
    ProfileAvailabilityPlanningErrorScreen,
    ProfileAvailabilityPlanScreen,
)
from sb_manager.ui.screens.profile_cloning import (
    ProfileClonePlanningErrorScreen,
    ProfileCloneScreen,
)
from sb_manager.ui.screens.profile_editing import ProfileEditFormScreen
from sb_manager.ui.screens.profile_removal import (
    ProfileRemovalPlanningErrorScreen,
    ProfileRemovalScreen,
)

__all__ = (
    "ProfileDetailsCapabilities",
    "ProfileDetailsErrorScreen",
    "ProfileDetailsScreen",
    "ProfileDetailsUnexpectedErrorScreen",
)


@dataclass(frozen=True, slots=True)
class ProfileDetailsCapabilities:
    """Lifecycle entries available from one profile-details snapshot."""

    editor: ProfileEditor | None = None
    remover: ProfileRemover | None = None
    availability_manager: ProfileAvailabilityManager | None = None
    cloner: ProfileCloner | None = None


class ProfileDetailsScreen(Screen[None]):
    """Present durable profile identity and reusable client information."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        details: ProfileDetails,
        *,
        capabilities: ProfileDetailsCapabilities | None = None,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.details = details
        self.capabilities = capabilities or ProfileDetailsCapabilities()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profile-details"):
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_TITLE),
                id="profile-details-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_SAFETY),
                id="profile-details-safety",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_NAME, name=self.details.profile_name),
                id="profile-details-name",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_DETAILS_PROTOCOL,
                    protocol=PROTOCOL_LABELS[self.details.protocol],
                ),
                id="profile-details-protocol",
                markup=False,
            )
            status = (
                (
                    self.copy.text(UiText.PROFILE_DETAILS_STATUS_ACTIVE)
                    if self.details.enabled
                    else self.copy.text(UiText.PROFILE_DETAILS_STATUS_PAUSED)
                )
                if self.details.status is ProfileStatus.APPLIED
                else self.copy.text(UiText.PROFILE_DETAILS_STATUS_DRAFT)
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_STATUS, status=status),
                id="profile-details-status",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_DETAILS_SERVER_ADDRESS,
                    address=self.details.server_address,
                )
                if self.details.server_address is not None
                else self.copy.text(UiText.PROFILE_DETAILS_SERVER_ADDRESS_UNSET),
                id="profile-details-server-address",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_DETAILS_LISTEN_PORT,
                    port=self.details.listen_port,
                )
                if self.details.listen_port is not None
                else self.copy.text(UiText.PROFILE_DETAILS_LISTEN_PORT_AUTOMATIC),
                id="profile-details-listen-port",
                markup=False,
            )
            if connection_info := self.details.connection_info:
                yield ConnectionSharePanel(connection_info, self.copy)
            else:
                yield Static(
                    self.copy.text(UiText.PROFILE_DETAILS_NO_CONNECTION),
                    id="profile-details-no-connection",
                    markup=False,
                )
            if self.capabilities.editor is not None:
                yield Button(
                    self.copy.text(UiText.PROFILE_DETAILS_EDIT),
                    id="edit-profile",
                    variant="primary",
                )
            if self.capabilities.cloner is not None:
                yield Button(self.copy.text(UiText.PROFILE_DETAILS_CLONE), id="clone-profile")
            if (
                self.capabilities.availability_manager is not None
                and self.details.status is ProfileStatus.APPLIED
            ):
                yield Button(
                    self.copy.text(
                        UiText.PROFILE_DETAILS_PAUSE
                        if self.details.enabled
                        else UiText.PROFILE_DETAILS_RESUME
                    ),
                    id="change-profile-availability",
                    variant="warning",
                )
            if self.capabilities.remover is not None:
                yield Button(
                    self.copy.text(UiText.PROFILE_DETAILS_REMOVE),
                    id="remove-profile",
                    variant="error",
                )
        yield Footer()

    @on(Button.Pressed, "#edit-profile")
    def open_profile_editing(self) -> None:
        if self.capabilities.editor is not None:
            self.app.push_screen(
                ProfileEditFormScreen(
                    self.capabilities.editor,
                    details=self.details,
                    copy_catalog=self.copy,
                )
            )

    @on(Button.Pressed, "#remove-profile")
    def open_profile_removal(self) -> None:
        if self.capabilities.remover is None:
            return
        try:
            screen = ProfileRemovalScreen(
                self.capabilities.remover,
                profile_id=self.details.profile_id,
                copy_catalog=self.copy,
            )
        except ProfileRemovalNotFoundError:
            self.app.push_screen(ProfileDetailsErrorScreen(self.copy))
            return
        except Exception:
            self.app.push_screen(ProfileRemovalPlanningErrorScreen(self.copy))
            return
        self.app.push_screen(screen)

    @on(Button.Pressed, "#clone-profile")
    def open_profile_clone(self) -> None:
        if self.capabilities.cloner is None:
            return
        try:
            screen = ProfileCloneScreen(
                self.capabilities.cloner,
                source_profile_id=self.details.profile_id,
                copy_catalog=self.copy,
            )
        except ProfileCloneError:
            self.app.push_screen(ProfileDetailsErrorScreen(self.copy))
            return
        except Exception:
            self.app.push_screen(ProfileClonePlanningErrorScreen(self.copy))
            return
        self.app.push_screen(screen, self.finish_profile_clone)

    def finish_profile_clone(self, result: ProfileCloneResult | None) -> None:
        if result is None:
            return
        self.dismiss()
        self.app.post_message(DashboardRefreshRequested())

    @on(Button.Pressed, "#change-profile-availability")
    def open_profile_availability(self) -> None:
        if self.capabilities.availability_manager is None:
            return
        target = ProfileAvailability.PAUSED if self.details.enabled else ProfileAvailability.ACTIVE
        try:
            plan = self.capabilities.availability_manager.plan_change(
                PlanProfileAvailabilityRequest(
                    profile_id=self.details.profile_id,
                    target=target,
                )
            )
        except (
            ProfileAvailabilityDraftError,
            ProfileAvailabilityNoChangeError,
            ProfileAvailabilityNotFoundError,
            ProfileResumePortUnavailableError,
        ) as error:
            self.app.push_screen(ProfileAvailabilityErrorScreen(str(error), copy_catalog=self.copy))
            return
        except Exception:
            self.app.push_screen(ProfileAvailabilityPlanningErrorScreen(self.copy))
            return
        self.app.push_screen(
            ProfileAvailabilityPlanScreen(
                self.capabilities.availability_manager,
                plan=plan,
                copy_catalog=self.copy,
            )
        )


class ProfileDetailsErrorScreen(Screen[None]):
    """Keep stale or incomplete desired state from terminating the TUI."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-details-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_ERROR_TITLE),
                id="profile-details-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_ERROR_MESSAGE),
                id="profile-details-error-message",
                markup=False,
            )
        yield Footer()


class ProfileDetailsUnexpectedErrorScreen(Screen[None]):
    """Report an unexpected profile-detail read without disclosing its cause."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-details-unexpected-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_UNEXPECTED_TITLE),
                id="profile-details-unexpected-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_UNEXPECTED_DETAILS),
                id="profile-details-unexpected-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_UNEXPECTED_SAFETY),
                id="profile-details-unexpected-safety",
                markup=False,
            )
        yield Footer()
