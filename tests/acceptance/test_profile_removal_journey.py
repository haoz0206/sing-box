from textual.widgets import Button, Static

from sb_manager.adapters.memory_state import MemoryStateStore
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
from sb_manager.transactions.apply import ApplyOutcome, ApplyTransactionResult
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools


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


def app_for(
    remover: RecordingProfileRemover,
    *,
    state_store: MemoryStateStore | None = None,
) -> ManagerApp:
    store = state_store or MemoryStateStore(installation(remover.status))
    return ManagerApp(
        manager=Manager(state_store=store),
        host_tools=ManagerAppHostTools(
            profile_details_reader=FixedProfileDetailsReader(remover.status),
            profile_remover=remover,
        ),
    )


async def test_operator_reviews_draft_profile_removal_before_confirmation() -> None:
    remover = RecordingProfileRemover()
    app = app_for(remover)

    async with app.run_test() as pilot:
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
    app = app_for(remover, state_store=state_store)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#remove-profile")
        await pilot.click("#confirm-profile-removal")

        assert (
            str(app.screen.query_one("#profile-removal-return-dashboard", Button).label)
            == "返回仪表盘"
        )
        await pilot.click("#profile-removal-return-dashboard")

        assert app.screen.query_one("#empty-state-title", Static).content == "尚未创建代理配置"
        assert app.screen.query_one("#profile-summary", Static).content == "配置：0 已应用 · 0 草案"


async def test_operator_confirms_applied_profile_shutdown_and_sees_healthy_result() -> None:
    app = app_for(RecordingProfileRemover(status=ProfileStatus.APPLIED))

    async with app.run_test() as pilot:
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


async def test_failed_applied_profile_removal_does_not_claim_success() -> None:
    app = app_for(ValidationFailingProfileRemover())

    async with app.run_test() as pilot:
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
