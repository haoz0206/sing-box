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


class ServiceLogsScreen(Screen[None]):
    """Load safe recent runtime evidence away from the UI thread."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(
        self,
        service_log_reader: ServiceLogReader,
        *,
        limit: int = DEFAULT_LOG_LIMIT,
    ) -> None:
        super().__init__()
        self.service_log_reader = service_log_reader
        self.limit = limit

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="service-logs"):
            yield Static("近期服务日志", id="service-logs-title")
            yield Static(
                f"只读 · 最多 {self.limit} 行 · 自动清理控制字符并脱敏",
                id="service-logs-safety",
            )
            yield Static("正在读取近期服务日志…", id="service-logs-loading")
            yield Static("", id="service-logs-source", classes="hidden", markup=False)
            yield Static("", id="service-logs-content", classes="hidden", markup=False)
            yield Button("重新读取", id="refresh-service-logs", disabled=True)
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
        source_summary = f"来源：{report.source_label}"
        if report.redacted_occurrences:
            source_summary += f" · 已脱敏 {report.redacted_occurrences} 处"
        source.update(source_summary)
        source.remove_class("hidden")
        content = self.query_one("#service-logs-content", Static)
        if report.condition is ServiceLogCondition.AVAILABLE:
            content.update("\n".join(report.lines))
        elif report.condition is ServiceLogCondition.EMPTY:
            content.update("近期没有可显示的 sing-box 服务日志。")
        else:
            content.update(f"无法读取服务日志：{report.diagnostics or '未提供诊断细节'}")
        content.remove_class("hidden")
        self.query_one("#refresh-service-logs", Button).disabled = False

    def show_error(self) -> None:
        self.query_one("#service-logs-loading", Static).update(
            "无法完成日志检查。底层错误未显示，以避免泄露敏感信息。请重新读取。"
        )
        self.query_one("#refresh-service-logs", Button).disabled = False

    @on(Button.Pressed, "#refresh-service-logs")
    def refresh_logs(self) -> None:
        self.query_one("#service-logs-source", Static).add_class("hidden")
        self.query_one("#service-logs-content", Static).add_class("hidden")
        loading = self.query_one("#service-logs-loading", Static)
        loading.update("正在重新读取近期服务日志…")
        loading.remove_class("hidden")
        self.query_one("#refresh-service-logs", Button).disabled = True
        self.load_logs()
