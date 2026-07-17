"""Capability-aware navigation for routine host operations."""

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.apply_history import ApplyHistoryReader
from sb_manager.application.core_update import CoreUpdater
from sb_manager.application.service_logs import ServiceLogReader
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.screens.apply_history import ApplyHistoryScreen
from sb_manager.ui.screens.core_update import CoreUpdateFormScreen
from sb_manager.ui.screens.service_logs import ServiceLogsScreen


class OperationsScreen(Screen[None]):
    """Present available operational workflows without executing them eagerly."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        *,
        core_updater: CoreUpdater | None,
        service_log_reader: ServiceLogReader | None,
        apply_history_reader: ApplyHistoryReader | None,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.core_updater = core_updater
        self.service_log_reader = service_log_reader
        self.apply_history_reader = apply_history_reader
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="operations"):
            yield Static(
                self.copy.text(UiText.OPERATIONS_TITLE),
                id="operations-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.OPERATIONS_SUMMARY),
                id="operations-summary",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.OPERATIONS_SAFETY),
                id="operations-safety",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.OPERATIONS_CORE_TITLE),
                id="operations-core-title",
                classes="section-title",
            )
            if self.core_updater is not None:
                yield Button(self.copy.text(UiText.CORE_UPDATE_OPEN), id="manage-core")
            else:
                yield Static(
                    self.copy.text(UiText.OPERATIONS_CORE_UNAVAILABLE),
                    id="operations-core-unavailable",
                    markup=False,
                )
            yield Static(
                self.copy.text(UiText.OPERATIONS_EVIDENCE_TITLE),
                id="operations-evidence-title",
                classes="section-title",
            )
            if self.service_log_reader is not None:
                yield Button(
                    self.copy.text(UiText.OPERATIONS_OPEN_SERVICE_LOGS),
                    id="open-service-logs",
                )
            else:
                yield Static(
                    self.copy.text(UiText.OPERATIONS_SERVICE_LOGS_UNAVAILABLE),
                    id="operations-service-logs-unavailable",
                    markup=False,
                )
            if self.apply_history_reader is not None:
                yield Button(
                    self.copy.text(UiText.OPERATIONS_OPEN_APPLY_HISTORY),
                    id="open-apply-history",
                )
            else:
                yield Static(
                    self.copy.text(UiText.OPERATIONS_APPLY_HISTORY_UNAVAILABLE),
                    id="operations-apply-history-unavailable",
                    markup=False,
                )
        yield Footer()

    @on(Button.Pressed, "#manage-core")
    def open_core_update(self) -> None:
        if self.core_updater is not None:
            self.app.push_screen(CoreUpdateFormScreen(self.core_updater, self.copy))

    @on(Button.Pressed, "#open-service-logs")
    def open_service_logs(self) -> None:
        if self.service_log_reader is not None:
            self.app.push_screen(ServiceLogsScreen(self.service_log_reader, copy_catalog=self.copy))

    @on(Button.Pressed, "#open-apply-history")
    def open_apply_history(self) -> None:
        if self.apply_history_reader is not None:
            self.app.push_screen(
                ApplyHistoryScreen(self.apply_history_reader, copy_catalog=self.copy)
            )
