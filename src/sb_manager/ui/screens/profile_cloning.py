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
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText

FACET_LABELS = {
    ProfileCloneFacet.PROTOCOL: UiText.PROFILE_CLONE_FACET_PROTOCOL,
    ProfileCloneFacet.SERVER_ADDRESS: UiText.PROFILE_CLONE_FACET_SERVER_ADDRESS,
    ProfileCloneFacet.TLS_STRATEGY: UiText.PROFILE_CLONE_FACET_TLS_STRATEGY,
    ProfileCloneFacet.TRANSPORT: UiText.PROFILE_CLONE_FACET_TRANSPORT,
    ProfileCloneFacet.CREDENTIALS: UiText.PROFILE_CLONE_FACET_CREDENTIALS,
    ProfileCloneFacet.LISTEN_PORT: UiText.PROFILE_CLONE_FACET_LISTEN_PORT,
    ProfileCloneFacet.RUNTIME_STATUS: UiText.PROFILE_CLONE_FACET_RUNTIME_STATUS,
}
MIN_JOINED_LABELS = 2


def _join_labels(facets: tuple[ProfileCloneFacet, ...], copy: CopyCatalog) -> str:
    labels = [copy.text(FACET_LABELS[facet]) for facet in facets]
    if len(labels) < MIN_JOINED_LABELS:
        return "".join(labels)
    prefix = copy.text(UiText.PROFILE_CLONE_FACET_SEPARATOR).join(labels[:-1])
    return copy.text(
        UiText.PROFILE_CLONE_FACET_CONJUNCTION,
        prefix=prefix,
        last=labels[-1],
    )


class ProfileClonePlanningErrorScreen(Screen[None]):
    """Report an unexpected read-only clone-planning failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-clone-planning-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_CLONE_PLANNING_TITLE),
                id="profile-clone-planning-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CLONE_PLANNING_DETAILS),
                id="profile-clone-planning-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CLONE_PLANNING_SAFETY),
                id="profile-clone-planning-error-safety",
                markup=False,
            )
        yield Footer()


class ProfileCloneOperationalErrorScreen(Screen[None]):
    """Report an unknown desired-state clone result without disclosing errors."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-clone-operational-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_CLONE_OPERATIONAL_TITLE),
                id="profile-clone-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CLONE_OPERATIONAL_DETAILS),
                id="profile-clone-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CLONE_OPERATIONAL_SAFETY),
                id="profile-clone-error-safety",
                markup=False,
            )
        yield Footer()


