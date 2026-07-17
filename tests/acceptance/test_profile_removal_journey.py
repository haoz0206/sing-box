from typing import cast

from textual.widgets import Button, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.host_diagnostics import (
    HostCondition,
    HostDiagnostics,
    HostDiagnosticsReport,
)
from sb_manager.application.manager import Manager
from sb_manager.application.profile_details import ProfileDetails
from sb_manager.application.profile_removal import (
    ProfileRemovalPlan,
    ProfileRemovalResult,
    ProfileRemovalScope,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    CommitResult,
    RollbackResult,
)
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools, ManagerAppInterfaceTools
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText

EXPECTED_DASHBOARD_INSPECTIONS = 2


class ProfileRemovalMarkerCatalog:
    """Render markers across the nested profile-removal journey."""

    def text(self, key: UiText, /, **values: object) -> str:
        markers = {
            "profile_removal.plan.title": "目录确认移除配置",
            "profile_removal.result.draft.title": "目录草案已移除",
            "profile_removal.result.applied.title": "目录配置已下线并移除",
            "profile_removal.operational.title": "目录无法确认移除结果",
            "profile_removal.operational.unexpected.details": "目录隐藏意外错误",
            "profile_removal.operational.unknown.safety": "目录未知结果恢复指引",
            "profile_removal.planning.title": "目录无法准备配置移除",
            "profile_removal.planning.details": "目录隐藏计划错误",
            "profile_removal.planning.safety": "目录计划恢复指引",
        }
        if marker := markers.get(key.value):
            return marker
        return SIMPLIFIED_CHINESE.text(key, **values)


def profile(status: ProfileStatus) -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=status,
    )


def installation(status: ProfileStatus) -> ManagedInstallation:
    return ManagedInstallation(schema_version=1, revision=2, profiles=(profile(status),))


class FixedProfileDetailsReader:
    def __init__(self, status: ProfileStatus) -> None:
        self.status = status

    def get_profile_details(self, profile_id: str) -> ProfileDetails:
        assert profile_id == "profile-1"
        return ProfileDetails(
            profile_id=profile_id,
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            status=self.status,
            listen_port=4433,
            server_address=None,
            connection_info=None,
        )


class RecordingProfileRemover:
    def __init__(self, *, status: ProfileStatus = ProfileStatus.DRAFT) -> None:
        self.status = status
        self.planned_profile_ids: list[str] = []
        self.removals: list[tuple[ProfileRemovalPlan, bool]] = []

    def plan_removal(self, profile_id: str) -> ProfileRemovalPlan:
        self.planned_profile_ids.append(profile_id)
        return ProfileRemovalPlan(
            profile_id=profile_id,
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            status=self.status,
            expected_revision=2,
            scope=(
                ProfileRemovalScope.LIVE_CONFIGURATION
                if self.status is ProfileStatus.APPLIED
                else ProfileRemovalScope.DESIRED_STATE_ONLY
            ),
            remaining_profile_count=0,
            remaining_applied_count=0,
        )

    def remove_profile(
        self,
        plan: ProfileRemovalPlan,
        *,
        confirmed: bool,
    ) -> ProfileRemovalResult:
        self.removals.append((plan, confirmed))
        transaction = (
            ApplyTransactionResult(
                outcome=ApplyOutcome.APPLIED,
                validation=ConfigValidationResult(valid=True, diagnostics="valid"),
                runtime_refresh=RuntimeRefreshResult(success=True, diagnostics="reloaded"),
                postcondition=RuntimePostcondition(healthy=True, diagnostics="active"),
                rollback=None,
            )
            if plan.scope is ProfileRemovalScope.LIVE_CONFIGURATION
            else None
        )
        return ProfileRemovalResult(
            scope=plan.scope,
            committed_revision=3,
            remaining_profile_count=0,
            transaction=transaction,
        )


