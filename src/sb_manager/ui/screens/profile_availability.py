"""Textual plan, confirmation, and result workflow for pause/resume."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_availability import (
    ProfileAvailability,
    ProfileAvailabilityManager,
    ProfileAvailabilityNotFoundError,
    ProfileAvailabilityPlan,
    ProfileAvailabilityPlanChangedError,
    ProfileAvailabilityResult,
    ProfileResumePortUnavailableError,
)
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.transactions.apply import ApplyOutcome
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.messages import DashboardRefreshRequested


class ProfileAvailabilityPlanScreen(ConfirmedOperationScreen[None]):
    """Present the exact pause/resume impact before one explicit confirmation."""

    def __init__(
        self,
        manager: ProfileAvailabilityManager,
        *,
        plan: ProfileAvailabilityPlan,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__(copy_catalog)
        self.manager = manager
        self.plan = plan

    def compose(self) -> ComposeResult:
        pausing = self.plan.target is ProfileAvailability.PAUSED
        yield Header()
        with Vertical(id="profile-availability-plan"):
            yield Static(
                self.copy.text(
                    UiText.PROFILE_AVAILABILITY_PLAN_PAUSE_TITLE
                    if pausing
                    else UiText.PROFILE_AVAILABILITY_PLAN_RESUME_TITLE
                ),
                id="profile-availability-plan-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_AVAILABILITY_PLAN_PROFILE,
                    name=self.plan.profile_name,
                ),
                id="profile-availability-plan-profile",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_AVAILABILITY_PLAN_PAUSE_IMPACT
                    if pausing
                    else UiText.PROFILE_AVAILABILITY_PLAN_RESUME_IMPACT
                ),
                id="profile-availability-plan-impact",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_AVAILABILITY_PLAN_ACTIVE_COUNT,
                    count=self.plan.remaining_active_profile_count,
                ),
                id="profile-availability-plan-count",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_PLAN_SAFETY_PREVIEW),
                id="profile-availability-plan-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(
                    UiText.PROFILE_AVAILABILITY_PLAN_CONFIRM_PAUSE
                    if pausing
                    else UiText.PROFILE_AVAILABILITY_PLAN_CONFIRM_RESUME
                ),
                id="confirm-profile-availability",
                variant="warning",
            )
        yield Footer()

    @on(Button.Pressed, "#confirm-profile-availability")
    def confirm_change(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-profile-availability", Button).disabled = True
        self.query_one("#profile-availability-plan-safety", Static).update(
            self.copy.text(UiText.PROFILE_AVAILABILITY_PLAN_IN_PROGRESS)
        )
        self.execute_change()

    @work(thread=True, exclusive=True)
    def execute_change(self) -> None:
        try:
            result = self.manager.apply_change(self.plan, confirmed=True)
        except (
            ConfigurationApplyError,
            OSError,
            ProfileAvailabilityNotFoundError,
            ProfileAvailabilityPlanChangedError,
            ProfileResumePortUnavailableError,
            StateRevisionConflictError,
        ) as error:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileAvailabilityErrorScreen(str(error), copy_catalog=self.copy),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileAvailabilityErrorScreen(copy_catalog=self.copy),
            )
            return
        self.app.call_from_thread(
            self.push_terminal_screen,
            ProfileAvailabilityResultScreen(result, copy_catalog=self.copy),
        )


class ProfileAvailabilityResultScreen(Screen[None]):
    """Present committed availability or a transaction outcome without guessing."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        result: ProfileAvailabilityResult,
        *,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.result = result
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        committed = (
            self.result.committed_revision is not None
            and self.result.transaction.outcome is ApplyOutcome.APPLIED
        )
        yield Header()
        with Vertical(id="profile-availability-result"):
            if committed:
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_AVAILABILITY_RESULT_PAUSED_TITLE
                        if self.result.availability is ProfileAvailability.PAUSED
                        else UiText.PROFILE_AVAILABILITY_RESULT_RESUMED_TITLE
                    ),
                    id="profile-availability-result-title",
                    markup=False,
                )
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_AVAILABILITY_RESULT_REVISION,
                        revision=self.result.committed_revision,
                    ),
                    id="profile-availability-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_SUCCESS_SAFETY),
                    id="profile-availability-result-safety",
                    markup=False,
                )
                yield Button(
                    self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_RETURN_DASHBOARD),
                    id="profile-availability-return-dashboard",
                    variant="primary",
                )
            else:
                yield from self._compose_failed_result()
        yield Footer()

    def _compose_failed_result(self) -> ComposeResult:
        transaction = self.result.transaction
        if transaction.outcome is ApplyOutcome.VALIDATION_FAILED:
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_VALIDATION_FAILED_TITLE),
                id="profile-availability-result-title",
                markup=False,
            )
            yield Static(
                transaction.validation.diagnostics,
                id="profile-availability-result-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_VALIDATION_FAILED_SAFETY),
                id="profile-availability-result-safety",
                markup=False,
            )
            return
        if transaction.outcome is ApplyOutcome.PRECONDITION_FAILED:
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_PRECONDITION_FAILED_TITLE),
                id="profile-availability-result-title",
                markup=False,
            )
            yield Static(
                (
                    transaction.commit.diagnostics
                    if transaction.commit is not None
                    else self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_PRECONDITION_FALLBACK)
                ),
                id="profile-availability-result-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_PRECONDITION_SAFETY),
                id="profile-availability-result-safety",
                markup=False,
            )
            return
        if transaction.outcome is ApplyOutcome.COMMIT_FAILED:
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_COMMIT_FAILED_TITLE),
                id="profile-availability-result-title",
                markup=False,
            )
            yield Static(
                (
                    transaction.commit.diagnostics
                    if transaction.commit is not None
                    else self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_COMMIT_FALLBACK)
                ),
                id="profile-availability-result-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_COMMIT_SAFETY),
                id="profile-availability-result-safety",
                markup=False,
            )
            return
        rollback = transaction.rollback
        if transaction.outcome is ApplyOutcome.ROLLED_BACK:
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_ROLLED_BACK_TITLE),
                id="profile-availability-result-title",
                markup=False,
            )
            yield Static(
                (
                    rollback.diagnostics
                    if rollback is not None
                    else self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_ROLLED_BACK_FALLBACK)
                ),
                id="profile-availability-result-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_ROLLED_BACK_SAFETY),
                id="profile-availability-result-safety",
                markup=False,
            )
            return
        yield Static(
            self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_ROLLBACK_UNKNOWN_TITLE),
            id="profile-availability-result-title",
            markup=False,
        )
        yield Static(
            (
                rollback.diagnostics
                if rollback is not None
                else self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_ROLLBACK_UNKNOWN_FALLBACK)
            ),
            id="profile-availability-result-details",
            markup=False,
        )
        yield Static(
            self.copy.text(UiText.PROFILE_AVAILABILITY_RESULT_ROLLBACK_UNKNOWN_SAFETY),
            id="profile-availability-result-safety",
            markup=False,
        )
        if rollback is not None:
            for index, instruction in enumerate(rollback.recovery_instructions):
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_AVAILABILITY_RESULT_RECOVERY_STEP,
                        number=index + 1,
                        instruction=instruction,
                    ),
                    id=f"profile-availability-recovery-step-{index}",
                    markup=False,
                )

    @on(Button.Pressed, "#profile-availability-return-dashboard")
    def return_to_dashboard(self) -> None:
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        self.app.post_message(DashboardRefreshRequested())


