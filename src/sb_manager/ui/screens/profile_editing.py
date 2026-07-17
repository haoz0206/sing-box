"""Complete Textual workflow for editing operator-facing profile metadata."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_details import ProfileDetails
from sb_manager.application.profile_editing import (
    PlanProfileEditRequest,
    ProfileEditNoChangesError,
    ProfileEditNotFoundError,
    ProfileEditor,
    ProfileEditPlan,
    ProfileEditPlanChangedError,
    ProfileEditPortUnavailableError,
    ProfileEditResult,
    ProfileEditScope,
    ProfileEditValidationError,
)
from sb_manager.domain.installation import PortSelection
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.transactions.apply import ApplyOutcome
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.messages import DashboardRefreshRequested


class ProfileEditFormScreen(Screen[None]):
    """Collect editable metadata without creating a plan on navigation."""

    BINDINGS: ClassVar[list[BindingType]] = [
        (
            "escape",
            "app.pop_screen",
            SIMPLIFIED_CHINESE.text(UiText.PROFILE_EDIT_CANCEL),
        )
    ]

    def __init__(
        self,
        profile_editor: ProfileEditor,
        *,
        details: ProfileDetails,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.profile_editor = profile_editor
        self.details = details
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profile-edit"):
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_TITLE),
                id="profile-edit-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_GUIDANCE),
                id="profile-edit-guidance",
                markup=False,
            )
            yield Label(
                self.copy.text(UiText.PROFILE_EDIT_NAME_LABEL),
                id="profile-edit-name-label",
                markup=False,
            )
            yield Input(value=self.details.profile_name, id="profile-edit-name")
            yield Label(
                self.copy.text(UiText.PROFILE_EDIT_SERVER_ADDRESS_LABEL),
                id="profile-edit-server-address-label",
                markup=False,
            )
            yield Input(
                value=self.details.server_address or "",
                id="profile-edit-server-address",
            )
            yield Label(
                self.copy.text(UiText.PROFILE_EDIT_LISTEN_PORT_LABEL),
                id="profile-edit-listen-port-label",
                markup=False,
            )
            yield Input(
                value=(
                    str(self.details.listen_port) if self.details.listen_port is not None else ""
                ),
                placeholder=self.copy.text(UiText.PROFILE_EDIT_LISTEN_PORT_PLACEHOLDER),
                id="profile-edit-listen-port",
            )
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_PORT_GUIDANCE),
                id="profile-edit-port-guidance",
                markup=False,
            )
            yield Static("", id="profile-edit-error", markup=False)
            yield Button(
                self.copy.text(UiText.PROFILE_EDIT_PREVIEW),
                id="preview-profile-edit",
                variant="primary",
            )
        yield Footer()

    @on(Button.Pressed, "#preview-profile-edit")
    def preview_edit(self) -> None:
        listen_port_input = self.query_one("#profile-edit-listen-port", Input)
        listen_port_text = listen_port_input.value.strip()
        try:
            listen_port = int(listen_port_text) if listen_port_text else None
        except ValueError:
            self.query_one("#profile-edit-error", Static).update(
                self.copy.text(UiText.PROFILE_EDIT_PORT_INVALID)
            )
            listen_port_input.focus()
            return
        try:
            plan = self.profile_editor.plan_edit(
                PlanProfileEditRequest(
                    profile_id=self.details.profile_id,
                    profile_name=self.query_one("#profile-edit-name", Input).value,
                    server_address=self.query_one("#profile-edit-server-address", Input).value,
                    listen_port=listen_port,
                )
            )
        except ProfileEditValidationError as error:
            self.query_one("#profile-edit-error", Static).update(error.message)
            self.query_one(f"#profile-edit-{error.field.removeprefix('profile_')}").focus()
            return
        except ProfileEditNoChangesError:
            self.query_one("#profile-edit-error", Static).update(
                self.copy.text(UiText.PROFILE_EDIT_NO_CHANGES)
            )
            return
        except ProfileEditNotFoundError:
            self.query_one("#profile-edit-error", Static).update(
                self.copy.text(UiText.PROFILE_EDIT_NOT_FOUND)
            )
            return
        except Exception:
            self.app.push_screen(ProfileEditPlanningErrorScreen(self.copy))
            return
        self.app.push_screen(
            ProfileEditPlanScreen(
                self.profile_editor,
                plan=plan,
                copy_catalog=self.copy,
            )
        )


class ProfileEditPlanningErrorScreen(Screen[None]):
    """Report an unexpected read-only edit-planning failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-edit-planning-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_PLANNING_TITLE),
                id="profile-edit-planning-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_PLANNING_DETAILS),
                id="profile-edit-planning-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_PLANNING_SAFETY),
                id="profile-edit-planning-error-safety",
                markup=False,
            )
        yield Footer()


