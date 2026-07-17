from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from textual.widgets import Button, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import Manager
from sb_manager.application.profile_availability import (
    ProfileAvailability,
    ProfileAvailabilityPlan,
    ProfileAvailabilityResult,
    ProfileAvailabilityService,
    ProfileResumePortUnavailableError,
)
from sb_manager.application.profile_details import ProfileDetails, ProfileDetailsService
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import RealityMaterial
from sb_manager.protocols.catalog import ProtocolCatalog, RealityHandler
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    CommitResult,
    ConfigTargetPrecondition,
    RollbackResult,
)
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools
from sb_manager.ui.screens.profile_availability import ProfileAvailabilityResultScreen


class GenerationMustNotRun:
    def generate(self) -> RealityMaterial:
        raise AssertionError("availability changes must reuse persisted material")


class PausePortSource:
    def is_available(self, port: int) -> bool:
        raise AssertionError("pausing must not probe the recorded port")

    def choose_available(self) -> int:
        raise AssertionError("pausing must not choose a port")


class AvailableResumePortSource:
    def is_available(self, port: int) -> bool:
        return True

    def choose_available(self) -> int:
        raise AssertionError("fixed-port resume must not choose a port")


class TrackingLock:
    @contextmanager
    def acquire(self) -> Iterator[None]:
        yield


class RecordingApplier:
    def __init__(self) -> None:
        self.document: Mapping[str, object] | None = None

    def apply(
        self,
        document: Mapping[str, object],
        *,
        precondition: ConfigTargetPrecondition,
    ) -> ApplyTransactionResult:
        self.document = document
        return ApplyTransactionResult(
            outcome=ApplyOutcome.APPLIED,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=RuntimeRefreshResult(success=True, diagnostics="reloaded"),
            postcondition=RuntimePostcondition(healthy=True, diagnostics="active"),
            rollback=None,
        )


class PausedProfileDetailsReader:
    def get_profile_details(self, profile_id: str) -> ProfileDetails:
        return ProfileDetails(
            profile_id=profile_id,
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            status=ProfileStatus.APPLIED,
            listen_port=4433,
            server_address="proxy.example.com",
            connection_info=None,
            enabled=False,
        )


class ResumePortUnavailableManager:
    def plan_change(self, request: object) -> object:
        raise ProfileResumePortUnavailableError(4433)

    def apply_change(self, plan: object, *, confirmed: bool) -> object:
        raise AssertionError("an unavailable resume plan must not be confirmed")


class UnexpectedProfileAvailabilityManager:
    def plan_change(self, request: object) -> ProfileAvailabilityPlan:
        return ProfileAvailabilityPlan(
            profile_id="profile-1",
            profile_name="手机",
            current=ProfileAvailability.PAUSED,
            target=ProfileAvailability.ACTIVE,
            expected_revision=5,
            remaining_active_profile_count=1,
            port_selection=PortSelection.FIXED,
            recorded_listen_port=4433,
            port_may_change=False,
            requires_live_apply=True,
        )

    def apply_change(
        self,
        plan: ProfileAvailabilityPlan,
        *,
        confirmed: bool,
    ) -> ProfileAvailabilityResult:
        assert confirmed
        raise RuntimeError("token=private-profile-availability-worker-error")


class UnexpectedPlanningProfileAvailabilityManager:
    def plan_change(self, request: object) -> ProfileAvailabilityPlan:
        raise RuntimeError("token=private-profile-availability-planning-error")

    def apply_change(
        self,
        plan: ProfileAvailabilityPlan,
        *,
        confirmed: bool,
    ) -> ProfileAvailabilityResult:
        raise AssertionError("a failed availability plan must not be confirmed")


async def test_operator_pauses_applied_profile_without_deleting_intent() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        protocol_material=RealityMaterial(
            user_uuid="11111111-1111-4111-8111-111111111111",
            private_key="private-key",
            public_key="public-key",
            short_id="0123456789abcdef",
            server_name="www.cloudflare.com",
        ),
        server_address="proxy.example.com",
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=4,
            profiles=(profile,),
            expected_config_sha256="a" * 64,
        )
    )
    catalog = ProtocolCatalog((RealityHandler(material_source=GenerationMustNotRun()),))
    applier = RecordingApplier()
    availability = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=catalog,
        port_source=PausePortSource(),
        applier=applier,
        apply_lock=TrackingLock(),
    )
    app = ManagerApp(
        manager=Manager(state_store=state_store),
        host_tools=ManagerAppHostTools(
            profile_details_reader=ProfileDetailsService(
                state_store=state_store,
                protocol_catalog=catalog,
            ),
            profile_availability_manager=availability,
        ),
    )

    async with app.run_test() as pilot:
        assert app.query_one("#profile-summary", Static).content == (
            "配置：1 在线 · 0 已暂停 · 0 草案"
        )
        assert "在线" in str(app.query_one("#profile-0", Static).content)

        await pilot.click("#view-profile-0")

        assert app.screen.query_one("#profile-details-status", Static).content == (
            "状态：已应用 · 在线"
        )
        action = app.screen.query_one("#change-profile-availability", Button)
        assert str(action.label) == "暂停配置"

        await pilot.click("#change-profile-availability")

        assert app.screen.query_one("#profile-availability-plan-title", Static).content == (
            "确认暂停配置"
        )
        assert app.screen.query_one("#profile-availability-plan-impact", Static).content == (
            "将从完整 sing-box 配置中移除此 inbound，保留 profile、端口和凭据。"
        )

        await pilot.click("#confirm-profile-availability")
        await pilot.pause()

        assert app.screen.query_one("#profile-availability-result-title", Static).content == (
            "配置已暂停"
        )
        assert state_store.load().profiles[0].enabled is False
        assert state_store.load().profiles[0].protocol_material == profile.protocol_material
        assert applier.document == {
            "inbounds": [],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        }


