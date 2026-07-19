import asyncio
from pathlib import Path
from threading import Event
from typing import cast

from textual.widgets import Button, Static

from sb_manager.application.state_recovery import (
    RecoveryAvailability,
    StateRecoveryPlan,
    StateRecoveryReport,
)
from sb_manager.domain.installation import ManagedInstallation
from sb_manager.seams.state_recovery import (
    StateRecoveryCommit,
    StateRecoveryPreconditionError,
    StateRecoverySourceError,
)
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools, ManagerAppInterfaceTools
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class StateRecoveryMarkerCatalog:
    """Render markers across the complete desired-state recovery journey."""

    def text(self, key: UiText, /, **values: object) -> str:
        markers = {
            "state_recovery.available.title": "目录恢复可用",
            "state_recovery.available.guidance": "目录恢复说明",
            "state_recovery.available.review": "目录审阅恢复",
            "state_recovery.confirm.title": "目录确认恢复",
            "state_recovery.confirm.safety": "目录确认安全说明",
            "state_recovery.confirm.action": "目录确认并恢复",
            "state_recovery.confirm.progress": "目录正在恢复",
            "state_recovery.result.title": "目录恢复成功",
            "state_recovery.result.safety": "目录恢复结果安全说明",
            "state_recovery.result.return_dashboard": "目录返回仪表盘",
            "state_recovery.rejection.title": "目录恢复拒绝",
            "state_recovery.rejection.safety": "目录拒绝安全说明",
            "state_recovery.unknown.title": "目录恢复结果未知",
            "state_recovery.unknown.details": "目录恢复未知详情",
            "state_recovery.unknown.safety": "目录恢复未知安全说明",
            "state_recovery.inspection_error.title": "目录恢复检查失败",
            "state_recovery.inspection_error.details": "目录恢复检查失败详情",
            "state_recovery.inspection_error.safety": "目录恢复检查安全说明",
            "state_recovery.unsupported.title": "目录未来版本",
            "state_recovery.unavailable.title": "目录恢复不可用",
            "state_recovery.unavailable.guidance": "目录恢复不可用说明",
            "state_recovery.planning_error.title": "目录恢复计划失败",
            "state_recovery.planning_error.details": "目录恢复计划失败详情",
            "state_recovery.planning_error.safety": "目录恢复计划安全说明",
        }
        if marker := markers.get(key.value):
            return marker
        templates = {
            "state_recovery.available.backup": ("目录可用 revision {revision} profiles {profiles}"),
            "state_recovery.confirm.backup": ("目录确认 revision {revision} profiles {profiles}"),
            "state_recovery.confirm.primary_fingerprint": "目录主文件指纹 {sha256}",
            "state_recovery.confirm.backup_fingerprint": "目录备份指纹 {sha256}",
            "state_recovery.result.revision": "目录结果 revision {revision}",
            "state_recovery.result.profiles": "目录结果 profiles {profiles}",
            "state_recovery.result.archive": "目录归档 {path}",
            "state_recovery.unsupported.guidance": "目录未来 schema {schema}",
        }
        if template := templates.get(key.value):
            return template.format_map(values)
        return SIMPLIFIED_CHINESE.text(key, **values)


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


class UnexpectedStateRecoveryManager(RecordingStateRecoveryManager):
    def recover(
        self,
        plan: StateRecoveryPlan,
        *,
        confirmed: bool,
    ) -> StateRecoveryCommit:
        assert confirmed
        raise RuntimeError("token=private-state-recovery-worker-error")


class RejectedStateRecoveryManager(RecordingStateRecoveryManager):
    def recover(
        self,
        plan: StateRecoveryPlan,
        *,
        confirmed: bool,
    ) -> StateRecoveryCommit:
        assert confirmed
        raise StateRecoveryPreconditionError("typed=reviewed-state-file-changed")


class UnknownDurabilityStateRecoveryManager(RecordingStateRecoveryManager):
    def recover(
        self,
        plan: StateRecoveryPlan,
        *,
        confirmed: bool,
    ) -> StateRecoveryCommit:
        assert confirmed
        raise StateRecoverySourceError("token=private-durable-recovery-result")


class SlowStateRecoveryManager(RecordingStateRecoveryManager):
    def __init__(self, report: StateRecoveryReport) -> None:
        super().__init__(report)
        self.started = Event()
        self.release = Event()

    def recover(
        self,
        plan: StateRecoveryPlan,
        *,
        confirmed: bool,
    ) -> StateRecoveryCommit:
        self.started.set()
        assert self.release.wait(timeout=1)
        return super().recover(plan, confirmed=confirmed)


async def wait_for_thread_event(event: Event, *, timeout: float = 1) -> None:
    assert await asyncio.to_thread(event.wait, timeout)


