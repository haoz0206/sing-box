"""Read-only drill-down for bounded configuration apply evidence."""

from datetime import timezone
from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.apply_history import (
    DEFAULT_APPLY_HISTORY_LIMIT,
    ApplyHistoryCondition,
    ApplyHistoryReader,
    ApplyHistoryReport,
)
from sb_manager.seams.apply_history import ApplyHistoryEntry, ApplyHistoryStatus
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText

STATUS_TEXT = {
    ApplyHistoryStatus.IN_PROGRESS: UiText.APPLY_HISTORY_STATUS_IN_PROGRESS,
    ApplyHistoryStatus.APPLIED: UiText.APPLY_HISTORY_STATUS_APPLIED,
    ApplyHistoryStatus.VALIDATION_FAILED: UiText.APPLY_HISTORY_STATUS_VALIDATION_FAILED,
    ApplyHistoryStatus.PRECONDITION_FAILED: UiText.APPLY_HISTORY_STATUS_PRECONDITION_FAILED,
    ApplyHistoryStatus.COMMIT_FAILED: UiText.APPLY_HISTORY_STATUS_COMMIT_FAILED,
    ApplyHistoryStatus.ROLLED_BACK: UiText.APPLY_HISTORY_STATUS_ROLLED_BACK,
    ApplyHistoryStatus.ROLLBACK_FAILED: UiText.APPLY_HISTORY_STATUS_ROLLBACK_FAILED,
    ApplyHistoryStatus.EXECUTION_ERROR: UiText.APPLY_HISTORY_STATUS_EXECUTION_ERROR,
}


class ApplyHistoryScreen(Screen[None]):
    """Load safe, durable apply evidence away from the UI thread."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        apply_history_reader: ApplyHistoryReader,
        *,
        limit: int = DEFAULT_APPLY_HISTORY_LIMIT,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.apply_history_reader = apply_history_reader
        self.limit = limit
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="apply-history"):
            yield Static(
                self.copy.text(UiText.APPLY_HISTORY_TITLE),
                id="apply-history-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.APPLY_HISTORY_SAFETY, limit=self.limit),
                id="apply-history-safety",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.APPLY_HISTORY_LOADING),
                id="apply-history-loading",
                markup=False,
            )
            yield Static("", id="apply-history-summary", classes="hidden", markup=False)
            yield Static("", id="apply-history-content", classes="hidden", markup=False)
            yield Button(
                self.copy.text(UiText.APPLY_HISTORY_REFRESH),
                id="refresh-apply-history",
                disabled=True,
            )
        yield Footer()

    def on_mount(self) -> None:
        self.load_history()

    @work(thread=True, exclusive=True)
    def load_history(self) -> None:
        try:
            report = self.apply_history_reader.read_recent(limit=self.limit)
        except Exception:
            self.app.call_from_thread(self.show_error)
            return
        self.app.call_from_thread(self.show_report, report)

    def show_report(self, report: ApplyHistoryReport) -> None:
        self.query_one("#apply-history-loading", Static).add_class("hidden")
        summary = self.query_one("#apply-history-summary", Static)
        summary.update(report.summary)
        summary.remove_class("hidden")
        content = self.query_one("#apply-history-content", Static)
        if report.condition is ApplyHistoryCondition.UNAVAILABLE:
            content.update(
                self.copy.text(
                    UiText.APPLY_HISTORY_UNAVAILABLE,
                    diagnostics=report.diagnostics
                    or self.copy.text(UiText.APPLY_HISTORY_DETAILS_UNAVAILABLE),
                )
            )
        elif not report.entries:
            content.update(self.copy.text(UiText.APPLY_HISTORY_EMPTY))
        else:
            content.update("\n\n".join(_render_entry(entry, self.copy) for entry in report.entries))
        content.remove_class("hidden")
        self.query_one("#refresh-apply-history", Button).disabled = False

    def show_error(self) -> None:
        loading = self.query_one("#apply-history-loading", Static)
        loading.update(self.copy.text(UiText.APPLY_HISTORY_ERROR))
        loading.remove_class("hidden")
        self.query_one("#refresh-apply-history", Button).disabled = False

    @on(Button.Pressed, "#refresh-apply-history")
    def refresh_history(self) -> None:
        self.query_one("#apply-history-summary", Static).add_class("hidden")
        self.query_one("#apply-history-content", Static).add_class("hidden")
        loading = self.query_one("#apply-history-loading", Static)
        loading.update(self.copy.text(UiText.APPLY_HISTORY_RELOADING))
        loading.remove_class("hidden")
        self.query_one("#refresh-apply-history", Button).disabled = True
        self.load_history()


def _render_entry(entry: ApplyHistoryEntry, copy: CopyCatalog) -> str:
    started_at = entry.started_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    status = copy.text(STATUS_TEXT[entry.status])
    lines = [
        copy.text(UiText.APPLY_HISTORY_ENTRY_HEADER, started_at=started_at, status=status),
        copy.text(
            UiText.APPLY_HISTORY_ENTRY_ACTIVE_PROFILES,
            count=entry.active_profile_count,
        ),
        copy.text(
            UiText.APPLY_HISTORY_ENTRY_CANDIDATE,
            sha256=entry.candidate_sha256,
        ),
    ]
    if entry.status is ApplyHistoryStatus.IN_PROGRESS:
        lines.append(copy.text(UiText.APPLY_HISTORY_ENTRY_IN_PROGRESS))
    if entry.diagnostics:
        lines.append(
            copy.text(
                UiText.APPLY_HISTORY_ENTRY_DIAGNOSTICS,
                diagnostics=entry.diagnostics,
            )
        )
    if entry.redacted_occurrences:
        lines.append(
            copy.text(
                UiText.APPLY_HISTORY_ENTRY_REDACTED,
                count=entry.redacted_occurrences,
            )
        )
    return "\n".join(lines)
