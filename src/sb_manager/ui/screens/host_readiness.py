"""First-run host readiness presentation behind one public screen interface."""

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.core_update import CoreUpdater
from sb_manager.application.host_readiness import (
    HostReadinessItemCode,
    HostReadinessReport,
    ReadinessState,
)
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.screens.core_update import CoreUpdateFormScreen

READINESS_STATE_TEXT = {
    ReadinessState.READY: UiText.HOST_READINESS_STATE_READY,
    ReadinessState.ATTENTION: UiText.HOST_READINESS_STATE_ATTENTION,
    ReadinessState.ACTION_REQUIRED: UiText.HOST_READINESS_STATE_ACTION_REQUIRED,
}


class HostReadinessScreen(Screen[None]):
    """Explain every prerequisite and route only currently valid setup actions."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        report: HostReadinessReport,
        *,
        core_updater: CoreUpdater | None,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.report = report
        self.core_updater = core_updater
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="host-readiness"):
            yield Static(
                self.copy.text(UiText.HOST_READINESS_TITLE),
                id="host-readiness-title",
                markup=False,
            )
            yield Static(self._summary(), id="host-readiness-summary", markup=False)
            for item in self.report.items:
                item_id = item.code.value
                yield Static(
                    self.copy.text(
                        UiText.HOST_READINESS_ITEM_TITLE,
                        state=self.copy.text(READINESS_STATE_TEXT[item.state]),
                        title=item.title,
                    ),
                    id=f"readiness-{item_id}-title",
                    markup=False,
                )
                yield Static(
                    item.summary,
                    id=f"readiness-{item_id}-summary",
                    markup=False,
                )
                yield Static(
                    item.diagnostics or self.copy.text(UiText.HOST_READINESS_DETAILS_UNAVAILABLE),
                    id=f"readiness-{item_id}-diagnostics",
                    markup=False,
                )
                if item.guidance:
                    yield Static(
                        self.copy.text(
                            UiText.HOST_READINESS_ITEM_GUIDANCE,
                            guidance=item.guidance,
                        ),
                        id=f"readiness-{item_id}-guidance",
                        markup=False,
                    )
            if self._can_install_core():
                yield Button(
                    self.copy.text(UiText.CORE_UPDATE_OPEN),
                    id="readiness-manage-core",
                    variant="primary",
                )
            yield Static(
                self.copy.text(UiText.HOST_READINESS_RECHECK),
                id="host-readiness-recheck",
                markup=False,
            )
        yield Footer()

    def _summary(self) -> str:
        count = self.report.action_required_count
        if count == 0:
            return self.copy.text(UiText.HOST_READINESS_SUMMARY_READY)
        return self.copy.text(UiText.HOST_READINESS_SUMMARY_ACTION_REQUIRED, count=count)

    def _can_install_core(self) -> bool:
        if self.core_updater is None:
            return False
        helper_ready = any(
            item.code is HostReadinessItemCode.PRIVILEGED_HELPER
            and item.state is ReadinessState.READY
            for item in self.report.items
        )
        core_missing = any(
            item.code is HostReadinessItemCode.CORE and item.state is ReadinessState.ACTION_REQUIRED
            for item in self.report.items
        )
        return helper_ready and core_missing

    @on(Button.Pressed, "#readiness-manage-core")
    def open_core_update(self) -> None:
        if self.core_updater is not None:
            self.app.push_screen(CoreUpdateFormScreen(self.core_updater, self.copy))
