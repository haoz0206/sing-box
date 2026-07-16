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
from sb_manager.ui.screens.core_update import CoreUpdateFormScreen


class HostReadinessScreen(Screen[None]):
    """Explain every prerequisite and route only currently valid setup actions."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(
        self,
        report: HostReadinessReport,
        *,
        core_updater: CoreUpdater | None,
    ) -> None:
        super().__init__()
        self.report = report
        self.core_updater = core_updater

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="host-readiness"):
            yield Static("主机准备度", id="host-readiness-title")
            yield Static(self._summary(), id="host-readiness-summary")
            for item in self.report.items:
                item_id = item.code.value
                yield Static(
                    f"{self._state_marker(item.state)} {item.title}",
                    id=f"readiness-{item_id}-title",
                )
                yield Static(item.summary, id=f"readiness-{item_id}-summary")
                yield Static(
                    item.diagnostics or "未提供诊断信息",
                    id=f"readiness-{item_id}-diagnostics",
                )
                if item.guidance:
                    yield Static(item.guidance, id=f"readiness-{item_id}-guidance")
            if self._can_install_core():
                yield Button(
                    "安装或升级 sing-box 核心",
                    id="readiness-manage-core",
                    variant="primary",
                )
            yield Static("完成主机调整后，返回 dashboard 选择“重新检查”。")
        yield Footer()

    def _summary(self) -> str:
        count = self.report.action_required_count
        return "应用前置条件已满足" if count == 0 else f"应用前需要完成 {count} 项准备"

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

    @staticmethod
    def _state_marker(state: ReadinessState) -> str:
        if state is ReadinessState.READY:
            return "[就绪]"
        if state is ReadinessState.ATTENTION:
            return "[注意]"
        return "[需处理]"

    @on(Button.Pressed, "#readiness-manage-core")
    def open_core_update(self) -> None:
        if self.core_updater is not None:
            self.app.push_screen(CoreUpdateFormScreen(self.core_updater))
