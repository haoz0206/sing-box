"""Complete exact-version core update workflow behind one screen interface."""

from typing import ClassVar, cast

from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select, Static

from sb_manager.application.core_update import (
    CoreArtifactAcquisitionError,
    CorePrereleaseConsentRequiredError,
    CoreUpdatePlan,
    CoreUpdater,
    CoreUpdateResult,
    PlanCoreUpdateRequest,
)
from sb_manager.application.protocol_compatibility import (
    CoreTargetIncompatibleWithDesiredState,
)
from sb_manager.seams.artifact_source import ArtifactArchitecture
from sb_manager.seams.core_activator import CoreActivationError
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.core_artifact_copy import artifact_evidence_widgets, artifact_warning_widgets

_PlanningOutcome = CoreUpdatePlan | UiText | CoreTargetIncompatibleWithDesiredState | None


class CoreUpdateResultScreen(Screen[None]):
    """Present the complete evidence returned by a successful activation."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        result: CoreUpdateResult,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.result = result
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        activation = self.result.activation
        yield Header()
        with Vertical(id="core-update-result"):
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_RESULT_TITLE),
                id="core-update-result-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_UPDATE_RESULT_VERSION,
                    version=activation.version,
                ),
                id="core-update-result-version",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_UPDATE_RESULT_BINARY,
                    path=str(activation.binary_path),
                ),
                id="core-update-result-binary",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_UPDATE_RESULT_TARGET,
                    target=activation.activated_target,
                ),
                id="core-update-result-target",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_UPDATE_RESULT_PREVIOUS,
                    target=(
                        activation.previous_target
                        or self.copy.text(UiText.CORE_UPDATE_RESULT_PREVIOUS_NONE)
                    ),
                ),
                id="core-update-result-previous",
                markup=False,
            )
        yield Footer()


class CoreUpdateErrorScreen(Screen[None]):
    """Distinguish acquisition failure from an unknown privileged host result."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        diagnostics: str,
        *,
        host_result_unknown: bool,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.diagnostics = diagnostics
        self.host_result_unknown = host_result_unknown
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-update-error"):
            yield Static(
                self.copy.text(
                    UiText.CORE_UPDATE_ERROR_UNKNOWN_TITLE
                    if self.host_result_unknown
                    else UiText.CORE_UPDATE_ERROR_ACQUISITION_TITLE
                ),
                id="core-update-error-title",
                markup=False,
            )
            yield Static(
                self.diagnostics,
                id="core-update-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_UPDATE_ERROR_UNKNOWN_SAFETY
                    if self.host_result_unknown
                    else UiText.CORE_UPDATE_ERROR_ACQUISITION_SAFETY
                ),
                id="core-update-error-safety",
                markup=False,
            )
        yield Footer()


class CoreUpdatePlanningErrorScreen(Screen[None]):
    """Report an unexpected read-only core-update planning failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-update-planning-error"):
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_PLANNING_ERROR_TITLE),
                id="core-update-planning-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_PLANNING_ERROR_DETAILS),
                id="core-update-planning-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_PLANNING_ERROR_SAFETY),
                id="core-update-planning-error-safety",
                markup=False,
            )
        yield Footer()


class CoreTargetCompatibilityScreen(Screen[None]):
    """Show structured blocker identities for a rejected core target."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        error: CoreTargetIncompatibleWithDesiredState,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.error = error
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-target-compatibility"):
            yield Static(
                self.copy.text(UiText.CORE_TARGET_COMPATIBILITY_TITLE),
                id="core-target-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_TARGET_COMPATIBILITY_VERSION,
                    version=self.error.target_version,
                ),
                id="core-target-version",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_TARGET_COMPATIBILITY_BLOCKERS,
                    names=", ".join(self.error.blocking_profile_names),
                ),
                id="core-target-blockers",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CORE_TARGET_COMPATIBILITY_SAFETY),
                id="core-target-safety",
                markup=False,
            )
        yield Footer()


