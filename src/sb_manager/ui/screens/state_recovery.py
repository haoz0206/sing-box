"""Explicit confirmation screen for restoring one reviewed desired-state backup."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.state_recovery import (
    RecoveryAvailability,
    StateRecoveryError,
    StateRecoveryManager,
    StateRecoveryPlan,
    StateRecoveryReport,
)
from sb_manager.seams.state_recovery import (
    StateRecoveryCommit,
    StateRecoveryPreconditionError,
    StateRecoverySourceError,
)
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.messages import DashboardRefreshRequested


class StateRecoveryPanel(Widget):
    """Render every non-healthy startup state without owning recovery policy."""

    def __init__(
        self,
        report: StateRecoveryReport,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__(id="state-recovery")
        self.report = report
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        if self.report.availability is RecoveryAvailability.RECOVERY_AVAILABLE:
            assert self.report.plan is not None
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_AVAILABLE_TITLE),
                id="state-recovery-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.STATE_RECOVERY_AVAILABLE_BACKUP,
                    revision=self.report.plan.backup_revision,
                    profiles=self.report.plan.backup_profile_count,
                ),
                id="state-recovery-backup",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_AVAILABLE_GUIDANCE),
                id="state-recovery-guidance",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.STATE_RECOVERY_AVAILABLE_REVIEW),
                id="review-state-recovery",
                variant="warning",
            )
            return
        if self.report.availability is RecoveryAvailability.UNSUPPORTED_SCHEMA:
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_UNSUPPORTED_TITLE),
                id="state-recovery-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.STATE_RECOVERY_UNSUPPORTED_GUIDANCE,
                    schema=self.report.found_schema_version,
                ),
                id="state-recovery-guidance",
                markup=False,
            )
            return
        yield Static(
            self.copy.text(UiText.STATE_RECOVERY_UNAVAILABLE_TITLE),
            id="state-recovery-title",
            markup=False,
        )
        yield Static(
            self.copy.text(UiText.STATE_RECOVERY_UNAVAILABLE_GUIDANCE),
            id="state-recovery-guidance",
            markup=False,
        )


class StateRecoveryInspectionErrorPanel(Widget):
    """Keep an unexpected startup inspection failure non-disclosing and read-only."""

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__(id="state-recovery-inspection-error")
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Static(
            self.copy.text(UiText.STATE_RECOVERY_INSPECTION_ERROR_TITLE),
            id="state-recovery-inspection-error-title",
            markup=False,
        )
        yield Static(
            self.copy.text(UiText.STATE_RECOVERY_INSPECTION_ERROR_DETAILS),
            id="state-recovery-inspection-error-details",
            markup=False,
        )
        yield Static(
            self.copy.text(UiText.STATE_RECOVERY_INSPECTION_ERROR_SAFETY),
            id="state-recovery-inspection-error-safety",
            markup=False,
        )


class StateRecoveryPlanningErrorScreen(Screen[None]):
    """Report an unexpected read-only plan reinspection failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="state-recovery-planning-error"):
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_PLANNING_ERROR_TITLE),
                id="state-recovery-planning-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_PLANNING_ERROR_DETAILS),
                id="state-recovery-planning-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_PLANNING_ERROR_SAFETY),
                id="state-recovery-planning-error-safety",
                markup=False,
            )
        yield Footer()


