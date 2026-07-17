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

STATUS_LABELS = {
    ApplyHistoryStatus.IN_PROGRESS: "结果待确认",
    ApplyHistoryStatus.APPLIED: "应用成功",
    ApplyHistoryStatus.VALIDATION_FAILED: "校验失败",
    ApplyHistoryStatus.PRECONDITION_FAILED: "前置条件失败",
    ApplyHistoryStatus.COMMIT_FAILED: "提交失败",
    ApplyHistoryStatus.ROLLED_BACK: "已回滚",
    ApplyHistoryStatus.ROLLBACK_FAILED: "回滚失败",
    ApplyHistoryStatus.EXECUTION_ERROR: "执行异常",
}


class ApplyHistoryScreen(Screen[None]):
    """Load safe, durable apply evidence away from the UI thread."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(
        self,
        apply_history_reader: ApplyHistoryReader,
        *,
        limit: int = DEFAULT_APPLY_HISTORY_LIMIT,
    ) -> None:
        super().__init__()
        self.apply_history_reader = apply_history_reader
        self.limit = limit

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="apply-history"):
            yield Static("配置应用历史", id="apply-history-title", markup=False)
            yield Static(
                f"只读 · 最近 {self.limit} 次 · 不保存配置正文或私钥",
                id="apply-history-safety",
                markup=False,
            )
            yield Static("正在读取配置应用历史…", id="apply-history-loading", markup=False)
            yield Static("", id="apply-history-summary", classes="hidden", markup=False)
            yield Static("", id="apply-history-content", classes="hidden", markup=False)
            yield Button("重新读取", id="refresh-apply-history", disabled=True)
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
            content.update(f"无法读取配置应用历史：{report.diagnostics or '未提供诊断细节'}")
        elif not report.entries:
            content.update("尚无配置应用记录。")
        else:
            content.update("\n\n".join(_render_entry(entry) for entry in report.entries))
        content.remove_class("hidden")
        self.query_one("#refresh-apply-history", Button).disabled = False

    def show_error(self) -> None:
        loading = self.query_one("#apply-history-loading", Static)
        loading.update("无法完成应用历史检查。底层错误未显示，以避免泄露敏感信息。请重新读取。")
        loading.remove_class("hidden")
        self.query_one("#refresh-apply-history", Button).disabled = False

    @on(Button.Pressed, "#refresh-apply-history")
    def refresh_history(self) -> None:
        self.query_one("#apply-history-summary", Static).add_class("hidden")
        self.query_one("#apply-history-content", Static).add_class("hidden")
        loading = self.query_one("#apply-history-loading", Static)
        loading.update("正在重新读取配置应用历史…")
        loading.remove_class("hidden")
        self.query_one("#refresh-apply-history", Button).disabled = True
        self.load_history()


def _render_entry(entry: ApplyHistoryEntry) -> str:
    started_at = entry.started_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    lines = [
        f"{started_at} · {STATUS_LABELS[entry.status]}",
        f"生效配置数：{entry.active_profile_count}",
        f"候选配置 SHA-256：{entry.candidate_sha256}",
    ]
    if entry.status is ApplyHistoryStatus.IN_PROGRESS:
        lines.append("结果尚未写入，需要核对主机状态")
    if entry.diagnostics:
        lines.append(f"诊断：{entry.diagnostics}")
    if entry.redacted_occurrences:
        lines.append(f"已脱敏：{entry.redacted_occurrences} 处")
    return "\n".join(lines)
