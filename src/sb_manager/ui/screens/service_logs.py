"""Read-only drill-down for bounded, redacted service logs."""

from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.service_logs import (
    DEFAULT_LOG_LIMIT,
    ServiceLogCondition,
    ServiceLogReader,
    ServiceLogReport,
)
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class ServiceLogsScreen(Screen[None]):
    """Load safe recent runtime evidence away from the UI thread."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        service_log_reader: ServiceLogReader,
        *,
        limit: int = DEFAULT_LOG_LIMIT,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.service_log_reader = service_log_reader
        self.limit = limit
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="service-logs"):
            yield Static(
                self.copy.text(UiText.SERVICE_LOGS_TITLE),
                id="service-logs-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.SERVICE_LOGS_SAFETY, limit=self.limit),
                id="service-logs-safety",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.SERVICE_LOGS_LOADING),
                id="service-logs-loading",
                markup=False,
            )
            yield Static("", id="service-logs-source", classes="hidden", markup=False)
            yield Static("", id="service-logs-content", classes="hidden", markup=False)
            yield Button(
                self.copy.text(UiText.SERVICE_LOGS_REFRESH),
                id="refresh-service-logs",
                disabled=True,
            )
        yield Footer()

    def on_mount(self) -> None:
        self.load_logs()

    @work(thread=True, exclusive=True)
    def load_logs(self) -> None:
        try:
            report = self.service_log_reader.read_recent(limit=self.limit)
        except Exception:
            self.app.call_from_thread(self.show_error)
            return
        self.app.call_from_thread(self.show_report, report)

    def show_report(self, report: ServiceLogReport) -> None:
        self.query_one("#service-logs-loading", Static).add_class("hidden")
        source = self.query_one("#service-logs-source", Static)
        source_summary = self.copy.text(
            UiText.SERVICE_LOGS_SOURCE,
            source=report.source_label,
        )
        if report.redacted_occurrences:
            source_summary = self.copy.text(
                UiText.SERVICE_LOGS_SOURCE_REDACTED,
                source=report.source_label,
                count=report.redacted_occurrences,
            )
        source.update(source_summary)
        source.remove_class("hidden")
        content = self.query_one("#service-logs-content", Static)
        if report.condition is ServiceLogCondition.AVAILABLE:
            content.update("\n".join(report.lines))
        elif report.condition is ServiceLogCondition.EMPTY:
            content.update(self.copy.text(UiText.SERVICE_LOGS_EMPTY))
        else:
            content.update(
                self.copy.text(
                    UiText.SERVICE_LOGS_UNAVAILABLE,
                    diagnostics=report.diagnostics
                    or self.copy.text(UiText.SERVICE_LOGS_DETAILS_UNAVAILABLE),
                )
            )
        content.remove_class("hidden")
        self.query_one("#refresh-service-logs", Button).disabled = False

    def show_error(self) -> None:
        self.query_one("#service-logs-loading", Static).update(
            self.copy.text(UiText.SERVICE_LOGS_ERROR)
        )
        self.query_one("#refresh-service-logs", Button).disabled = False

    @on(Button.Pressed, "#refresh-service-logs")
    def refresh_logs(self) -> None:
        self.query_one("#service-logs-source", Static).add_class("hidden")
        self.query_one("#service-logs-content", Static).add_class("hidden")
        loading = self.query_one("#service-logs-loading", Static)
        loading.update(self.copy.text(UiText.SERVICE_LOGS_RELOADING))
        loading.remove_class("hidden")
        self.query_one("#refresh-service-logs", Button).disabled = True
        self.load_logs()
