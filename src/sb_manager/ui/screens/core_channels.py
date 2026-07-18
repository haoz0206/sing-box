"""Stable/Preview discovery and exact channel-action workflow."""

from typing import ClassVar, cast

from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Select, Static

from sb_manager.application.core_update import (
    CoreArtifactAcquisitionError,
    CoreChannelManager,
    CoreChannelPlan,
    CoreChannelPlanKind,
    PlanCoreChannelRequest,
)
from sb_manager.seams.artifact_source import ArtifactArchitecture, CoreReleaseChannel
from sb_manager.seams.core_activator import CoreActivationError
from sb_manager.seams.core_switcher import CoreSwitchError
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.core_artifact_copy import TRUST_COPY, WARNING_COPY
from sb_manager.ui.screens.core_update import CoreUpdateErrorScreen, CoreUpdateResultScreen

_ChannelPlanningOutcome = CoreChannelPlan | None


def _channel_label(channel: CoreReleaseChannel) -> str:
    return "Stable" if channel is CoreReleaseChannel.STABLE else "Preview"


class CoreChannelCurrentScreen(Screen[None]):
    """Report that channel discovery resolved to the already-active release."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        plan: CoreChannelPlan,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.plan = plan
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-channel-current"):
            yield Static(
                self.copy.text(
                    UiText.CORE_CHANNEL_CURRENT_TITLE,
                    channel=_channel_label(self.plan.channel),
                ),
                id="core-channel-current-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_CHANNEL_CURRENT_VERSION,
                    version=self.plan.version,
                ),
                id="core-channel-current-version",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CORE_CHANNEL_CURRENT_SAFETY),
                id="core-channel-current-safety",
                markup=False,
            )
        yield Footer()


class CoreChannelPlanningErrorScreen(Screen[None]):
    """Hide unexpected discovery details while preserving the no-mutation claim."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-channel-planning-error"):
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_PLANNING_ERROR_TITLE),
                id="core-channel-planning-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_PLANNING_ERROR_DETAILS),
                id="core-channel-planning-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_PLANNING_ERROR_SAFETY),
                id="core-channel-planning-error-safety",
                markup=False,
            )
        yield Footer()


