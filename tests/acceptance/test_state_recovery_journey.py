from pathlib import Path

from textual.widgets import Button, Static

from sb_manager.application.state_recovery import (
    RecoveryAvailability,
    StateRecoveryPlan,
    StateRecoveryReport,
)
from sb_manager.domain.installation import ManagedInstallation
from sb_manager.seams.state_recovery import StateRecoveryCommit
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools


class RecordingStateRecoveryManager:
    def __init__(self, report: StateRecoveryReport) -> None:
        self.report = report
        self.confirmations: list[tuple[StateRecoveryPlan, bool]] = []

    def inspect(self) -> StateRecoveryReport:
        return self.report

    def recover(
        self,
        plan: StateRecoveryPlan,
        *,
        confirmed: bool,
    ) -> StateRecoveryCommit:
        self.confirmations.append((plan, confirmed))
        installation = ManagedInstallation(
            schema_version=1,
            revision=plan.backup_revision,
            profiles=(),
        )
        self.report = StateRecoveryReport(
            availability=RecoveryAvailability.HEALTHY,
            installation=installation,
        )
        return StateRecoveryCommit(
            installation=installation,
            corrupt_archive_path=Path("/state/state.json.corrupt-reviewed"),
        )


async def test_operator_can_review_and_confirm_desired_state_recovery() -> None:
    plan = StateRecoveryPlan(
        primary_sha256="a" * 64,
        backup_sha256="b" * 64,
        backup_revision=6,
        backup_profile_count=0,
    )
    recovery = RecordingStateRecoveryManager(
        StateRecoveryReport(
            availability=RecoveryAvailability.RECOVERY_AVAILABLE,
            plan=plan,
        )
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(state_recovery_manager=recovery),
    )

    async with app.run_test() as pilot:
        assert app.screen.query_one("#state-recovery-title", Static).content == (
            "desired state 无法读取"
        )
        assert app.screen.query_one("#state-recovery-backup", Static).content == (
            "可恢复备份：revision 6 · 0 个配置"
        )
        assert str(app.screen.query_one("#review-state-recovery", Button).label) == ("审阅恢复计划")

        await pilot.click("#review-state-recovery")

        assert app.screen.query_one("#state-recovery-confirm-title", Static).content == (
            "确认恢复 desired state"
        )
        assert app.screen.query_one("#state-recovery-confirm-safety", Static).content == (
            "将用已审阅备份替换损坏主文件，损坏原文件会被完整归档。"
        )

        await pilot.click("#confirm-state-recovery")
        await pilot.pause()

        assert recovery.confirmations == [(plan, True)]
        assert app.screen.query_one("#empty-state-title", Static).content == "尚未创建代理配置"


async def test_newer_state_schema_is_never_offered_as_corruption_recovery() -> None:
    recovery = RecordingStateRecoveryManager(
        StateRecoveryReport(
            availability=RecoveryAvailability.UNSUPPORTED_SCHEMA,
            found_schema_version=2,
        )
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(state_recovery_manager=recovery),
    )

    async with app.run_test():
        assert app.screen.query_one("#state-recovery-title", Static).content == (
            "desired state 版本高于当前管理器"
        )
        assert app.screen.query_one("#state-recovery-guidance", Static).content == (
            "检测到 schema 2。请使用兼容版本的管理器打开，当前版本不会覆盖该文件。"
        )
        assert not app.screen.query("#review-state-recovery")