class ProfileCloneScreen(ConfirmedOperationScreen[ProfileCloneResult | None]):
    """Edit a name, review reset semantics, then create one desired-state draft."""

    def __init__(
        self,
        profile_cloner: ProfileCloner,
        *,
        source_profile_id: str,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.profile_cloner = profile_cloner
        self.plan = profile_cloner.plan(
            PlanProfileCloneRequest(source_profile_id=source_profile_id)
        )
        self.result: ProfileCloneResult | None = None
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-clone"):
            yield Static(
                self.copy.text(UiText.PROFILE_CLONE_FORM_TITLE),
                id="profile-clone-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_CLONE_FORM_SOURCE,
                    name=self.plan.source_profile_name,
                ),
                id="profile-clone-source",
                markup=False,
            )
            yield Input(value=self.plan.profile_name, id="profile-clone-name")
            yield Static(
                self.copy.text(
                    UiText.PROFILE_CLONE_FORM_COPIED,
                    facets=_join_labels(self.plan.copied_facets, self.copy),
                ),
                id="profile-clone-copied",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_CLONE_FORM_RESET,
                    facets=_join_labels(self.plan.reset_facets, self.copy),
                ),
                id="profile-clone-reset",
                markup=False,
            )
            yield Static("", id="profile-clone-summary", classes="hidden", markup=False)
            yield Static("", id="profile-clone-error", classes="hidden", markup=False)
            yield Static("", id="profile-clone-result", classes="hidden", markup=False)
            yield Button(
                self.copy.text(UiText.PROFILE_CLONE_FORM_REVIEW),
                id="review-profile-clone",
                variant="primary",
            )
            yield Button(
                self.copy.text(UiText.PROFILE_CLONE_FORM_EDIT),
                id="edit-profile-clone",
                classes="hidden",
            )
            yield Button(
                self.copy.text(UiText.PROFILE_CLONE_FORM_CONFIRM),
                id="confirm-profile-clone",
                classes="hidden",
                variant="warning",
            )
            yield Button(
                self.copy.text(UiText.PROFILE_CLONE_FORM_RETURN_LIST),
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
        except Exception:
            self.app.push_screen(ProfileClonePlanningErrorScreen(self.copy))
            return
        self.plan = plan
        self.query_one("#profile-clone-title", Static).update(
            self.copy.text(UiText.PROFILE_CLONE_REVIEW_TITLE)
        )
        name_input = self.query_one("#profile-clone-name", Input)
        name_input.value = plan.profile_name
        name_input.disabled = True
        summary = self.query_one("#profile-clone-summary", Static)
        summary.update(
            self.copy.text(
                UiText.PROFILE_CLONE_REVIEW_SUMMARY,
                source=plan.source_profile_name,
                target=plan.profile_name,
            )
        )
        summary.remove_class("hidden")
        self.query_one("#profile-clone-error", Static).add_class("hidden")
        self.query_one("#review-profile-clone", Button).add_class("hidden")
        self.query_one("#edit-profile-clone", Button).remove_class("hidden")
        confirm = self.query_one("#confirm-profile-clone", Button)
        confirm.disabled = False
        confirm.remove_class("hidden")

    @on(Button.Pressed, "#edit-profile-clone")
    def edit_clone(self) -> None:
        self.query_one("#profile-clone-title", Static).update(
            self.copy.text(UiText.PROFILE_CLONE_FORM_TITLE)
        )
        self.query_one("#profile-clone-name", Input).disabled = False
        self.query_one("#profile-clone-summary", Static).add_class("hidden")
        self.query_one("#profile-clone-error", Static).add_class("hidden")
        self.query_one("#review-profile-clone", Button).remove_class("hidden")
        self.query_one("#edit-profile-clone", Button).add_class("hidden")
        self.query_one("#confirm-profile-clone", Button).add_class("hidden")

    @on(Button.Pressed, "#confirm-profile-clone")
    def confirm_clone(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-profile-clone", Button).disabled = True
        self.query_one("#edit-profile-clone", Button).disabled = True
        self.query_one("#profile-clone-summary", Static).update(
            self.copy.text(UiText.PROFILE_CLONE_IN_PROGRESS)
        )
        self.execute_clone(self.plan)

    @work(thread=True, exclusive=True)
    def execute_clone(self, plan: ProfileClonePlan) -> None:
        try:
            result = self.profile_cloner.clone(plan, confirmed=True)
        except StateRevisionConflictError:
            self.app.call_from_thread(
                self.show_stale_error,
                self.copy.text(UiText.PROFILE_CLONE_STALE),
            )
            return
        except ProfileCloneError as error:
            self.app.call_from_thread(self.show_error, str(error))
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileCloneOperationalErrorScreen(self.copy),
            )
            return
        self.app.call_from_thread(self.show_success, result)

    def show_error(self, diagnostics: str) -> None:
        self.finish_confirmed_operation()
        error = self.query_one("#profile-clone-error", Static)
        error.update(diagnostics)
        error.remove_class("hidden")
        self.query_one("#confirm-profile-clone", Button).disabled = False
        self.query_one("#edit-profile-clone", Button).disabled = False

    def show_stale_error(self, diagnostics: str) -> None:
        self.show_error(diagnostics)
        self.query_one("#confirm-profile-clone", Button).disabled = True

    def show_success(self, result: ProfileCloneResult) -> None:
        self.finish_confirmed_operation()
        self.result = result
        self.query_one("#profile-clone-title", Static).update(
            self.copy.text(UiText.PROFILE_CLONE_RESULT_TITLE)
        )
        result_summary = self.query_one("#profile-clone-result", Static)
        result_summary.update(
            self.copy.text(
                UiText.PROFILE_CLONE_RESULT_SUMMARY,
                name=result.profile_name,
                revision=result.committed_revision,
            )
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