class CoreChannelPlanScreen(ConfirmedOperationScreen[None]):
    """Render one frozen channel action and require explicit host consent."""

    def __init__(
        self,
        core_channels: CoreChannelManager,
        plan: CoreChannelPlan,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__(copy_catalog)
        self.core_channels = core_channels
        self.plan = plan

    @property
    def is_switch(self) -> bool:
        return self.plan.kind is CoreChannelPlanKind.SWITCH_RETAINED

    def compose(self) -> ComposeResult:
        action_key = (
            UiText.CORE_CHANNEL_ACTION_SWITCH
            if self.is_switch
            else UiText.CORE_CHANNEL_ACTION_ACQUIRE
        )
        yield Header()
        with Vertical(id="core-channel-plan"):
            yield Static(
                self.copy.text(
                    UiText.CORE_CHANNEL_PLAN_TITLE,
                    channel=_channel_label(self.plan.channel),
                ),
                id="core-channel-plan-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CORE_UPDATE_PLAN_VERSION, version=self.plan.version),
                id="core-channel-plan-version",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_UPDATE_PLAN_ARCHITECTURE,
                    architecture=self.plan.architecture.value,
                ),
                id="core-channel-plan-architecture",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.CORE_CHANNEL_PLAN_ACTION,
                    action=self.copy.text(action_key),
                ),
                id="core-channel-plan-action",
                markup=False,
            )
            if self.plan.exact_update is not None:
                artifact = self.plan.exact_update.artifact
                yield Static(
                    self.copy.text(
                        UiText.CORE_UPDATE_PLAN_ASSET,
                        asset=artifact.asset_name,
                    ),
                    id="core-channel-plan-asset",
                    markup=False,
                )
                yield Static(
                    self.copy.text(
                        UiText.CORE_UPDATE_PLAN_SHA256,
                        sha256=artifact.sha256,
                    ),
                    id="core-channel-plan-sha256",
                    markup=False,
                )
                yield Static(
                    self.copy.text(
                        UiText.CORE_UPDATE_PLAN_TRUST,
                        trust=self.copy.text(TRUST_COPY[artifact.trust_mode]),
                    ),
                    id="core-channel-plan-trust",
                    markup=False,
                )
                for index, warning in enumerate(self.plan.exact_update.warnings):
                    yield Static(
                        self.copy.text(WARNING_COPY[warning]),
                        id=f"core-channel-warning-{index}",
                        markup=False,
                    )
            if self.plan.target is not None:
                yield Static(
                    self.copy.text(
                        UiText.CORE_CHANNEL_PLAN_TARGET_SHA256,
                        sha256=self.plan.target.source_sha256,
                    ),
                    id="core-channel-plan-target-sha256",
                    markup=False,
                )
            if self.plan.expected_active is not None:
                yield Static(
                    self.copy.text(
                        UiText.CORE_CHANNEL_PLAN_ACTIVE_SHA256,
                        sha256=self.plan.expected_active.source_sha256,
                    ),
                    id="core-channel-plan-active-sha256",
                    markup=False,
                )
            if self.plan.exact_update is None and self.plan.prerelease:
                yield Static(
                    self.copy.text(UiText.CORE_UPDATE_PLAN_WARNING_PRERELEASE),
                    id="core-channel-plan-prerelease-warning",
                    markup=False,
                )
            yield Static(
                self.copy.text(
                    UiText.CORE_CHANNEL_PLAN_SAFETY_SWITCH
                    if self.is_switch
                    else UiText.CORE_CHANNEL_PLAN_SAFETY_ACQUIRE
                ),
                id="core-channel-plan-safety",
                markup=False,
            )
            yield Static("", id="core-channel-progress", markup=False)
            yield Button(
                self.copy.text(
                    UiText.CORE_CHANNEL_PLAN_CONFIRM_SWITCH
                    if self.is_switch
                    else UiText.CORE_CHANNEL_PLAN_CONFIRM_ACQUIRE
                ),
                id="confirm-core-channel",
                variant="error",
            )
        yield Footer()

    @on(Button.Pressed, "#confirm-core-channel")
    def confirm_channel_action(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-core-channel", Button).disabled = True
        self.query_one("#core-channel-progress", Static).update(
            self.copy.text(
                UiText.CORE_CHANNEL_PLAN_PROGRESS_SWITCH
                if self.is_switch
                else UiText.CORE_CHANNEL_PLAN_PROGRESS_ACQUIRE
            )
        )
        self.execute_channel_action()

    @work(thread=True, exclusive=True)
    def execute_channel_action(self) -> None:
        try:
            result = self.core_channels.execute(self.plan, confirmed=True)
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
        except (CoreActivationError, CoreSwitchError) as error:
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


class CoreChannelSelectionScreen(Screen[None]):
    """Select one semantic channel before read-only discovery begins."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        core_channels: CoreChannelManager,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.core_channels = core_channels
        self.copy = copy_catalog
        self._planning_generation = 0
        self._completed_planning_generation: int | None = None
        self._deferred_planning_outcome: tuple[int, _ChannelPlanningOutcome] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="core-channel-selection"):
            yield Static(
                self.copy.text(UiText.CORE_CHANNEL_TITLE),
                id="core-channel-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.CORE_CHANNEL_GUIDANCE),
                id="core-channel-guidance",
                markup=False,
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
                id="core-channel-architecture",
            )
            yield Button(
                self.copy.text(UiText.CORE_CHANNEL_STABLE),
                id="inspect-stable-channel",
                variant="primary",
            )
            yield Button(
                self.copy.text(UiText.CORE_CHANNEL_PREVIEW),
                id="inspect-preview-channel",
            )
            yield Static("", id="core-channel-progress", markup=False)
        yield Footer()

    @on(Button.Pressed, "#inspect-stable-channel")
    def inspect_stable(self, event: Button.Pressed) -> None:
        event.stop()
        self._start_plan(CoreReleaseChannel.STABLE)

    @on(Button.Pressed, "#inspect-preview-channel")
    def inspect_preview(self, event: Button.Pressed) -> None:
        event.stop()
        self._start_plan(CoreReleaseChannel.PREVIEW)

    def _start_plan(self, channel: CoreReleaseChannel) -> None:
        architecture = cast(
            Select[ArtifactArchitecture],
            self.query_one("#core-channel-architecture", Select),
        ).value
        if not isinstance(architecture, ArtifactArchitecture):
            self.query_one("#core-channel-progress", Static).update(
                self.copy.text(UiText.CORE_CHANNEL_ERROR_ARCHITECTURE)
            )
            return
        self.query_one("#inspect-stable-channel", Button).disabled = True
        self.query_one("#inspect-preview-channel", Button).disabled = True
        self._planning_generation += 1
        generation = self._planning_generation
        self._deferred_planning_outcome = None
        self.query_one("#core-channel-progress", Static).update(
            self.copy.text(UiText.CORE_CHANNEL_LOADING, channel=_channel_label(channel))
        )
        self.prepare_plan(channel, architecture, generation)

    @work(thread=True, exclusive=True)
    def prepare_plan(
        self,
        channel: CoreReleaseChannel,
        architecture: ArtifactArchitecture,
        generation: int,
    ) -> None:
        try:
            plan = self.core_channels.plan(
                PlanCoreChannelRequest(channel=channel, architecture=architecture)
            )
        except Exception:
            self.app.call_from_thread(
                self._show_planning_error,
                generation,
            )
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
        outcome: _ChannelPlanningOutcome,
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
        outcome: _ChannelPlanningOutcome,
    ) -> None:
        if not self._planning_is_relevant(generation) or self.app.screen is not self:
            return
        self._completed_planning_generation = generation
        self._deferred_planning_outcome = None
        self.query_one("#inspect-stable-channel", Button).disabled = False
        self.query_one("#inspect-preview-channel", Button).disabled = False
        self.query_one("#core-channel-progress", Static).update("")
        if outcome is None:
            self.app.push_screen(CoreChannelPlanningErrorScreen(self.copy))
            return
        if outcome.kind is CoreChannelPlanKind.ALREADY_CURRENT:
            self.app.push_screen(CoreChannelCurrentScreen(outcome, self.copy))
            return
        self.app.push_screen(CoreChannelPlanScreen(self.core_channels, outcome, self.copy))

    @on(events.ScreenResume)
    def resume_deferred_planning(self) -> None:
        deferred = self._deferred_planning_outcome
        if deferred is None:
            return
        self._deferred_planning_outcome = None
        self._deliver_or_defer_planning(*deferred)

    def _show_planning_error(self, generation: int) -> None:
        self._deliver_or_defer_planning(generation, None)

    def _show_plan(self, generation: int, plan: CoreChannelPlan) -> None:
        self._deliver_or_defer_planning(generation, plan)