class ProfileEditPlanScreen(ConfirmedOperationScreen[None]):
    """Present exact normalized changes and their host impact."""

    def __init__(
        self,
        profile_editor: ProfileEditor,
        *,
        plan: ProfileEditPlan,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__(copy_catalog)
        self.profile_editor = profile_editor
        self.plan = plan

    def compose(self) -> ComposeResult:
        changes: list[str] = []
        if "profile_name" in self.plan.changed_fields:
            changes.append(
                self.copy.text(
                    UiText.PROFILE_EDIT_PLAN_CHANGE_NAME,
                    previous=self.plan.previous_profile_name,
                    current=self.plan.profile_name,
                )
            )
        if "server_address" in self.plan.changed_fields:
            changes.append(
                self.copy.text(
                    UiText.PROFILE_EDIT_PLAN_CHANGE_SERVER_ADDRESS,
                    previous=(
                        self.plan.previous_server_address
                        or self.copy.text(UiText.PROFILE_EDIT_PLAN_VALUE_UNSET)
                    ),
                    current=(
                        self.plan.server_address
                        or self.copy.text(UiText.PROFILE_EDIT_PLAN_VALUE_UNSET)
                    ),
                )
            )
        if "listen_port" in self.plan.changed_fields:
            changes.append(
                self.copy.text(
                    UiText.PROFILE_EDIT_PLAN_CHANGE_LISTEN_PORT,
                    previous=(
                        self.plan.previous_listen_port
                        if self.plan.previous_listen_port is not None
                        else self.copy.text(UiText.PROFILE_EDIT_PLAN_VALUE_AUTOMATIC)
                    ),
                    current=(
                        self.plan.listen_port
                        if self.plan.listen_port is not None
                        else self.copy.text(
                            UiText.PROFILE_EDIT_PLAN_VALUE_AUTOMATIC_AT_CONFIRMATION
                        )
                    ),
                )
            )
        if "port_selection" in self.plan.changed_fields:
            changes.append(
                self.copy.text(
                    UiText.PROFILE_EDIT_PLAN_CHANGE_PORT_SELECTION,
                    previous=self._port_selection_label(self.plan.previous_port_selection),
                    current=self._port_selection_label(self.plan.port_selection),
                )
            )
        desired_only = self.plan.scope is ProfileEditScope.DESIRED_STATE_ONLY
        yield Header()
        with Vertical(id="profile-edit-plan"):
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_PLAN_TITLE),
                id="profile-edit-plan-title",
                markup=False,
            )
            yield Static("\n".join(changes), id="profile-edit-plan-changes", markup=False)
            yield Static(
                (
                    self.copy.text(UiText.PROFILE_EDIT_PLAN_IMPACT_DESIRED)
                    if desired_only
                    else self.copy.text(UiText.PROFILE_EDIT_PLAN_IMPACT_LIVE)
                ),
                id="profile-edit-plan-impact",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_PLAN_SAFETY_PREVIEW),
                id="profile-edit-plan-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(
                    UiText.PROFILE_EDIT_PLAN_CONFIRM_DESIRED
                    if desired_only
                    else UiText.PROFILE_EDIT_PLAN_CONFIRM_LIVE
                ),
                id="confirm-profile-edit",
                variant="warning" if desired_only else "error",
            )
        yield Footer()

    def _port_selection_label(self, selection: PortSelection) -> str:
        return self.copy.text(
            UiText.PROFILE_EDIT_PLAN_VALUE_AUTOMATIC
            if selection is PortSelection.AUTOMATIC
            else UiText.PROFILE_EDIT_PLAN_VALUE_FIXED
        )

    @on(Button.Pressed, "#confirm-profile-edit")
    def confirm_edit(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-profile-edit", Button).disabled = True
        self.query_one("#profile-edit-plan-safety", Static).update(
            self.copy.text(UiText.PROFILE_EDIT_PLAN_IN_PROGRESS)
        )
        self.execute_edit()

    @work(thread=True, exclusive=True)
    def execute_edit(self) -> None:
        try:
            result = self.profile_editor.apply_edit(self.plan, confirmed=True)
        except ProfileEditPortUnavailableError as error:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileEditPortConflictScreen(str(error), copy_catalog=self.copy),
            )
            return
        except (
            ProfileEditNoChangesError,
            ProfileEditNotFoundError,
            ProfileEditPlanChangedError,
            StateRevisionConflictError,
        ) as error:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileEditConflictScreen(str(error), copy_catalog=self.copy),
            )
            return
        except (
            ConfigurationApplyError,
            OSError,
            ProfileEditValidationError,
        ) as error:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileEditOperationalErrorScreen(str(error), copy_catalog=self.copy),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ProfileEditOperationalErrorScreen(copy_catalog=self.copy),
            )
            return
        self.app.call_from_thread(
            self.push_terminal_screen,
            ProfileEditResultScreen(result, copy_catalog=self.copy),
        )


