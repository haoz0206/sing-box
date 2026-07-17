"""Action-oriented diagnostics center behind one Textual screen interface."""

from dataclasses import dataclass
from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.apply_history import ApplyHistoryReader
from sb_manager.application.config_adoption import ConfigAdopter
from sb_manager.application.core_update import CoreUpdater
from sb_manager.application.diagnostics_center import (
    DiagnosticAction,
    DiagnosticCode,
    DiagnosticCondition,
    DiagnosticItem,
    DiagnosticsCenter,
    DiagnosticsCenterReport,
)
from sb_manager.application.service_logs import ServiceLogReader
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.screens.apply_history import ApplyHistoryScreen
from sb_manager.ui.screens.config_adoption import ConfigAdoptionScreen
from sb_manager.ui.screens.core_update import CoreUpdateFormScreen
from sb_manager.ui.screens.service_logs import ServiceLogsScreen


@dataclass(frozen=True, slots=True)
class DiagnosticsCenterTools:
    """Optional navigation capabilities exposed by the diagnostics center."""

    config_adopter: ConfigAdopter | None = None
    core_updater: CoreUpdater | None = None
    service_log_reader: ServiceLogReader | None = None
    apply_history_reader: ApplyHistoryReader | None = None


class DiagnosticsCenterScreen(Screen[None]):
    """Load and present one prioritized diagnostics report on demand."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        diagnostics_center: DiagnosticsCenter,
        *,
        tools: DiagnosticsCenterTools,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.diagnostics_center = diagnostics_center
        self.config_adopter = tools.config_adopter
        self.core_updater = tools.core_updater
        self.service_log_reader = tools.service_log_reader
        self.apply_history_reader = tools.apply_history_reader
        self.copy = copy_catalog
        self.report: DiagnosticsCenterReport | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="diagnostics-center"):
            yield Static(
                self.copy.text(UiText.DIAGNOSTICS_CENTER_TITLE),
                id="diagnostics-center-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.DIAGNOSTICS_CENTER_LOADING),
                id="diagnostics-center-loading",
                markup=False,
            )
            yield Static("", id="diagnostics-center-summary", classes="hidden", markup=False)
            yield Static(
                "",
                id="diagnostics-center-recommended-action",
                classes="hidden",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.DIAGNOSTICS_CENTER_ACTION_REVIEW_CONFIG_ADOPTION),
                id="diagnostics-center-action",
                classes="hidden",
                variant="primary",
            )
            for code in DiagnosticCode:
                item_id = code.value
                yield Static(
                    "",
                    id=f"diagnostic-{item_id}-title",
                    classes="hidden",
                    markup=False,
                )
                yield Static(
                    "",
                    id=f"diagnostic-{item_id}-summary",
                    classes="hidden",
                    markup=False,
                )
                yield Static(
                    "",
                    id=f"diagnostic-{item_id}-details",
                    classes="hidden",
                    markup=False,
                )
                yield Static(
                    "",
                    id=f"diagnostic-{item_id}-guidance",
                    classes="hidden",
                    markup=False,
                )
            yield Button(
                self.copy.text(UiText.DIAGNOSTICS_CENTER_REFRESH),
                id="refresh-diagnostics-center",
                disabled=True,
            )
            if self.service_log_reader is not None:
                yield Button(
                    self.copy.text(UiText.DIAGNOSTICS_CENTER_OPEN_SERVICE_LOGS),
                    id="open-service-logs",
                )
            if self.apply_history_reader is not None:
                yield Button(
                    self.copy.text(UiText.DIAGNOSTICS_CENTER_OPEN_APPLY_HISTORY),
                    id="open-apply-history",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.load_report()

    @work(thread=True, exclusive=True)
    def load_report(self) -> None:
        try:
            report = self.diagnostics_center.inspect()
        except Exception:
            self.app.call_from_thread(self.show_error)
            return
        self.app.call_from_thread(self.show_report, report)

    def show_report(self, report: DiagnosticsCenterReport) -> None:
        self.report = report
        self.query_one("#diagnostics-center-loading", Static).add_class("hidden")
        summary = self.query_one("#diagnostics-center-summary", Static)
        summary.update(self._summary(report))
        summary.remove_class("hidden")
        recommended = self.query_one("#diagnostics-center-recommended-action", Static)
        recommended_summary = (
            self.copy.text(UiText.DIAGNOSTICS_CENTER_RECOMMENDATION_NONE)
            if report.condition is DiagnosticCondition.HEALTHY
            else report.recommended_action
            or self.copy.text(UiText.DIAGNOSTICS_CENTER_RECOMMENDATION_NONE)
        )
        recommended.update(
            self.copy.text(
                UiText.DIAGNOSTICS_CENTER_RECOMMENDATION,
                summary=recommended_summary,
            )
        )
        recommended.remove_class("hidden")
        action = self.query_one("#diagnostics-center-action", Button)
        if (
            report.recommended_action_kind is DiagnosticAction.REVIEW_CONFIG_ADOPTION
            and self.config_adopter is not None
        ):
            action.label = self.copy.text(UiText.DIAGNOSTICS_CENTER_ACTION_REVIEW_CONFIG_ADOPTION)
            action.remove_class("hidden")
        elif (
            report.recommended_action_kind is DiagnosticAction.MANAGE_CORE
            and self.core_updater is not None
        ):
            action.label = self.copy.text(UiText.CORE_UPDATE_OPEN)
            action.remove_class("hidden")
        else:
            action.add_class("hidden")
        self._hide_items()
        for item in report.items:
            self._show_item(item)
        self.query_one("#refresh-diagnostics-center", Button).disabled = False

    def show_error(self) -> None:
        self.report = None
        loading = self.query_one("#diagnostics-center-loading", Static)
        loading.update(self.copy.text(UiText.DIAGNOSTICS_CENTER_ERROR))
        loading.remove_class("hidden")
        self.query_one("#diagnostics-center-action", Button).add_class("hidden")
        self.query_one("#refresh-diagnostics-center", Button).disabled = False

    @on(Button.Pressed, "#refresh-diagnostics-center")
    def refresh_report(self) -> None:
        self.report = None
        self.query_one("#diagnostics-center-summary", Static).add_class("hidden")
        self.query_one("#diagnostics-center-recommended-action", Static).add_class("hidden")
        self.query_one("#diagnostics-center-action", Button).add_class("hidden")
        self._hide_items()
        loading = self.query_one("#diagnostics-center-loading", Static)
        loading.update(self.copy.text(UiText.DIAGNOSTICS_CENTER_RECHECKING))
        loading.remove_class("hidden")
        self.query_one("#refresh-diagnostics-center", Button).disabled = True
        self.load_report()

    @on(Button.Pressed, "#diagnostics-center-action")
    def open_recommended_action(self) -> None:
        if (
            self.report is not None
            and self.report.recommended_action_kind is DiagnosticAction.REVIEW_CONFIG_ADOPTION
            and self.config_adopter is not None
        ):
            self.app.push_screen(ConfigAdoptionScreen(self.config_adopter, self.copy))
        elif (
            self.report is not None
            and self.report.recommended_action_kind is DiagnosticAction.MANAGE_CORE
            and self.core_updater is not None
        ):
            self.app.push_screen(CoreUpdateFormScreen(self.core_updater, self.copy))

    @on(Button.Pressed, "#open-service-logs")
    def open_service_logs(self) -> None:
        if self.service_log_reader is not None:
            self.app.push_screen(ServiceLogsScreen(self.service_log_reader, copy_catalog=self.copy))

    @on(Button.Pressed, "#open-apply-history")
    def open_apply_history(self) -> None:
        if self.apply_history_reader is not None:
            self.app.push_screen(ApplyHistoryScreen(self.apply_history_reader))

    def _summary(self, report: DiagnosticsCenterReport) -> str:
        if report.condition is DiagnosticCondition.HEALTHY:
            return self.copy.text(UiText.DIAGNOSTICS_CENTER_SUMMARY_HEALTHY)
        return self.copy.text(
            UiText.DIAGNOSTICS_CENTER_SUMMARY_ACTIONABLE,
            action_required=report.action_required_count,
            attention=report.attention_count,
        )

    def _hide_items(self) -> None:
        for code in DiagnosticCode:
            for suffix in ("title", "summary", "details", "guidance"):
                self.query_one(f"#diagnostic-{code.value}-{suffix}", Static).add_class("hidden")

    def _show_item(self, item: DiagnosticItem) -> None:
        item_id = item.code.value
        title = self.query_one(f"#diagnostic-{item_id}-title", Static)
        title.update(
            self.copy.text(
                UiText.DIAGNOSTICS_CENTER_ITEM_TITLE,
                condition=self._condition_marker(item.condition),
                title=item.title,
            )
        )
        title.remove_class("hidden")
        summary = self.query_one(f"#diagnostic-{item_id}-summary", Static)
        summary.update(item.summary)
        summary.remove_class("hidden")
        details = self.query_one(f"#diagnostic-{item_id}-details", Static)
        details.update(
            item.diagnostics or self.copy.text(UiText.DIAGNOSTICS_CENTER_DETAILS_UNAVAILABLE)
        )
        details.remove_class("hidden")
        if item.guidance:
            guidance = self.query_one(f"#diagnostic-{item_id}-guidance", Static)
            guidance.update(
                self.copy.text(
                    UiText.DIAGNOSTICS_CENTER_ITEM_GUIDANCE,
                    guidance=item.guidance,
                )
            )
            guidance.remove_class("hidden")

    def _condition_marker(self, condition: DiagnosticCondition) -> str:
        if condition is DiagnosticCondition.HEALTHY:
            return self.copy.text(UiText.DIAGNOSTICS_CENTER_CONDITION_HEALTHY)
        if condition is DiagnosticCondition.ATTENTION:
            return self.copy.text(UiText.DIAGNOSTICS_CENTER_CONDITION_ATTENTION)
        return self.copy.text(UiText.DIAGNOSTICS_CENTER_CONDITION_ACTION_REQUIRED)