class ValidationFailingProfileRemover(RecordingProfileRemover):
    def __init__(self) -> None:
        super().__init__(status=ProfileStatus.APPLIED)

    def remove_profile(
        self,
        plan: ProfileRemovalPlan,
        *,
        confirmed: bool,
    ) -> ProfileRemovalResult:
        return ProfileRemovalResult(
            scope=ProfileRemovalScope.LIVE_CONFIGURATION,
            committed_revision=None,
            remaining_profile_count=0,
            transaction=ApplyTransactionResult(
                outcome=ApplyOutcome.VALIDATION_FAILED,
                validation=ConfigValidationResult(
                    valid=False,
                    diagnostics="candidate has no valid inbound",
                ),
                runtime_refresh=None,
                postcondition=None,
                rollback=None,
            ),
        )


class TransactionResultProfileRemover(RecordingProfileRemover):
    def __init__(self, transaction: ApplyTransactionResult | None) -> None:
        super().__init__(status=ProfileStatus.APPLIED)
        self.transaction = transaction

    def remove_profile(
        self,
        plan: ProfileRemovalPlan,
        *,
        confirmed: bool,
    ) -> ProfileRemovalResult:
        assert confirmed
        return ProfileRemovalResult(
            scope=ProfileRemovalScope.LIVE_CONFIGURATION,
            committed_revision=None,
            remaining_profile_count=0,
            transaction=self.transaction,
        )


def failed_live_transaction(
    outcome: ApplyOutcome,
    *,
    commit: CommitResult | None = None,
    rollback: RollbackResult | None = None,
) -> ApplyTransactionResult:
    return ApplyTransactionResult(
        outcome=outcome,
        validation=ConfigValidationResult(valid=True, diagnostics="valid"),
        runtime_refresh=None,
        postcondition=None,
        rollback=rollback,
        commit=commit,
    )


class UnavailableProfileRemover(RecordingProfileRemover):
    def __init__(self) -> None:
        super().__init__(status=ProfileStatus.APPLIED)

    def remove_profile(
        self,
        plan: ProfileRemovalPlan,
        *,
        confirmed: bool,
    ) -> ProfileRemovalResult:
        raise ConfigurationApplyError("sudo authorization denied")


class UnexpectedProfileRemover(RecordingProfileRemover):
    def __init__(self) -> None:
        super().__init__(status=ProfileStatus.APPLIED)

    def remove_profile(
        self,
        plan: ProfileRemovalPlan,
        *,
        confirmed: bool,
    ) -> ProfileRemovalResult:
        assert confirmed
        raise RuntimeError("token=private-profile-removal-worker-error")


class UnexpectedPlanningProfileRemover(RecordingProfileRemover):
    def plan_removal(self, profile_id: str) -> ProfileRemovalPlan:
        raise RuntimeError("token=private-profile-removal-planning-error")


class StateMutatingProfileRemover(RecordingProfileRemover):
    def __init__(self, state_store: MemoryStateStore) -> None:
        super().__init__()
        self.state_store = state_store

    def remove_profile(
        self,
        plan: ProfileRemovalPlan,
        *,
        confirmed: bool,
    ) -> ProfileRemovalResult:
        result = super().remove_profile(plan, confirmed=confirmed)
        current = self.state_store.load()
        self.state_store.save(
            ManagedInstallation(
                schema_version=current.schema_version,
                revision=3,
                profiles=(),
                expected_config_sha256=current.expected_config_sha256,
            )
        )
        return result


class HostDiagnosticsChangedAfterRemoval:
    def __init__(self) -> None:
        self.inspections = 0

    def inspect(self) -> HostDiagnosticsReport:
        self.inspections += 1
        healthy = self.inspections == 1
        return HostDiagnosticsReport(
            condition=HostCondition.HEALTHY if healthy else HostCondition.UNHEALTHY,
            summary="sing-box 服务运行正常" if healthy else "sing-box 服务需要检查",
            diagnostics="active" if healthy else "inactive after desired-state change",
            recovery_instructions=() if healthy else ("检查 sing-box 服务",),
        )


