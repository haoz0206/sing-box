"""Explicit existing-configuration adoption workflow behind one screen interface."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.config_adoption import (
    ConfigAdopter,
    ConfigAdoptionError,
    ConfigAdoptionPlan,
    ConfigAdoptionResult,
)
from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.seams.config_target import ConfigTargetInspectionError
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.messages import DashboardRefreshRequested


class _ConfigAdoptionResultScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        result: ConfigAdoptionResult,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.result = result
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-adoption-result"):
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_RESULT_TITLE),
                id="config-adoption-result-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CONFIG_ADOPTION_RESULT_REVISION,
                    revision=self.result.committed_revision,
                ),
                id="config-adoption-result-revision",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_RESULT_SAFETY),
                id="config-adoption-result-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.CONFIG_ADOPTION_RESULT_RETURN_DASHBOARD),
                id="config-adoption-return-dashboard",
                variant="primary",
            )
        yield Footer()

    @on(Button.Pressed, "#config-adoption-return-dashboard")
    def return_to_dashboard(self) -> None:
        self.post_message(DashboardRefreshRequested())


class _ConfigAdoptionErrorScreen(Screen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        diagnostics: str,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.diagnostics = diagnostics
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-adoption-error"):
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_ERROR_TITLE),
                id="config-adoption-error-title",
                markup=False,
            )
            yield Static(
                self.diagnostics,
                id="config-adoption-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_ERROR_SAFETY),
                id="config-adoption-error-safety",
                markup=False,
            )
        yield Footer()


class _ConfigAdoptionPlanningErrorScreen(Screen[None]):
    """Report an unexpected read-only adoption-planning failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-adoption-planning-error"):
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_PLANNING_ERROR_TITLE),
                id="config-adoption-planning-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_PLANNING_ERROR_DETAILS),
                id="config-adoption-planning-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_PLANNING_ERROR_SAFETY),
                id="config-adoption-planning-error-safety",
                markup=False,
            )
        yield Footer()


class _ConfigAdoptionOperationalErrorScreen(Screen[None]):
    """Report an unknown desired-state adoption result without disclosure."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-adoption-operational-error"):
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_UNKNOWN_TITLE),
                id="config-adoption-unknown-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_UNKNOWN_DETAILS),
                id="config-adoption-unknown-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_UNKNOWN_SAFETY),
                id="config-adoption-unknown-safety",
                markup=False,
            )
        yield Footer()


class ConfigAdoptionScreen(ConfirmedOperationScreen[None]):
    """Inspect, review, recheck, and record one exact live config identity."""

    def __init__(
        self,
        config_adopter: ConfigAdopter,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__(copy_catalog)
        self.config_adopter = config_adopter
        self.plan: ConfigAdoptionPlan | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="config-adoption"):
            yield Static(
                self.copy.text(UiText.CONFIG_ADOPTION_PLAN_LOADING),
                id="config-adoption-title",
                markup=False,
            )
            yield Static(
                "",
                id="config-adoption-fingerprint",
                classes="hidden",
                markup=False,
            )
            yield Static(
                "",
                id="config-adoption-safety",
                classes="hidden",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.CONFIG_ADOPTION_PLAN_CONFIRM),
                id="confirm-config-adoption",
                classes="hidden",
                variant="warning",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.load_plan()

    @work(thread=True, exclusive=True)
    def load_plan(self) -> None:
        try:
            plan = self.config_adopter.plan()
        except (ConfigAdoptionError, ConfigTargetInspectionError) as error:
            self.app.call_from_thread(
                self.app.push_screen,
                _ConfigAdoptionErrorScreen(str(error), self.copy),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.app.push_screen,
                _ConfigAdoptionPlanningErrorScreen(self.copy),
            )
            return
        self.app.call_from_thread(self.show_plan, plan)

    def show_plan(self, plan: ConfigAdoptionPlan) -> None:
        self.plan = plan
        self.query_one("#config-adoption-title", Static).update(
            self.copy.text(UiText.CONFIG_ADOPTION_PLAN_TITLE)
        )
        fingerprint = self.query_one("#config-adoption-fingerprint", Static)
        fingerprint.update(
            self.copy.text(
                UiText.CONFIG_ADOPTION_PLAN_FINGERPRINT,
                sha256=plan.config_sha256,
            )
        )
        fingerprint.remove_class("hidden")
        safety = self.query_one("#config-adoption-safety", Static)
        safety.update(self.copy.text(UiText.CONFIG_ADOPTION_PLAN_SAFETY))
        safety.remove_class("hidden")
        self.query_one("#confirm-config-adoption", Button).remove_class("hidden")

    @on(Button.Pressed, "#confirm-config-adoption")
    def confirm_adoption(self) -> None:
        if self.plan is None:
            return
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-config-adoption", Button).disabled = True
        self.query_one("#config-adoption-safety", Static).update(
            self.copy.text(UiText.CONFIG_ADOPTION_PLAN_PROGRESS)
        )
        self.execute_adoption(self.plan)

    @work(thread=True, exclusive=True)
    def execute_adoption(self, plan: ConfigAdoptionPlan) -> None:
        try:
            result = self.config_adopter.adopt(plan, confirmed=True)
        except (
            ConfigAdoptionError,
            ConfigTargetInspectionError,
            StateRevisionConflictError,
        ) as error:
            self.app.call_from_thread(
                self.push_terminal_screen,
                _ConfigAdoptionErrorScreen(str(error), self.copy),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                _ConfigAdoptionOperationalErrorScreen(self.copy),
            )
            return
        self.app.call_from_thread(
            self.push_terminal_screen,
            _ConfigAdoptionResultScreen(result, self.copy),
        )