class UnexpectedInspectionStateRecoveryManager:
    def inspect(self) -> StateRecoveryReport:
        raise RuntimeError("token=private-state-recovery-inspection-error")

    def recover(
        self,
        plan: StateRecoveryPlan,
        *,
        confirmed: bool,
    ) -> StateRecoveryCommit:
        raise AssertionError("an unavailable startup inspection must not recover")


class UnexpectedReviewStateRecoveryManager(RecordingStateRecoveryManager):
    def __init__(self, report: StateRecoveryReport) -> None:
        super().__init__(report)
        self.inspections = 0

    def inspect(self) -> StateRecoveryReport:
        self.inspections += 1
        if self.inspections > 1:
            raise RuntimeError("token=private-state-recovery-review-error")
        return self.report


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
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, StateRecoveryMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        assert app.screen.query_one("#state-recovery-title", Static).content == "目录恢复可用"
        assert app.screen.query_one("#state-recovery-backup", Static).content == (
            "目录可用 revision 6 profiles 0"
        )
        assert str(app.screen.query_one("#review-state-recovery", Button).label) == "目录审阅恢复"

        await pilot.click("#review-state-recovery")

        assert (
            app.screen.query_one("#state-recovery-confirm-title", Static).content == "目录确认恢复"
        )
        assert app.screen.query_one("#state-recovery-confirm-primary", Static).content == (
            f"目录主文件指纹 {'a' * 64}"
        )
        assert app.screen.query_one("#state-recovery-confirm-backup-sha", Static).content == (
            f"目录备份指纹 {'b' * 64}"
        )

        await pilot.click("#confirm-state-recovery")
        await pilot.pause()

        assert recovery.confirmations == [(plan, True)]
        assert app.screen.query_one("#state-recovery-result-title", Static).content == (
            "目录恢复成功"
        )
        assert app.screen.query_one("#state-recovery-result-revision", Static).content == (
            "目录结果 revision 6"
        )
        assert app.screen.query_one("#state-recovery-result-archive", Static).content == (
            "目录归档 /state/state.json.corrupt-reviewed"
        )
        assert str(app.screen.query_one("#state-recovery-return-dashboard", Button).label) == (
            "目录返回仪表盘"
        )

        await pilot.click("#state-recovery-return-dashboard")
        await pilot.pause()

        assert app.screen.query_one("#empty-state-title", Static).content == "尚未创建代理配置"


