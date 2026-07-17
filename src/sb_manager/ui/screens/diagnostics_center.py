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

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

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
            yield Static("诊断中心", id="diagnostics-center-title", markup=False)
            yield Static(
                "正在读取 desired state、主机准备度与运行状态…",
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
                "审查并接管现有配置",
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
                "重新检查",
                id="refresh-diagnostics-center",
                disabled=True,
            )
            if self.service_log_reader is not None:
                yield Button("查看近期服务日志", id="open-service-logs")
            if self.apply_history_reader is not None:
                yield Button("查看配置应用历史", id="open-apply-history")
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
        recommended.update(f"建议：{report.recommended_action}")
        recommended.remove_class("hidden")
        action = self.query_one("#diagnostics-center-action", Button)
        if (
            report.recommended_action_kind is DiagnosticAction.REVIEW_CONFIG_ADOPTION
            and self.config_adopter is not None
        ):
            action.label = "审查并接管现有配置"
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
        loading.update("无法完成诊断检查。底层错误未显示，以避免泄露敏感信息。请重新检查。")
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
        loading.update("正在重新检查 desired state、主机准备度与运行状态…")
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
            self.app.push_screen(ServiceLogsScreen(self.service_log_reader))

    @on(Button.Pressed, "#open-apply-history")
    def open_apply_history(self) -> None:
        if self.apply_history_reader is not None:
            self.app.push_screen(ApplyHistoryScreen(self.apply_history_reader))

    @staticmethod
    def _summary(report: DiagnosticsCenterReport) -> str:
        if report.condition is DiagnosticCondition.HEALTHY:
            return "整体状态：所有检查均正常"
        return (
            f"整体状态：需要处理 {report.action_required_count} 项，"
            f"注意 {report.attention_count} 项"
        )

    def _hide_items(self) -> None:
        for code in DiagnosticCode:
            for suffix in ("title", "summary", "details", "guidance"):
                self.query_one(f"#diagnostic-{code.value}-{suffix}", Static).add_class("hidden")

    def _show_item(self, item: DiagnosticItem) -> None:
        item_id = item.code.value
        title = self.query_one(f"#diagnostic-{item_id}-title", Static)
        title.update(f"{self._condition_marker(item.condition)} {item.title}")
        title.remove_class("hidden")
        summary = self.query_one(f"#diagnostic-{item_id}-summary", Static)
        summary.update(item.summary)
        summary.remove_class("hidden")
        details = self.query_one(f"#diagnostic-{item_id}-details", Static)
        details.update(item.diagnostics or "未提供诊断细节")
        details.remove_class("hidden")
        if item.guidance:
            guidance = self.query_one(f"#diagnostic-{item_id}-guidance", Static)
            guidance.update(f"下一步：{item.guidance}")
            guidance.remove_class("hidden")

    @staticmethod
    def _condition_marker(condition: DiagnosticCondition) -> str:
        if condition is DiagnosticCondition.HEALTHY:
            return "[正常]"
        if condition is DiagnosticCondition.ATTENTION:
            return "[注意]"
        return "[需处理]"
