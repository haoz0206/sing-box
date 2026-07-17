from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from sb_manager.application.host_diagnostics import HostCondition, HostDiagnosticsReport
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class HostDiagnosticsScreen(Screen[None]):
    """Present one typed host observation with operator recovery guidance."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        report: HostDiagnosticsReport,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.report = report
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="host-diagnostics"):
            yield Static(
                self.copy.text(UiText.HOST_DIAGNOSTICS_TITLE),
                id="diagnostics-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.HOST_DIAGNOSTICS_SUMMARY_HEALTHY
                    if self.report.condition is HostCondition.HEALTHY
                    else UiText.HOST_DIAGNOSTICS_SUMMARY_UNHEALTHY
                ),
                id="diagnostics-summary",
                markup=False,
            )
            yield Static(
                self.report.diagnostics
                or self.copy.text(UiText.HOST_DIAGNOSTICS_DETAILS_UNAVAILABLE),
                id="diagnostics-details",
                markup=False,
            )
            if self.report.recovery_instructions:
                yield Static(
                    self.copy.text(UiText.HOST_DIAGNOSTICS_RECOVERY_TITLE),
                    id="diagnostics-recovery-title",
                    markup=False,
                )
                for index, instruction in enumerate(self.report.recovery_instructions):
                    yield Static(
                        self.copy.text(
                            UiText.HOST_DIAGNOSTICS_RECOVERY_STEP,
                            number=index + 1,
                            instruction=instruction,
                        ),
                        id=f"diagnostics-recovery-{index}",
                        markup=False,
                    )
            else:
                yield Static(
                    self.copy.text(UiText.HOST_DIAGNOSTICS_RECOVERY_EMPTY),
                    id="diagnostics-recovery-empty",
                    markup=False,
                )
        yield Footer()