class StateRecoveryConfirmationScreen(ConfirmedOperationScreen[None]):
    """Keep destructive file replacement behind a second explicit action."""

    def __init__(
        self,
        recovery_manager: StateRecoveryManager,
        plan: StateRecoveryPlan,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__(copy_catalog)
        self.recovery_manager = recovery_manager
        self.plan = plan

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="state-recovery-confirmation"):
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_CONFIRM_TITLE),
                id="state-recovery-confirm-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.STATE_RECOVERY_CONFIRM_BACKUP,
                    revision=self.plan.backup_revision,
                    profiles=self.plan.backup_profile_count,
                ),
                id="state-recovery-confirm-backup",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.STATE_RECOVERY_CONFIRM_PRIMARY_FINGERPRINT,
                    sha256=self.plan.primary_sha256,
                ),
                id="state-recovery-confirm-primary",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.STATE_RECOVERY_CONFIRM_BACKUP_FINGERPRINT,
                    sha256=self.plan.backup_sha256,
                ),
                id="state-recovery-confirm-backup-sha",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_CONFIRM_SAFETY),
                id="state-recovery-confirm-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.STATE_RECOVERY_CONFIRM_ACTION),
                id="confirm-state-recovery",
                variant="warning",
            )
        yield Footer()

    @on(Button.Pressed, "#confirm-state-recovery")
    def confirm_recovery(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-state-recovery", Button).disabled = True
        self.query_one("#state-recovery-confirm-safety", Static).update(
            self.copy.text(UiText.STATE_RECOVERY_CONFIRM_PROGRESS)
        )
        self.execute_recovery()

    @work(thread=True, exclusive=True)
    def execute_recovery(self) -> None:
        try:
            result = self.recovery_manager.recover(self.plan, confirmed=True)
        except (StateRecoveryError, StateRecoveryPreconditionError) as error:
            self.app.call_from_thread(
                self.push_terminal_screen,
                StateRecoveryRejectionScreen(str(error), self.copy),
            )
            return
        except StateRecoverySourceError:
            self.app.call_from_thread(
                self.push_terminal_screen,
                StateRecoveryOperationalErrorScreen(self.copy),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                StateRecoveryOperationalErrorScreen(self.copy),
            )
            return
        self.app.call_from_thread(self.finish_recovery, result)

    def finish_recovery(self, result: StateRecoveryCommit) -> None:
        self.push_terminal_screen(StateRecoveryResultScreen(result, self.copy))


class StateRecoveryResultScreen(Screen[None]):
    """Present durable recovery evidence before rebuilding the dashboard."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        result: StateRecoveryCommit,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.result = result
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        installation = self.result.installation
        yield Header()
        with Vertical(id="state-recovery-result"):
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_RESULT_TITLE),
                id="state-recovery-result-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.STATE_RECOVERY_RESULT_REVISION,
                    revision=installation.revision,
                ),
                id="state-recovery-result-revision",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.STATE_RECOVERY_RESULT_PROFILES,
                    profiles=len(installation.profiles),
                ),
                id="state-recovery-result-profiles",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.STATE_RECOVERY_RESULT_ARCHIVE,
                    path=self.result.corrupt_archive_path,
                ),
                id="state-recovery-result-archive",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_RESULT_SAFETY),
                id="state-recovery-result-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.STATE_RECOVERY_RESULT_RETURN_DASHBOARD),
                id="state-recovery-return-dashboard",
                variant="primary",
            )
        yield Footer()

    @on(Button.Pressed, "#state-recovery-return-dashboard")
    def return_to_dashboard(self) -> None:
        self.post_message(DashboardRefreshRequested())


class StateRecoveryRejectionScreen(Screen[None]):
    """Present a typed, non-retryable rejection of the reviewed plan."""

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
        with Vertical(id="state-recovery-rejection"):
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_REJECTION_TITLE),
                id="state-recovery-rejection-title",
                markup=False,
            )
            yield Static(
                self.diagnostics,
                id="state-recovery-rejection-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_REJECTION_SAFETY),
                id="state-recovery-rejection-safety",
                markup=False,
            )
        yield Footer()


class StateRecoveryOperationalErrorScreen(Screen[None]):
    """Report an unknown desired-state recovery result without disclosure."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="state-recovery-operational-error"):
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_UNKNOWN_TITLE),
                id="state-recovery-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_UNKNOWN_DETAILS),
                id="state-recovery-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.STATE_RECOVERY_UNKNOWN_SAFETY),
                id="state-recovery-error-safety",
                markup=False,
            )
        yield Footer()
