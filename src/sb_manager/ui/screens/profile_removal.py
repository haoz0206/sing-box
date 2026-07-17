"""Complete Textual workflow for planned profile removal."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_removal import (
    ProfileRemovalNotFoundError,
    ProfileRemovalPlan,
    ProfileRemovalResult,
    ProfileRemovalScope,
    ProfileRemover,
)
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.transactions.apply import ApplyOutcome
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.messages import DashboardRefreshRequested


class ProfileRemovalScreen(ConfirmedOperationScreen[None]):
    """Show exact removal impact before exposing the destructive action."""

    def __init__(
        self,
        profile_remover: ProfileRemover,
        *,
        profile_id: str,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.profile_remover = profile_remover
        self.plan: ProfileRemovalPlan = profile_remover.plan_removal(profile_id)
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        draft_only = self.plan.scope is ProfileRemovalScope.DESIRED_STATE_ONLY
        yield Header()
        with Vertical(id="profile-removal"):
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_PLAN_TITLE),
                id="profile-removal-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_REMOVAL_PLAN_PROFILE,
                    name=self.plan.profile_name,
                ),
                id="profile-removal-profile",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_REMOVAL_PLAN_DRAFT_IMPACT
                    if draft_only
                    else UiText.PROFILE_REMOVAL_PLAN_LIVE_IMPACT
                ),
                id="profile-removal-impact",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_REMOVAL_PLAN_REMAINING,
                    profiles=self.plan.remaining_profile_count,
                    applied=self.plan.remaining_applied_count,
                ),
                id="profile-removal-remaining",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_PLAN_SAFETY_PREVIEW),
                id="profile-removal-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(
                    UiText.PROFILE_REMOVAL_PLAN_CONFIRM_DRAFT
                    if draft_only
                    else UiText.PROFILE_REMOVAL_PLAN_CONFIRM_LIVE
                ),
                id="confirm-profile-removal",
                variant="error",
            )
        yield Footer()

    @on(Button.Pressed, "#confirm-profile-removal")
    def confirm_removal(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-profile-removal", Button).disabled = True
        self.query_one("#profile-removal-safety", Static).update(
            self.copy.text(UiText.PROFILE_REMOVAL_PLAN_IN_PROGRESS)
        )
        self.execute_removal()

    @work(thread=True, exclusive=True)
    def execute_removal(self) -> None:
        try:
            result = self.profile_remover.remove_profile(self.plan, confirmed=True)
        except (
            ConfigurationApplyError,
            OSError,
            ProfileRemovalNotFoundError,
            StateRevisionConflictError,
        ) as error:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileRemovalOperationalErrorScreen(str(error), copy_catalog=self.copy),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileRemovalOperationalErrorScreen(copy_catalog=self.copy),
            )
            return
        self.app.call_from_thread(
            self.push_terminal_screen,
            ProfileRemovalResultScreen(result, copy_catalog=self.copy),
        )


class ProfileRemovalResultScreen(Screen[None]):
    """Present the committed desired-state result of profile removal."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        result: ProfileRemovalResult,
        *,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.result = result
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        draft_only = self.result.scope is ProfileRemovalScope.DESIRED_STATE_ONLY
        yield Header()
        with Vertical(id="profile-removal-result"):
            if draft_only:
                yield Static(
                    self.copy.text(UiText.PROFILE_REMOVAL_RESULT_DRAFT_TITLE),
                    id="profile-removal-result-title",
                    markup=False,
                )
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_REMOVAL_RESULT_REVISION,
                        revision=self.result.committed_revision,
                    ),
                    id="profile-removal-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_REMOVAL_RESULT_DRAFT_SAFETY),
                    id="profile-removal-result-safety",
                    markup=False,
                )
            else:
                yield from self._compose_live_result()
            if self.result.committed_revision is not None:
                yield Button(
                    self.copy.text(UiText.PROFILE_REMOVAL_RESULT_RETURN_DASHBOARD),
                    id="profile-removal-return-dashboard",
                    variant="primary",
                )
        yield Footer()

    @on(Button.Pressed, "#profile-removal-return-dashboard")
    def return_to_dashboard(self) -> None:
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        self.app.post_message(DashboardRefreshRequested())

    def _compose_live_result(self) -> ComposeResult:
        transaction = self.result.transaction
        if transaction is None:
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_UNTRUSTED_TITLE),
                id="profile-removal-result-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_UNTRUSTED_DETAILS),
                id="profile-removal-result-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_UNTRUSTED_SAFETY),
                id="profile-removal-result-safety",
                markup=False,
            )
            return
        if transaction.outcome is ApplyOutcome.APPLIED:
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_APPLIED_TITLE),
                id="profile-removal-result-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_REMOVAL_RESULT_REVISION,
                    revision=self.result.committed_revision,
                ),
                id="profile-removal-result-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_APPLIED_SAFETY),
                id="profile-removal-result-safety",
                markup=False,
            )
            return
        if transaction.outcome is ApplyOutcome.VALIDATION_FAILED:
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_VALIDATION_FAILED_TITLE),
                id="profile-removal-result-title",
                markup=False,
            )
            yield Static(
                transaction.validation.diagnostics,
                id="profile-removal-result-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_VALIDATION_FAILED_SAFETY),
                id="profile-removal-result-safety",
                markup=False,
            )
            return
        if transaction.outcome is ApplyOutcome.PRECONDITION_FAILED:
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_PRECONDITION_FAILED_TITLE),
                id="profile-removal-result-title",
                markup=False,
            )
            yield Static(
                (
                    transaction.commit.diagnostics
                    if transaction.commit is not None
                    else self.copy.text(UiText.PROFILE_REMOVAL_RESULT_PRECONDITION_FALLBACK)
                ),
                id="profile-removal-result-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_PRECONDITION_SAFETY),
                id="profile-removal-result-safety",
                markup=False,
            )
            return
        if transaction.outcome is ApplyOutcome.COMMIT_FAILED:
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_COMMIT_FAILED_TITLE),
                id="profile-removal-result-title",
                markup=False,
            )
            yield Static(
                (
                    transaction.commit.diagnostics
                    if transaction.commit is not None
                    else self.copy.text(UiText.PROFILE_REMOVAL_RESULT_COMMIT_FALLBACK)
                ),
                id="profile-removal-result-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_COMMIT_SAFETY),
                id="profile-removal-result-safety",
                markup=False,
            )
            return
        rollback = transaction.rollback
        if transaction.outcome is ApplyOutcome.ROLLED_BACK:
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_ROLLED_BACK_TITLE),
                id="profile-removal-result-title",
                markup=False,
            )
            yield Static(
                (
                    rollback.diagnostics
                    if rollback is not None
                    else self.copy.text(UiText.PROFILE_REMOVAL_RESULT_ROLLED_BACK_FALLBACK)
                ),
                id="profile-removal-result-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_RESULT_ROLLED_BACK_SAFETY),
                id="profile-removal-result-safety",
                markup=False,
            )
            return
        yield Static(
            self.copy.text(UiText.PROFILE_REMOVAL_RESULT_ROLLBACK_UNKNOWN_TITLE),
            id="profile-removal-result-title",
            markup=False,
        )
        yield Static(
            (
                rollback.diagnostics
                if rollback is not None
                else self.copy.text(UiText.PROFILE_REMOVAL_RESULT_ROLLBACK_UNKNOWN_FALLBACK)
            ),
            id="profile-removal-result-details",
            markup=False,
        )
        yield Static(
            self.copy.text(UiText.PROFILE_REMOVAL_RESULT_ROLLBACK_UNKNOWN_SAFETY),
            id="profile-removal-result-safety",
            markup=False,
        )
        if rollback is not None:
            for index, instruction in enumerate(rollback.recovery_instructions):
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_REMOVAL_RESULT_RECOVERY_STEP,
                        number=index + 1,
                        instruction=instruction,
                    ),
                    id=f"profile-removal-recovery-step-{index}",
                    markup=False,
                )


class ProfileRemovalOperationalErrorScreen(Screen[None]):
    """Explain an unknown host result without claiming profile removal."""

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
        with Vertical(id="profile-removal-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_OPERATIONAL_TITLE),
                id="profile-removal-error-title",
                markup=False,
            )
            yield Static(
                self.diagnostics
                or self.copy.text(UiText.PROFILE_REMOVAL_OPERATIONAL_UNEXPECTED_DETAILS),
                id="profile-removal-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_REMOVAL_OPERATIONAL_KNOWN_SAFETY
                    if self.diagnostics is not None
                    else UiText.PROFILE_REMOVAL_OPERATIONAL_UNKNOWN_SAFETY
                ),
                id="profile-removal-error-safety",
                markup=False,
            )
        yield Footer()


class ProfileRemovalPlanningErrorScreen(Screen[None]):
    """Report an unexpected read-only removal-planning failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-removal-planning-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_PLANNING_TITLE),
                id="profile-removal-planning-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_PLANNING_DETAILS),
                id="profile-removal-planning-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_REMOVAL_PLANNING_SAFETY),
                id="profile-removal-planning-error-safety",
                markup=False,
            )
        yield Footer()