async def test_unexpected_state_recovery_failure_is_unknown_and_not_disclosed() -> None:
    plan = StateRecoveryPlan(
        primary_sha256="a" * 64,
        backup_sha256="b" * 64,
        backup_revision=6,
        backup_profile_count=0,
    )
    recovery = UnexpectedStateRecoveryManager(
        StateRecoveryReport(
            availability=RecoveryAvailability.RECOVERY_AVAILABLE,
            plan=plan,
        )
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(state_recovery_manager=recovery),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, StateRecoveryMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#review-state-recovery")
        await pilot.click("#confirm-state-recovery")
        await pilot.pause()

        assert app.screen.query_one("#state-recovery-error-title", Static).content == (
            "目录恢复结果未知"
        )
        assert app.screen.query_one("#state-recovery-error-details", Static).content == (
            "目录恢复未知详情"
        )
        assert app.screen.query_one("#state-recovery-error-safety", Static).content == (
            "目录恢复未知安全说明"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-state-recovery-worker-error" not in rendered_text


async def test_changed_reviewed_state_is_a_catalogued_rejection_without_retry() -> None:
    plan = StateRecoveryPlan(
        primary_sha256="a" * 64,
        backup_sha256="b" * 64,
        backup_revision=6,
        backup_profile_count=0,
    )
    recovery = RejectedStateRecoveryManager(
        StateRecoveryReport(
            availability=RecoveryAvailability.RECOVERY_AVAILABLE,
            plan=plan,
        )
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(state_recovery_manager=recovery),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, StateRecoveryMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#review-state-recovery")
        await pilot.click("#confirm-state-recovery")
        await pilot.pause()

        assert app.screen.query_one("#state-recovery-rejection-title", Static).content == (
            "目录恢复拒绝"
        )
        assert app.screen.query_one("#state-recovery-rejection-details", Static).content == (
            "typed=reviewed-state-file-changed"
        )
        assert app.screen.query_one("#state-recovery-rejection-safety", Static).content == (
            "目录拒绝安全说明"
        )
        assert not app.screen.query("#confirm-state-recovery")


async def test_durability_failure_is_unknown_and_not_misreported_as_rejected() -> None:
    plan = StateRecoveryPlan(
        primary_sha256="a" * 64,
        backup_sha256="b" * 64,
        backup_revision=6,
        backup_profile_count=0,
    )
    recovery = UnknownDurabilityStateRecoveryManager(
        StateRecoveryReport(
            availability=RecoveryAvailability.RECOVERY_AVAILABLE,
            plan=plan,
        )
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(state_recovery_manager=recovery),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, StateRecoveryMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#review-state-recovery")
        await pilot.click("#confirm-state-recovery")
        await pilot.pause()

        assert app.screen.query_one("#state-recovery-error-title", Static).content == (
            "目录恢复结果未知"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-durable-recovery-result" not in rendered_text
        assert not app.screen.query("#state-recovery-rejection-title")


async def test_confirmed_state_recovery_exposes_non_returning_progress() -> None:
    plan = StateRecoveryPlan(
        primary_sha256="a" * 64,
        backup_sha256="b" * 64,
        backup_revision=6,
        backup_profile_count=0,
    )
    recovery = SlowStateRecoveryManager(
        StateRecoveryReport(
            availability=RecoveryAvailability.RECOVERY_AVAILABLE,
            plan=plan,
        )
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(state_recovery_manager=recovery),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, StateRecoveryMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#review-state-recovery")
        await pilot.click("#confirm-state-recovery")
        await wait_for_thread_event(recovery.started)
        await pilot.pause()

        try:
            assert app.screen.query_one("#state-recovery-confirm-safety", Static).content == (
                "目录正在恢复"
            )
            assert app.screen.query_one("#confirm-state-recovery", Button).disabled is True
            await pilot.press("escape")
            assert app.screen.query_one("#state-recovery-confirm-safety", Static).content == (
                "目录正在恢复"
            )
        finally:
            recovery.release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()


async def test_newer_state_schema_is_never_offered_as_corruption_recovery() -> None:
    recovery = RecordingStateRecoveryManager(
        StateRecoveryReport(
            availability=RecoveryAvailability.UNSUPPORTED_SCHEMA,
            found_schema_version=2,
        )
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(state_recovery_manager=recovery),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, StateRecoveryMarkerCatalog())
        ),
    )

    async with app.run_test():
        assert app.screen.query_one("#state-recovery-title", Static).content == ("目录未来版本")
        assert app.screen.query_one("#state-recovery-guidance", Static).content == (
            "目录未来 schema 2"
        )
        assert not app.screen.query("#review-state-recovery")


async def test_unverified_backup_is_catalogued_without_a_recovery_action() -> None:
    recovery = RecordingStateRecoveryManager(
        StateRecoveryReport(availability=RecoveryAvailability.RECOVERY_UNAVAILABLE)
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(state_recovery_manager=recovery),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, StateRecoveryMarkerCatalog())
        ),
    )

    async with app.run_test():
        assert app.screen.query_one("#state-recovery-title", Static).content == ("目录恢复不可用")
        assert app.screen.query_one("#state-recovery-guidance", Static).content == (
            "目录恢复不可用说明"
        )
        assert not app.screen.query("#review-state-recovery")


async def test_unexpected_review_reinspection_failure_is_safe_and_catalogued() -> None:
    plan = StateRecoveryPlan(
        primary_sha256="a" * 64,
        backup_sha256="b" * 64,
        backup_revision=6,
        backup_profile_count=0,
    )
    recovery = UnexpectedReviewStateRecoveryManager(
        StateRecoveryReport(
            availability=RecoveryAvailability.RECOVERY_AVAILABLE,
            plan=plan,
        )
    )
    app = ManagerApp(
        host_tools=ManagerAppHostTools(state_recovery_manager=recovery),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, StateRecoveryMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#review-state-recovery")

        assert app.screen.query_one("#state-recovery-planning-error-title", Static).content == (
            "目录恢复计划失败"
        )
        assert app.screen.query_one("#state-recovery-planning-error-details", Static).content == (
            "目录恢复计划失败详情"
        )
        assert app.screen.query_one("#state-recovery-planning-error-safety", Static).content == (
            "目录恢复计划安全说明"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-state-recovery-review-error" not in rendered_text
        assert not app.screen.query("#confirm-state-recovery")


async def test_unexpected_state_inspection_failure_starts_safe_and_not_disclosed() -> None:
    app = ManagerApp(
        host_tools=ManagerAppHostTools(
            state_recovery_manager=UnexpectedInspectionStateRecoveryManager()
        ),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, StateRecoveryMarkerCatalog())
        ),
    )

    async with app.run_test():
        assert app.screen.query_one("#state-recovery-inspection-error-title", Static).content == (
            "目录恢复检查失败"
        )
        assert app.screen.query_one("#state-recovery-inspection-error-details", Static).content == (
            "目录恢复检查失败详情"
        )
        assert app.screen.query_one("#state-recovery-inspection-error-safety", Static).content == (
            "目录恢复检查安全说明"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-state-recovery-inspection-error" not in rendered_text
        assert not app.screen.query("#create-first-profile")