async def test_operator_restores_paused_profile_from_details() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
        protocol_material=RealityMaterial(
            user_uuid="11111111-1111-4111-8111-111111111111",
            private_key="private-key",
            public_key="public-key",
            short_id="0123456789abcdef",
            server_name="www.cloudflare.com",
        ),
        server_address="proxy.example.com",
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=5,
            profiles=(profile,),
            expected_config_sha256="b" * 64,
        )
    )
    catalog = ProtocolCatalog((RealityHandler(material_source=GenerationMustNotRun()),))
    applier = RecordingApplier()
    availability = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=catalog,
        port_source=AvailableResumePortSource(),
        applier=applier,
        apply_lock=TrackingLock(),
    )
    app = ManagerApp(
        manager=Manager(state_store=state_store),
        host_tools=ManagerAppHostTools(
            profile_details_reader=ProfileDetailsService(
                state_store=state_store,
                protocol_catalog=catalog,
            ),
            profile_availability_manager=availability,
        ),
    )

    async with app.run_test() as pilot:
        assert app.query_one("#profile-summary", Static).content == (
            "配置：0 在线 · 1 已暂停 · 0 草案"
        )
        assert "已暂停" in str(app.query_one("#profile-0", Static).content)

        await pilot.click("#view-profile-0")

        assert app.screen.query_one("#profile-details-status", Static).content == (
            "状态：已应用 · 已暂停"
        )
        action = app.screen.query_one("#change-profile-availability", Button)
        assert str(action.label) == "恢复配置"

        await pilot.click("#change-profile-availability")

        assert app.screen.query_one("#profile-availability-plan-title", Static).content == (
            "确认恢复配置"
        )
        assert app.screen.query_one("#profile-availability-plan-impact", Static).content == (
            "将把此 inbound 恢复到完整 sing-box 配置，校验并刷新服务。"
        )

        await pilot.click("#confirm-profile-availability")
        await pilot.pause()

        assert app.screen.query_one("#profile-availability-result-title", Static).content == (
            "配置已恢复"
        )
        assert state_store.load().profiles[0].enabled is True
        assert applier.document is not None
        assert [inbound["tag"] for inbound in applier.document["inbounds"]] == ["profile-1"]