class ProfileEditResultScreen(Screen[None]):
    """Present the committed desired-state result of profile editing."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        result: ProfileEditResult,
        *,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.result = result
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-edit-result"):
            if self.result.scope is ProfileEditScope.DESIRED_STATE_ONLY:
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_DESIRED_TITLE),
                    id="profile-edit-result-title",
                    markup=False,
                )
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_EDIT_RESULT_REVISION,
                        revision=self.result.committed_revision,
                    ),
                    id="profile-edit-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_DESIRED_SAFETY),
                    id="profile-edit-result-safety",
                    markup=False,
                )
            elif (
                self.result.transaction is not None
                and self.result.transaction.outcome is ApplyOutcome.APPLIED
            ):
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_APPLIED_TITLE),
                    id="profile-edit-result-title",
                    markup=False,
                )
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_EDIT_RESULT_REVISION,
                        revision=self.result.committed_revision,
                    ),
                    id="profile-edit-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_APPLIED_SAFETY),
                    id="profile-edit-result-safety",
                    markup=False,
                )
            elif (
                self.result.transaction is not None
                and self.result.transaction.outcome is ApplyOutcome.VALIDATION_FAILED
            ):
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_VALIDATION_FAILED_TITLE),
                    id="profile-edit-result-title",
                    markup=False,
                )
                yield Static(
                    self.result.transaction.validation.diagnostics,
                    id="profile-edit-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_VALIDATION_FAILED_SAFETY),
                    id="profile-edit-result-safety",
                    markup=False,
                )
            elif (
                self.result.transaction is not None
                and self.result.transaction.outcome is ApplyOutcome.PRECONDITION_FAILED
            ):
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_PRECONDITION_FAILED_TITLE),
                    id="profile-edit-result-title",
                    markup=False,
                )
                yield Static(
                    (
                        self.result.transaction.commit.diagnostics
                        if self.result.transaction.commit is not None
                        else self.copy.text(UiText.PROFILE_EDIT_RESULT_PRECONDITION_FALLBACK)
                    ),
                    id="profile-edit-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_PRECONDITION_SAFETY),
                    id="profile-edit-result-safety",
                    markup=False,
                )
            elif (
                self.result.transaction is not None
                and self.result.transaction.outcome is ApplyOutcome.COMMIT_FAILED
            ):
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_COMMIT_FAILED_TITLE),
                    id="profile-edit-result-title",
                    markup=False,
                )
                yield Static(
                    (
                        self.result.transaction.commit.diagnostics
                        if self.result.transaction.commit is not None
                        else self.copy.text(UiText.PROFILE_EDIT_RESULT_COMMIT_FALLBACK)
                    ),
                    id="profile-edit-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_COMMIT_SAFETY),
                    id="profile-edit-result-safety",
                    markup=False,
                )
            elif (
                self.result.transaction is not None
                and self.result.transaction.outcome is ApplyOutcome.ROLLED_BACK
            ):
                rollback = self.result.transaction.rollback
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_ROLLED_BACK_TITLE),
                    id="profile-edit-result-title",
                    markup=False,
                )
                yield Static(
                    (
                        rollback.diagnostics
                        if rollback is not None
                        else self.copy.text(UiText.PROFILE_EDIT_RESULT_ROLLED_BACK_FALLBACK)
                    ),
                    id="profile-edit-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_ROLLED_BACK_SAFETY),
                    id="profile-edit-result-safety",
                    markup=False,
                )
            elif self.result.transaction is not None:
                rollback = self.result.transaction.rollback
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_ROLLBACK_UNKNOWN_TITLE),
                    id="profile-edit-result-title",
                    markup=False,
                )
                yield Static(
                    (
                        rollback.diagnostics
                        if rollback is not None
                        else self.copy.text(UiText.PROFILE_EDIT_RESULT_ROLLBACK_UNKNOWN_FALLBACK)
                    ),
                    id="profile-edit-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_ROLLBACK_UNKNOWN_SAFETY),
                    id="profile-edit-result-safety",
                    markup=False,
                )
                if rollback is not None:
                    for index, instruction in enumerate(rollback.recovery_instructions):
                        yield Static(
                            self.copy.text(
                                UiText.PROFILE_EDIT_RESULT_RECOVERY_STEP,
                                number=index + 1,
                                instruction=instruction,
                            ),
                            id=f"profile-edit-recovery-step-{index}",
                            markup=False,
                        )
            if self.result.committed_revision is not None and self.result.listen_port is not None:
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_EDIT_RESULT_LISTEN_PORT,
                        port=self.result.listen_port,
                    ),
                    id="profile-edit-result-listen-port",
                    markup=False,
                )
            if self.result.committed_revision is not None:
                yield Button(
                    self.copy.text(UiText.PROFILE_EDIT_RESULT_RETURN_DASHBOARD),
                    id="profile-edit-return-dashboard",
                    variant="primary",
                )
        yield Footer()

    @on(Button.Pressed, "#profile-edit-return-dashboard")
    def return_to_dashboard(self) -> None:
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        self.app.post_message(DashboardRefreshRequested())


class ProfileEditOperationalErrorScreen(Screen[None]):
    """Explain an unknown host result without claiming profile changes."""

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
        with Vertical(id="profile-edit-operational-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_OPERATIONAL_TITLE),
                id="profile-edit-error-title",
                markup=False,
            )
            yield Static(
                self.diagnostics
                or self.copy.text(UiText.PROFILE_EDIT_OPERATIONAL_UNEXPECTED_DETAILS),
                id="profile-edit-error-details",
                markup=False,
            )
            yield Static(
                (
                    self.copy.text(UiText.PROFILE_EDIT_OPERATIONAL_KNOWN_SAFETY)
                    if self.diagnostics is not None
                    else self.copy.text(UiText.PROFILE_EDIT_OPERATIONAL_UNKNOWN_SAFETY)
                ),
                id="profile-edit-error-safety",
                markup=False,
            )
        yield Footer()


class ProfileEditPortConflictScreen(Screen[None]):
    """Explain a safe confirmation-time port conflict without implying host mutation."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        diagnostics: str,
        *,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.diagnostics = diagnostics
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-edit-port-conflict"):
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_PORT_CONFLICT_TITLE),
                id="profile-edit-port-conflict-title",
                markup=False,
            )
            yield Static(
                self.diagnostics,
                id="profile-edit-port-conflict-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_PORT_CONFLICT_SAFETY),
                id="profile-edit-port-conflict-safety",
                markup=False,
            )
        yield Footer()


class ProfileEditConflictScreen(Screen[None]):
    """Explain that a reviewed edit plan is no longer current."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        diagnostics: str,
        *,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.diagnostics = diagnostics
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-edit-conflict"):
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_CONFLICT_TITLE),
                id="profile-edit-conflict-title",
                markup=False,
            )
            yield Static(
                self.diagnostics,
                id="profile-edit-conflict-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_EDIT_CONFLICT_SAFETY),
                id="profile-edit-conflict-safety",
                markup=False,
            )
        yield Footer()