class _CoreUpdatePlanScreen(ConfirmedOperationScreen[None]):
    """Show frozen artifact evidence and require explicit host-mutation consent."""

    def __init__(
        self,
        core_updater: CoreUpdater,
        plan: CoreUpdatePlan,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__(copy_catalog)
        self.core_updater = core_updater
        self.plan = plan

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-update-plan"):
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_PLAN_TITLE),
                id="core-update-plan-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_UPDATE_PLAN_VERSION,
                    version=self.plan.version,
                ),
                id="core-update-plan-version",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_UPDATE_PLAN_ARCHITECTURE,
                    architecture=self.plan.architecture.value,
                ),
                id="core-update-plan-architecture",
                markup=False,
            )
            yield from artifact_evidence_widgets(
                self.copy,
                self.plan.artifact,
                field_id_prefix="core-update-plan",
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_UPDATE_PLAN_SOURCE,
                    source=self.plan.source,
                ),
                id="core-update-plan-source",
                markup=False,
            )
            yield from artifact_warning_widgets(
                self.copy,
                self.plan.warnings,
                warning_id_prefix="core-update-warning",
            )
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_PLAN_SAFETY),
                id="core-update-plan-safety",
                markup=False,
            )
            yield Static("", id="core-update-progress", markup=False)
            yield Button(
                self.copy.text(UiText.CORE_UPDATE_PLAN_CONFIRM),
                id="confirm-core-update",
                variant="error",
            )
        yield Footer()

    @on(Button.Pressed, "#confirm-core-update")
    def confirm_core_update(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-core-update", Button).disabled = True
        self.query_one("#core-update-progress", Static).update(
            self.copy.text(UiText.CORE_UPDATE_PLAN_PROGRESS)
        )
        self.execute_core_update()

    @work(thread=True, exclusive=True)
    def execute_core_update(self) -> None:
        try:
            result = self.core_updater.execute(self.plan, confirmed=True)
        except CoreArtifactAcquisitionError as error:
            self.app.call_from_thread(
                self.push_terminal_screen,
                CoreUpdateErrorScreen(
                    str(error),
                    host_result_unknown=False,
                    copy_catalog=self.copy,
                ),
            )
            return
        except CoreActivationError as error:
            self.app.call_from_thread(
                self.push_terminal_screen,
                CoreUpdateErrorScreen(
                    str(error),
                    host_result_unknown=True,
                    copy_catalog=self.copy,
                ),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                CoreUpdateErrorScreen(
                    self.copy.text(UiText.CORE_UPDATE_ERROR_UNEXPECTED_DETAILS),
                    host_result_unknown=True,
                    copy_catalog=self.copy,
                ),
            )
            return
        self.app.call_from_thread(
            self.push_terminal_screen,
            CoreUpdateResultScreen(result, self.copy),
        )


class CoreUpdateFormScreen(Screen[None]):
    """Collect, plan, confirm, and execute one exact core version update."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        core_updater: CoreUpdater,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.core_updater = core_updater
        self.copy = copy_catalog
        self._planning_generation = 0
        self._completed_planning_generation: int | None = None
        self._deferred_planning_outcome: tuple[int, _PlanningOutcome] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-update-form"):
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_FORM_TITLE),
                id="core-update-form-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_FORM_GUIDANCE),
                id="core-update-form-guidance",
                markup=False,
            )
            yield Label(
                self.copy.text(UiText.CORE_UPDATE_FORM_VERSION_LABEL),
                classes="field-label",
            )
            yield Input(
                placeholder=self.copy.text(UiText.CORE_UPDATE_FORM_VERSION_PLACEHOLDER),
                id="core-version",
            )
            yield Label(
                self.copy.text(UiText.CORE_UPDATE_FORM_ARCHITECTURE_LABEL),
                classes="field-label",
            )
            yield Select(
                (
                    (
                        self.copy.text(UiText.CORE_UPDATE_FORM_ARCHITECTURE_AMD64),
                        ArtifactArchitecture.AMD64,
                    ),
                    (
                        self.copy.text(UiText.CORE_UPDATE_FORM_ARCHITECTURE_ARM64),
                        ArtifactArchitecture.ARM64,
                    ),
                ),
                value=ArtifactArchitecture.AMD64,
                allow_blank=False,
                id="core-architecture",
            )
            yield Checkbox(
                self.copy.text(UiText.CORE_UPDATE_FORM_PRERELEASE_CONSENT),
                id="allow-prerelease",
            )
            yield Static(
                "",
                id="core-update-form-error",
                classes="field-error",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.CORE_UPDATE_FORM_PREVIEW),
                id="preview-core-update",
                variant="primary",
            )
        yield Footer()

    @on(Button.Pressed, "#preview-core-update")
    def preview_core_update(self) -> None:
        version = self.query_one("#core-version", Input).value.strip()
        architecture = cast(
            Select[ArtifactArchitecture],
            self.query_one("#core-architecture", Select),
        ).value
        error = self.query_one("#core-update-form-error", Static)
        error.update("")
        if not isinstance(architecture, ArtifactArchitecture):
            error.update(self.copy.text(UiText.CORE_UPDATE_FORM_ERROR_ARCHITECTURE))
            return
        request = PlanCoreUpdateRequest(
            version=version,
            architecture=architecture,
            allow_prerelease=self.query_one("#allow-prerelease", Checkbox).value,
        )
        self._planning_generation += 1
        generation = self._planning_generation
        self._deferred_planning_outcome = None
        self.query_one("#preview-core-update", Button).disabled = True
        error.update(self.copy.text(UiText.CORE_UPDATE_FORM_PLANNING))
        self.plan_core_update(request, generation)

    @work(thread=True, exclusive=True)
    def plan_core_update(self, request: PlanCoreUpdateRequest, generation: int) -> None:
        try:
            plan = self.core_updater.plan(request)
        except ValueError:
            self.app.call_from_thread(
                self._show_planning_validation,
                generation,
                UiText.CORE_UPDATE_FORM_ERROR_INVALID_VERSION,
            )
            return
        except CorePrereleaseConsentRequiredError:
            self.app.call_from_thread(
                self._show_planning_validation,
                generation,
                UiText.CORE_UPDATE_FORM_ERROR_PRERELEASE_CONSENT,
            )
            return
        except CoreTargetIncompatibleWithDesiredState as error:
            self.app.call_from_thread(self._show_target_incompatibility, generation, error)
            return
        except Exception:
            self.app.call_from_thread(self._show_planning_error, generation)
            return
        self.app.call_from_thread(self._show_plan, generation, plan)

    def _planning_is_relevant(self, generation: int) -> bool:
        return (
            generation == self._planning_generation
            and generation != self._completed_planning_generation
            and self in self.app.screen_stack
        )

    def _deliver_or_defer_planning(
        self,
        generation: int,
        outcome: _PlanningOutcome,
    ) -> None:
        if not self._planning_is_relevant(generation):
            return
        if self.app.screen is not self:
            self._deferred_planning_outcome = (generation, outcome)
            return
        self._consume_planning_outcome(generation, outcome)

    def _consume_planning_outcome(
        self,
        generation: int,
        outcome: _PlanningOutcome,
    ) -> None:
        if not self._planning_is_relevant(generation) or self.app.screen is not self:
            return
        self._completed_planning_generation = generation
        self._deferred_planning_outcome = None
        self.query_one("#preview-core-update", Button).disabled = False
        error = self.query_one("#core-update-form-error", Static)
        if isinstance(outcome, UiText):
            error.update(self.copy.text(outcome))
            return
        if isinstance(outcome, CoreTargetIncompatibleWithDesiredState):
            error.update("")
            self.app.push_screen(CoreTargetCompatibilityScreen(outcome, self.copy))
            return
        if outcome is None:
            self.app.push_screen(CoreUpdatePlanningErrorScreen(self.copy))
            return
        error.update("")
        self.app.push_screen(_CoreUpdatePlanScreen(self.core_updater, outcome, self.copy))

    @on(events.ScreenResume)
    def resume_deferred_planning(self) -> None:
        deferred = self._deferred_planning_outcome
        if deferred is None:
            return
        self._deferred_planning_outcome = None
        self._deliver_or_defer_planning(*deferred)

    def _show_planning_validation(self, generation: int, message: UiText) -> None:
        self._deliver_or_defer_planning(generation, message)

    def _show_planning_error(self, generation: int) -> None:
        self._deliver_or_defer_planning(generation, None)

    def _show_target_incompatibility(
        self,
        generation: int,
        error: CoreTargetIncompatibleWithDesiredState,
    ) -> None:
        self._deliver_or_defer_planning(generation, error)

    def _show_plan(self, generation: int, plan: CoreUpdatePlan) -> None:
        self._deliver_or_defer_planning(generation, plan)