async def test_unavailable_resume_port_has_actionable_planning_guidance() -> None:
    paused = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=5, profiles=(paused,))
    )
    app = ManagerApp(
        manager=Manager(state_store=state_store),
        host_tools=ManagerAppHostTools(
            profile_details_reader=PausedProfileDetailsReader(),
            profile_availability_manager=ResumePortUnavailableManager(),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#change-profile-availability")

        assert app.screen.query_one("#profile-availability-error-title", Static).content == (
            "无法确认配置状态变更"
        )
        assert app.screen.query_one("#profile-availability-error-details", Static).content == (
            "Port 4433 is unavailable for profile resume"
        )
        assert app.screen.query_one("#profile-availability-error-safety", Static).content == (
            "desired state 未提交。请重新打开配置详情并检查当前服务状态。"
        )


async def test_unexpected_availability_planning_failure_is_safe_and_not_disclosed() -> None:
    paused = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=5, profiles=(paused,))
    )
    app = ManagerApp(
        manager=Manager(state_store=state_store),
        host_tools=ManagerAppHostTools(
            profile_details_reader=PausedProfileDetailsReader(),
            profile_availability_manager=UnexpectedPlanningProfileAvailabilityManager(),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#change-profile-availability")
        await pilot.pause()

        assert app.screen.query_one(
            "#profile-availability-planning-error-title", Static
        ).content == ("无法准备配置状态变更")
        assert app.screen.query_one(
            "#profile-availability-planning-error-details", Static
        ).content == ("读取暂停/恢复计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。")
        assert (
            app.screen.query_one("#profile-availability-planning-error-safety", Static).content
            == "尚未执行任何操作。请返回配置列表，重新打开详情后再试。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-availability-planning-error" not in rendered_text


async def test_unexpected_availability_failure_is_unknown_and_not_disclosed() -> None:
    paused = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=5, profiles=(paused,))
    )
    app = ManagerApp(
        manager=Manager(state_store=state_store),
        host_tools=ManagerAppHostTools(
            profile_details_reader=PausedProfileDetailsReader(),
            profile_availability_manager=UnexpectedProfileAvailabilityManager(),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#change-profile-availability")
        await pilot.click("#confirm-profile-availability")
        await pilot.pause()

        assert app.screen.query_one("#profile-availability-error-title", Static).content == (
            "无法确认配置状态变更"
        )
        assert app.screen.query_one("#profile-availability-error-details", Static).content == (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#profile-availability-error-safety", Static).content == (
            "服务器配置、服务和 desired state 的结果均未知。"
            "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-availability-worker-error" not in rendered_text


def availability_result(
    transaction: ApplyTransactionResult,
) -> ProfileAvailabilityResult:
    return ProfileAvailabilityResult(
        availability=ProfileAvailability.PAUSED,
        listen_port=4433,
        transaction=transaction,
        committed_revision=None,
    )


async def test_pause_validation_failure_explains_that_nothing_changed() -> None:
    result = availability_result(
        ApplyTransactionResult(
            outcome=ApplyOutcome.VALIDATION_FAILED,
            validation=ConfigValidationResult(
                valid=False,
                diagnostics="paused candidate is invalid",
            ),
            runtime_refresh=None,
            postcondition=None,
            rollback=None,
        )
    )
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore()))

    async with app.run_test() as pilot:
        app.push_screen(ProfileAvailabilityResultScreen(result))
        await pilot.pause()

        assert app.screen.query_one("#profile-availability-result-title", Static).content == (
            "配置校验失败，状态未改变"
        )
        assert app.screen.query_one("#profile-availability-result-details", Static).content == (
            "paused candidate is invalid"
        )
        assert app.screen.query_one("#profile-availability-result-safety", Static).content == (
            "原有配置、服务和 desired state 均未改变。"
        )


async def test_pause_precondition_failure_explains_that_nothing_was_written() -> None:
    result = availability_result(
        ApplyTransactionResult(
            outcome=ApplyOutcome.PRECONDITION_FAILED,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=None,
            postcondition=None,
            rollback=None,
            commit=CommitResult(
                success=False,
                diagnostics="Live configuration fingerprint changed after review",
            ),
        )
    )
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore()))

    async with app.run_test() as pilot:
        app.push_screen(ProfileAvailabilityResultScreen(result))
        await pilot.pause()

        assert app.screen.query_one("#profile-availability-result-title", Static).content == (
            "服务器配置已变化，状态未改变"
        )
        assert app.screen.query_one("#profile-availability-result-details", Static).content == (
            "Live configuration fingerprint changed after review"
        )
        assert app.screen.query_one("#profile-availability-result-safety", Static).content == (
            "本次尚未写入配置，请重新检查后再确认。"
        )


async def test_failed_pause_reports_successful_automatic_rollback() -> None:
    result = availability_result(
        ApplyTransactionResult(
            outcome=ApplyOutcome.ROLLED_BACK,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=RuntimeRefreshResult(
                success=False,
                diagnostics="service failed",
            ),
            postcondition=None,
            rollback=RollbackResult(
                success=True,
                diagnostics="old configuration restored",
                recovery_instructions=(),
            ),
            commit=CommitResult(success=True, diagnostics="committed"),
        )
    )
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore()))

    async with app.run_test() as pilot:
        app.push_screen(ProfileAvailabilityResultScreen(result))
        await pilot.pause()

        assert app.screen.query_one("#profile-availability-result-title", Static).content == (
            "状态变更失败，已自动回滚"
        )
        assert app.screen.query_one("#profile-availability-result-details", Static).content == (
            "old configuration restored"
        )
        assert app.screen.query_one("#profile-availability-result-safety", Static).content == (
            "原有配置、服务和 desired state 已保留。"
        )


async def test_failed_pause_exposes_manual_recovery_steps() -> None:
    result = availability_result(
        ApplyTransactionResult(
            outcome=ApplyOutcome.ROLLBACK_FAILED,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=RuntimeRefreshResult(
                success=False,
                diagnostics="service failed",
            ),
            postcondition=None,
            rollback=RollbackResult(
                success=False,
                diagnostics="old service did not recover",
                recovery_instructions=(
                    "restore /etc/sing-box/config.json.bak",
                    "restart sing-box.service",
                ),
            ),
            commit=CommitResult(success=True, diagnostics="committed"),
        )
    )
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore()))

    async with app.run_test() as pilot:
        app.push_screen(ProfileAvailabilityResultScreen(result))
        await pilot.pause()

        assert app.screen.query_one("#profile-availability-result-title", Static).content == (
            "回滚未完成，需要人工恢复"
        )
        assert app.screen.query_one("#profile-availability-result-details", Static).content == (
            "old service did not recover"
        )
        assert app.screen.query_one("#profile-availability-recovery-step-0", Static).content == (
            "1. restore /etc/sing-box/config.json.bak"
        )
        assert app.screen.query_one("#profile-availability-recovery-step-1", Static).content == (
            "2. restart sing-box.service"
        )
