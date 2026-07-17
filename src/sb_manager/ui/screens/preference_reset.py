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
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class PreferenceResetConfirmationScreen(ConfirmedOperationScreen[PreferenceResetResult | None]):
    """Show one hash-bound preference reset before any filesystem write."""

    def __init__(
        self,
        preference_service: InterfacePreferenceService,
        plan: PreferenceResetPlan,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__(copy_catalog)
        self.preference_service = preference_service
        self.plan = plan

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="preference-reset-confirmation"):
            yield Static(
                self.copy.text(UiText.PREFERENCE_RESET_TITLE),
                id="preference-reset-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PREFERENCE_RESET_FINGERPRINT,
                    sha256=self.plan.expected_sha256,
                ),
                id="preference-reset-fingerprint",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PREFERENCE_RESET_DEFAULT),
                id="preference-reset-default",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PREFERENCE_RESET_SAFETY),
                id="preference-reset-safety",
                markup=False,
            )
            yield Static("", id="preference-reset-error", classes="hidden", markup=False)
            yield Button(
                self.copy.text(UiText.PREFERENCE_RESET_CONFIRM),
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
            self.copy.text(UiText.PREFERENCE_RESET_IN_PROGRESS)
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
                PreferenceResetOperationalErrorScreen(self.copy),
            )
            return
        self.app.call_from_thread(self.finish_reset, result)

    def finish_reset(self, result: PreferenceResetResult) -> None:
        self.finish_confirmed_operation()
        self.dismiss(result)

    def show_conflict(self) -> None:
        self.finish_confirmed_operation()
        error = self.query_one("#preference-reset-error", Static)
        error.update(self.copy.text(UiText.PREFERENCE_RESET_CONFLICT))
        error.remove_class("hidden")

    def show_error(self) -> None:
        self.finish_confirmed_operation()
        error = self.query_one("#preference-reset-error", Static)
        error.update(self.copy.text(UiText.PREFERENCE_RESET_ERROR))
        error.remove_class("hidden")
        self.query_one("#confirm-preference-reset", Button).disabled = False


class PreferenceResetPlanningErrorScreen(Screen[None]):
    """Keep an unexpected or unsafe reset candidate non-disclosing."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="preference-reset-planning-error"):
            yield Static(
                self.copy.text(UiText.PREFERENCE_RESET_PLANNING_TITLE),
                id="preference-reset-planning-error-title",
            )
            yield Static(
                self.copy.text(UiText.PREFERENCE_RESET_PLANNING_DETAILS),
                id="preference-reset-planning-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PREFERENCE_RESET_PLANNING_SAFETY),
                id="preference-reset-planning-error-safety",
                markup=False,
            )
        yield Footer()


class PreferenceResetOperationalErrorScreen(Screen[None]):
    """Report an unknown local preference-reset result without disclosure."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="preference-reset-operational-error"):
            yield Static(
                self.copy.text(UiText.PREFERENCE_RESET_OPERATIONAL_TITLE),
                id="preference-reset-operational-title",
            )
            yield Static(
                self.copy.text(UiText.PREFERENCE_RESET_OPERATIONAL_DETAILS),
                id="preference-reset-operational-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PREFERENCE_RESET_OPERATIONAL_SAFETY),
                id="preference-reset-operational-safety",
                markup=False,
            )
        yield Footer()