class ProfileAvailabilityErrorScreen(Screen[None]):
    """Conservatively report an unavailable or stale availability transition."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        diagnostics: str | None = None,
        *,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.diagnostics = diagnostics
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-availability-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_OPERATIONAL_TITLE),
                id="profile-availability-error-title",
                markup=False,
            )
            yield Static(
                self.diagnostics
                or self.copy.text(UiText.PROFILE_AVAILABILITY_OPERATIONAL_UNEXPECTED_DETAILS),
                id="profile-availability-error-details",
                markup=False,
            )
            yield Static(
                (
                    self.copy.text(UiText.PROFILE_AVAILABILITY_OPERATIONAL_KNOWN_SAFETY)
                    if self.diagnostics is not None
                    else self.copy.text(UiText.PROFILE_AVAILABILITY_OPERATIONAL_UNKNOWN_SAFETY)
                ),
                id="profile-availability-error-safety",
                markup=False,
            )
        yield Footer()


class ProfileAvailabilityPlanningErrorScreen(Screen[None]):
    """Report an unexpected read-only availability-planning failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-availability-planning-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_PLANNING_TITLE),
                id="profile-availability-planning-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_PLANNING_DETAILS),
                id="profile-availability-planning-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_AVAILABILITY_PLANNING_SAFETY),
                id="profile-availability-planning-error-safety",
                markup=False,
            )
        yield Footer()