def app_for(
    remover: RecordingProfileRemover,
    *,
    state_store: MemoryStateStore | None = None,
    host_diagnostics: HostDiagnostics | None = None,
    copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
) -> ManagerApp:
    store = state_store or MemoryStateStore(installation(remover.status))
    return ManagerApp(
        manager=Manager(state_store=store),
        host_tools=ManagerAppHostTools(
            host_diagnostics=host_diagnostics,
            profile_details_reader=FixedProfileDetailsReader(remover.status),
            profile_remover=remover,
        ),
        interface_tools=ManagerAppInterfaceTools(copy_catalog=copy_catalog),
    )


async def test_profile_removal_copy_catalog_flows_from_details_through_result() -> None:
    app = app_for(
        RecordingProfileRemover(),
        copy_catalog=cast(CopyCatalog, ProfileRemovalMarkerCatalog()),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")

        assert app.screen.query_one("#profile-removal-title", Static).content == (
            "目录确认移除配置"
        )

        await pilot.click("#confirm-profile-removal")
        await pilot.pause()

        assert app.screen.query_one("#profile-removal-result-title", Static).content == (
            "目录草案已移除"
        )


async def test_profile_removal_copy_catalog_reaches_unknown_result() -> None:
    app = app_for(
        UnexpectedProfileRemover(),
        copy_catalog=cast(CopyCatalog, ProfileRemovalMarkerCatalog()),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")
        await pilot.pause()

        assert app.screen.query_one("#profile-removal-error-title", Static).content == (
            "目录无法确认移除结果"
        )
        assert app.screen.query_one("#profile-removal-error-details", Static).content == (
            "目录隐藏意外错误"
        )
        assert app.screen.query_one("#profile-removal-error-safety", Static).content == (
            "目录未知结果恢复指引"
        )


async def test_profile_removal_copy_catalog_reaches_planning_failure() -> None:
    app = app_for(
        UnexpectedPlanningProfileRemover(),
        copy_catalog=cast(CopyCatalog, ProfileRemovalMarkerCatalog()),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")

        assert app.screen.query_one("#profile-removal-planning-error-title", Static).content == (
            "目录无法准备配置移除"
        )
        assert (
            app.screen.query_one("#profile-removal-planning-error-details", Static).content
            == "目录隐藏计划错误"
        )
        assert (
            app.screen.query_one("#profile-removal-planning-error-safety", Static).content
            == "目录计划恢复指引"
        )


async def test_profile_removal_copy_catalog_reaches_live_result() -> None:
    app = app_for(
        RecordingProfileRemover(status=ProfileStatus.APPLIED),
        copy_catalog=cast(CopyCatalog, ProfileRemovalMarkerCatalog()),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")
        await pilot.pause()

        assert app.screen.query_one("#profile-removal-result-title", Static).content == (
            "目录配置已下线并移除"
        )


async def test_operator_reviews_draft_profile_removal_before_confirmation() -> None:
    remover = RecordingProfileRemover()
    app = app_for(remover)

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        assert str(app.screen.query_one("#remove-profile", Button).label) == "移除此配置"

        await pilot.click("#remove-profile")

        assert remover.planned_profile_ids == ["profile-1"]
        assert app.screen.query_one("#profile-removal-title", Static).content == "确认移除配置"
        assert app.screen.query_one("#profile-removal-impact", Static).content == (
            "只删除 manager 中的草案，不会修改 sing-box 配置或刷新服务。"
        )
        assert app.screen.query_one("#profile-removal-safety", Static).content == (
            "当前仅预览，尚未删除任何内容。"
        )
        assert str(app.screen.query_one("#confirm-profile-removal", Button).label) == (
            "确认移除草案"
        )


async def test_operator_confirms_draft_removal_and_sees_desired_state_result() -> None:
    remover = RecordingProfileRemover()
    app = app_for(remover)

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")

        assert len(remover.removals) == 1
        plan, confirmed = remover.removals[0]
        assert plan.profile_id == "profile-1"
        assert confirmed is True
        assert app.screen.query_one("#profile-removal-result-title", Static).content == (
            "草案已移除"
        )
        assert app.screen.query_one("#profile-removal-result-details", Static).content == (
            "desired state 已提交 revision 3。"
        )
        assert app.screen.query_one("#profile-removal-result-safety", Static).content == (
            "未修改 sing-box 配置，也未刷新服务。"
        )


async def test_successful_profile_removal_returns_to_recomposed_dashboard() -> None:
    state_store = MemoryStateStore(installation(ProfileStatus.DRAFT))
    remover = StateMutatingProfileRemover(state_store)
    host_diagnostics = HostDiagnosticsChangedAfterRemoval()
    app = app_for(
        remover,
        state_store=state_store,
        host_diagnostics=host_diagnostics,
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.query_one("#runtime-status", Static).content == "服务状态：运行正常"
        assert host_diagnostics.inspections == 1

        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")

        assert (
            str(app.screen.query_one("#profile-removal-return-dashboard", Button).label)
            == "返回仪表盘"
        )
        await pilot.click("#profile-removal-return-dashboard")

        assert app.screen.query_one("#empty-state-title", Static).content == "尚未创建代理配置"
        assert app.screen.query_one("#profile-summary", Static).content == (
            "配置：0 在线 · 0 已暂停 · 0 草案"
        )
        await pilot.pause()
        assert app.screen.query_one("#runtime-status", Static).content == "服务状态：需要检查"
        assert host_diagnostics.inspections == EXPECTED_DASHBOARD_INSPECTIONS


async def test_operator_confirms_applied_profile_shutdown_and_sees_healthy_result() -> None:
    app = app_for(RecordingProfileRemover(status=ProfileStatus.APPLIED))

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")

        assert app.screen.query_one("#profile-removal-impact", Static).content == (
            "将生成不含此配置的完整 sing-box 配置，校验并刷新服务。失败时自动回滚。"
        )
        assert str(app.screen.query_one("#confirm-profile-removal", Button).label) == (
            "确认下线并移除"
        )
        await pilot.click("#confirm-profile-removal")

        assert app.screen.query_one("#profile-removal-result-title", Static).content == (
            "配置已下线并移除"
        )
        assert app.screen.query_one("#profile-removal-result-safety", Static).content == (
            "新配置已通过校验，服务刷新和健康检查已完成。"
        )


async def test_missing_host_transaction_requires_identity_status_and_history_checks() -> None:
    app = app_for(TransactionResultProfileRemover(None))

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")

        assert app.screen.query_one("#profile-removal-result-title", Static).content == (
            "无法确认移除结果"
        )
        assert app.screen.query_one("#profile-removal-result-details", Static).content == (
            "未收到可信的 host transaction。"
        )
        assert app.screen.query_one("#profile-removal-result-safety", Static).content == (
            "desired state 未提交，host transaction 结果未知。"
            "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
        )


async def test_precondition_failure_preserves_external_diagnostics_as_plain_text() -> None:
    app = app_for(
        TransactionResultProfileRemover(
            failed_live_transaction(
                ApplyOutcome.PRECONDITION_FAILED,
                commit=CommitResult(
                    success=False,
                    diagnostics="[bold]fingerprint[/bold] changed",
                ),
            )
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")

        details = app.screen.query_one("#profile-removal-result-details", Static)
        assert app.screen.query_one("#profile-removal-result-title", Static).content == (
            "服务器配置已变化，未移除"
        )
        assert details.content == "[bold]fingerprint[/bold] changed"
        assert details.render().plain == details.content
        assert app.screen.query_one("#profile-removal-result-safety", Static).content == (
            "本次尚未写入配置，请重新检查后再确认。"
        )


async def test_commit_failure_explains_that_runtime_was_not_refreshed() -> None:
    app = app_for(
        TransactionResultProfileRemover(
            failed_live_transaction(
                ApplyOutcome.COMMIT_FAILED,
                commit=CommitResult(success=False, diagnostics="target replace denied"),
            )
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")

        assert app.screen.query_one("#profile-removal-result-title", Static).content == (
            "无法写入移除后的配置"
        )
        assert app.screen.query_one("#profile-removal-result-details", Static).content == (
            "target replace denied"
        )
        assert app.screen.query_one("#profile-removal-result-safety", Static).content == (
            "尚未刷新服务，原有配置和 desired state 保持不变。"
        )


async def test_failed_runtime_refresh_reports_successful_rollback() -> None:
    app = app_for(
        TransactionResultProfileRemover(
            failed_live_transaction(
                ApplyOutcome.ROLLED_BACK,
                rollback=RollbackResult(
                    success=True,
                    diagnostics="old configuration restored",
                ),
            )
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")

        assert app.screen.query_one("#profile-removal-result-title", Static).content == (
            "移除失败，已自动回滚"
        )
        assert app.screen.query_one("#profile-removal-result-details", Static).content == (
            "old configuration restored"
        )
        assert app.screen.query_one("#profile-removal-result-safety", Static).content == (
            "原有配置、服务和 desired state 已保留。"
        )


async def test_failed_rollback_renders_plain_text_manual_recovery_steps() -> None:
    app = app_for(
        TransactionResultProfileRemover(
            failed_live_transaction(
                ApplyOutcome.ROLLBACK_FAILED,
                rollback=RollbackResult(
                    success=False,
                    diagnostics="[bold]rollback[/bold] restore failed",
                    recovery_instructions=(
                        "restore [bold]previous[/bold] configuration",
                        "restart sing-box",
                    ),
                ),
            )
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")

        details = app.screen.query_one("#profile-removal-result-details", Static)
        first_step = app.screen.query_one("#profile-removal-recovery-step-0", Static)
        assert app.screen.query_one("#profile-removal-result-title", Static).content == (
            "回滚未完成，需要人工恢复"
        )
        assert details.content == "[bold]rollback[/bold] restore failed"
        assert details.render().plain == details.content
        assert app.screen.query_one("#profile-removal-result-safety", Static).content == (
            "desired state 未提交。完成恢复前不要再次修改配置。"
        )
        assert first_step.content == "1. restore [bold]previous[/bold] configuration"
        assert first_step.render().plain == first_step.content
        assert app.screen.query_one("#profile-removal-recovery-step-1", Static).content == (
            "2. restart sing-box"
        )


async def test_failed_applied_profile_removal_does_not_claim_success() -> None:
    app = app_for(ValidationFailingProfileRemover())

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")

        assert app.screen.query_one("#profile-removal-result-title", Static).content == (
            "配置校验失败，未移除"
        )
        assert app.screen.query_one("#profile-removal-result-details", Static).content == (
            "candidate has no valid inbound"
        )
        assert app.screen.query_one("#profile-removal-result-safety", Static).content == (
            "原有配置、服务和 desired state 均未改变。"
        )


async def test_unknown_profile_removal_host_result_requires_operator_diagnostics() -> None:
    app = app_for(UnavailableProfileRemover())

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")

        assert app.screen.query_one("#profile-removal-error-title", Static).content == (
            "无法确认配置移除结果"
        )
        assert app.screen.query_one("#profile-removal-error-details", Static).content == (
            "sudo authorization denied"
        )
        assert app.screen.query_one("#profile-removal-error-safety", Static).content == (
            "desired state 未提交。请检查 sing-box 服务和 helper 日志后再决定是否重试。"
        )


async def test_unexpected_profile_removal_planning_failure_is_safe_and_not_disclosed() -> None:
    app = app_for(UnexpectedPlanningProfileRemover())

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.pause()

        assert app.screen.query_one("#profile-removal-planning-error-title", Static).content == (
            "无法准备配置移除"
        )
        assert app.screen.query_one("#profile-removal-planning-error-details", Static).content == (
            "读取配置移除计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#profile-removal-planning-error-safety", Static).content == (
            "尚未执行任何操作。请返回配置列表，重新打开详情后再试。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-removal-planning-error" not in rendered_text


async def test_unexpected_profile_removal_failure_is_unknown_and_not_disclosed() -> None:
    app = app_for(UnexpectedProfileRemover())

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")
        await pilot.pause()

        assert app.screen.query_one("#profile-removal-error-title", Static).content == (
            "无法确认配置移除结果"
        )
        assert app.screen.query_one("#profile-removal-error-details", Static).content == (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#profile-removal-error-safety", Static).content == (
            "服务器配置、服务和 desired state 的结果均未知。"
            "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-removal-worker-error" not in rendered_text
