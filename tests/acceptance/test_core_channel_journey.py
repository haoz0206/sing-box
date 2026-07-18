import asyncio
from pathlib import Path
from threading import Event

from textual.pilot import Pilot
from textual.widgets import Button, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.core_update import (
    CoreChannelPlan,
    CoreChannelPlanKind,
    CoreChannelService,
    CoreUpdatePlan,
    CoreUpdateResult,
    CoreUpdateService,
    CoreUpdateWarning,
    PlanCoreChannelRequest,
    PlanCoreUpdateRequest,
)
from sb_manager.application.protocol_compatibility import ProtocolCompatibilityPolicy
from sb_manager.artifacts.installation import (
    CoreActivation,
    CoreReleaseIdentity,
    InstalledCoreRelease,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    CoreArtifactRequest,
    CoreArtifactTrustMode,
    CoreRelease,
    CoreReleaseChannel,
    PlannedCoreArtifact,
    VerifiedCoreArtifact,
)
from sb_manager.seams.core_activator import CoreActivationRequest
from sb_manager.seams.core_switcher import CoreSwitchRequest
from sb_manager.ui.app import ManagerApp
from sb_manager.ui.screens.core_channels import CoreChannelSelectionScreen

EXPECTED_PLANNING_ATTEMPTS = 2


class NeverCalledExactUpdater:
    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        raise AssertionError("opening channel management must not open exact-version planning")

    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
        raise AssertionError("an already-current channel must not execute an update")


class AlreadyCurrentChannels:
    def __init__(self) -> None:
        self.requests: list[PlanCoreChannelRequest] = []
        self.executions: list[tuple[CoreChannelPlan, bool]] = []

    def plan(self, request: PlanCoreChannelRequest) -> CoreChannelPlan:
        self.requests.append(request)
        identity = CoreReleaseIdentity(
            version="1.13.14",
            architecture=request.architecture,
            source_sha256="a" * 64,
        )
        return CoreChannelPlan(
            kind=CoreChannelPlanKind.ALREADY_CURRENT,
            channel=request.channel,
            version="1.13.14",
            architecture=request.architecture,
            prerelease=False,
            requires_confirmation=False,
            target=identity,
            expected_active=identity,
            exact_update=None,
            expected_state_revision=3,
        )

    def execute(self, plan: CoreChannelPlan, *, confirmed: bool) -> CoreUpdateResult:
        self.executions.append((plan, confirmed))
        raise AssertionError("an already-current channel must not execute")


class RetainedPreviewChannels(AlreadyCurrentChannels):
    def plan(self, request: PlanCoreChannelRequest) -> CoreChannelPlan:
        self.requests.append(request)
        return CoreChannelPlan(
            kind=CoreChannelPlanKind.SWITCH_RETAINED,
            channel=request.channel,
            version="1.14.0-alpha.46",
            architecture=request.architecture,
            prerelease=True,
            requires_confirmation=True,
            target=CoreReleaseIdentity(
                version="1.14.0-alpha.46",
                architecture=request.architecture,
                source_sha256="b" * 64,
            ),
            expected_active=CoreReleaseIdentity(
                version="1.13.14",
                architecture=request.architecture,
                source_sha256="a" * 64,
            ),
            exact_update=None,
            expected_state_revision=3,
        )

    def execute(self, plan: CoreChannelPlan, *, confirmed: bool) -> CoreUpdateResult:
        self.executions.append((plan, confirmed))
        return CoreUpdateResult(
            activation=CoreActivation(
                version=plan.version,
                distribution_directory=Path("/opt/sing-box-manager/core/versions/preview"),
                binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
                activated_target="versions/preview",
                previous_target="versions/stable",
            )
        )


class MissingPreviewChannels(RetainedPreviewChannels):
    def plan(self, request: PlanCoreChannelRequest) -> CoreChannelPlan:
        self.requests.append(request)
        return CoreChannelPlan(
            kind=CoreChannelPlanKind.ACQUIRE_AND_ACTIVATE,
            channel=request.channel,
            version="1.14.0-alpha.46",
            architecture=request.architecture,
            prerelease=True,
            requires_confirmation=True,
            target=None,
            expected_active=CoreReleaseIdentity(
                version="1.13.14",
                architecture=request.architecture,
                source_sha256="a" * 64,
            ),
            exact_update=CoreUpdatePlan(
                artifact=PlannedCoreArtifact(
                    version="1.14.0-alpha.46",
                    architecture=request.architecture,
                    asset_name="sing-box-1.14.0-alpha.46-linux-amd64.tar.gz",
                    download_url=(
                        "https://github.com/SagerNet/sing-box/releases/download/"
                        "v1.14.0-alpha.46/sing-box-1.14.0-alpha.46-linux-amd64.tar.gz"
                    ),
                    sha256="b" * 64,
                    trust_mode=CoreArtifactTrustMode.IMMUTABLE_RELEASE,
                    release_immutable=True,
                    prerelease=True,
                ),
                mutates_host=False,
                warnings=(CoreUpdateWarning.PRERELEASE_COMPATIBILITY_RISK,),
                expected_state_revision=3,
            ),
            expected_state_revision=3,
        )

    def execute(self, plan: CoreChannelPlan, *, confirmed: bool) -> CoreUpdateResult:
        self.executions.append((plan, confirmed))
        return CoreUpdateResult(
            activation=CoreActivation(
                version=plan.version,
                distribution_directory=Path("/opt/sing-box-manager/core/versions/preview"),
                binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
                activated_target="versions/preview",
                previous_target="versions/stable",
            )
        )


class MissingStableChannels(MissingPreviewChannels):
    def plan(self, request: PlanCoreChannelRequest) -> CoreChannelPlan:
        self.requests.append(request)
        return CoreChannelPlan(
            kind=CoreChannelPlanKind.ACQUIRE_AND_ACTIVATE,
            channel=CoreReleaseChannel.STABLE,
            version="1.13.14",
            architecture=request.architecture,
            prerelease=False,
            requires_confirmation=True,
            target=None,
            expected_active=None,
            exact_update=CoreUpdatePlan(
                artifact=PlannedCoreArtifact(
                    version="1.13.14",
                    architecture=request.architecture,
                    asset_name="sing-box-1.13.14-linux-amd64.tar.gz",
                    download_url=(
                        "https://github.com/SagerNet/sing-box/releases/download/"
                        "v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz"
                    ),
                    sha256="f" * 64,
                    trust_mode=CoreArtifactTrustMode.DIGEST_PINNED_STABLE,
                    release_immutable=False,
                    prerelease=False,
                ),
                mutates_host=False,
                warnings=(CoreUpdateWarning.DIGEST_PINNED_MUTABLE_RELEASE,),
                expected_state_revision=3,
            ),
            expected_state_revision=3,
        )


class UnexpectedRetainedPreviewChannels(RetainedPreviewChannels):
    def execute(self, plan: CoreChannelPlan, *, confirmed: bool) -> CoreUpdateResult:
        self.executions.append((plan, confirmed))
        raise RuntimeError("token=private-core-channel-switch-error")


class BlockingPlanningChannels(AlreadyCurrentChannels):
    def __init__(self) -> None:
        super().__init__()
        self.planning_started = Event()
        self.release_planning = Event()
        self.planning_returned = Event()

    def plan(self, request: PlanCoreChannelRequest) -> CoreChannelPlan:
        self.planning_started.set()
        if not self.release_planning.wait(timeout=2):
            raise RuntimeError("planning test release timed out")
        plan = super().plan(request)
        self.planning_returned.set()
        return plan


class FailsOncePlanningChannels(AlreadyCurrentChannels):
    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    def plan(self, request: PlanCoreChannelRequest) -> CoreChannelPlan:
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("token=private-core-channel-planning-error")
        return super().plan(request)


class JourneyCoreSource:
    def __init__(self) -> None:
        self.release_channels: list[CoreReleaseChannel] = []
        self.inspect_requests: list[CoreArtifactRequest] = []
        self.acquire_calls: list[tuple[PlannedCoreArtifact, Path]] = []

    def latest(self, channel: CoreReleaseChannel) -> CoreRelease:
        self.release_channels.append(channel)
        return CoreRelease(
            channel=CoreReleaseChannel.STABLE,
            version="1.13.14",
            prerelease=False,
        )

    def inspect(self, request: CoreArtifactRequest) -> PlannedCoreArtifact:
        self.inspect_requests.append(request)
        asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
        return PlannedCoreArtifact(
            version=request.version,
            architecture=request.architecture,
            asset_name=asset_name,
            download_url=f"https://example.invalid/{asset_name}",
            sha256="a" * 64,
            trust_mode=CoreArtifactTrustMode.DIGEST_PINNED_STABLE,
            release_immutable=False,
            prerelease=False,
        )

    def acquire(
        self,
        artifact: PlannedCoreArtifact,
        *,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact:
        self.acquire_calls.append((artifact, destination_directory))
        raise AssertionError("an incompatible channel review must not acquire an artifact")


class JourneyCoreInventory:
    def list_installed(self) -> tuple[InstalledCoreRelease, ...]:
        return (
            InstalledCoreRelease(
                version="1.14.0-alpha.47",
                architecture=ArtifactArchitecture.AMD64,
                source_sha256="b" * 64,
                distribution_directory=Path("/opt/sing-box-manager/core/versions/preview"),
                target="versions/preview",
                active=True,
            ),
            InstalledCoreRelease(
                version="1.13.14",
                architecture=ArtifactArchitecture.AMD64,
                source_sha256="a" * 64,
                distribution_directory=Path("/opt/sing-box-manager/core/versions/stable"),
                target="versions/stable",
                active=False,
            ),
        )


class JourneyCoreController:
    def __init__(self) -> None:
        self.activations: list[CoreActivationRequest] = []
        self.switches: list[CoreSwitchRequest] = []

    def activate_core(self, request: CoreActivationRequest) -> CoreActivation:
        self.activations.append(request)
        raise AssertionError("an incompatible channel review must not activate a core")

    def switch_core(self, request: CoreSwitchRequest) -> CoreActivation:
        self.switches.append(request)
        raise AssertionError("an incompatible channel review must not switch cores")


def installation_with_active_snell() -> ManagedInstallation:
    return ManagedInstallation(
        schema_version=1,
        revision=7,
        profiles=(
            ManagedProfile(
                profile_id="profile-7",
                profile_name="private-snell",
                protocol=ProtocolKind.SNELL_V6,
                listen_port=8388,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                enabled=True,
            ),
        ),
    )


async def wait_for_thread_event(event: Event, *, timeout: float = 1) -> None:
    assert await asyncio.to_thread(event.wait, timeout)


async def open_channel_selection(app: ManagerApp, pilot: Pilot[None]) -> CoreChannelSelectionScreen:
    await pilot.click("#open-operations")
    await pilot.click("#manage-core-channels")
    assert isinstance(app.screen, CoreChannelSelectionScreen)
    return app.screen


async def test_applied_snell_rejects_retained_stable_before_acquire_or_switch(
    tmp_path: Path,
) -> None:
    state_store = MemoryStateStore(installation_with_active_snell())
    compatibility = ProtocolCompatibilityPolicy()
    source = JourneyCoreSource()
    controller = JourneyCoreController()
    updater = CoreUpdateService(
        artifact_source=source,
        core_activator=controller,
        incoming_directory=tmp_path / "incoming",
        state_store=state_store,
        compatibility=compatibility,
    )
    channels = CoreChannelService(
        release_source=source,
        core_inventory=JourneyCoreInventory(),
        core_updater=updater,
        core_switcher=controller,
        state_store=state_store,
        compatibility=compatibility,
    )
    app = ManagerApp(core_updater=updater, core_channel_manager=channels)

    async with app.run_test() as pilot:
        await open_channel_selection(app, pilot)
        await pilot.click("#inspect-stable-channel")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.screen.query_one("#core-channel-planning-error")
        assert not app.screen.query("#core-channel-plan")

    assert source.release_channels == [CoreReleaseChannel.STABLE]
    assert source.inspect_requests == []
    assert source.acquire_calls == []
    assert controller.activations == []
    assert controller.switches == []


async def test_operator_sees_stable_already_current_without_a_confirmation_action() -> None:
    channels = AlreadyCurrentChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")

        assert str(app.screen.query_one("#manage-core-channels", Button).label) == (
            "管理 Stable / Preview 通道"
        )

        await pilot.click("#manage-core-channels")
        await pilot.click("#inspect-stable-channel")
        await pilot.pause()

        assert app.screen.query_one("#core-channel-current-title", Static).content == (
            "Stable 已是当前版本"
        )
        assert app.screen.query_one("#core-channel-current-version", Static).content == (
            "精确版本：1.13.14"
        )
        assert len(app.screen.query("#confirm-core-channel")) == 0
        assert channels.requests == [
            PlanCoreChannelRequest(
                channel=CoreReleaseChannel.STABLE,
                architecture=ArtifactArchitecture.AMD64,
            )
        ]
        assert channels.executions == []


async def test_operator_confirms_an_offline_switch_to_retained_preview() -> None:
    channels = RetainedPreviewChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")
        await pilot.click("#manage-core-channels")
        await pilot.click("#inspect-preview-channel")
        await pilot.pause()

        assert app.screen.query_one("#core-channel-plan-title", Static).content == (
            "确认 Preview 通道操作"
        )
        assert app.screen.query_one("#core-channel-plan-version", Static).content == (
            "版本：1.14.0-alpha.46"
        )
        assert app.screen.query_one("#core-channel-plan-action", Static).content == (
            "操作：切换到已安装版本 (无需下载)"
        )
        assert app.screen.query_one("#core-channel-plan-target-sha256", Static).content == (
            f"目标制品 SHA-256：{'b' * 64}"
        )
        assert app.screen.query_one("#core-channel-plan-active-sha256", Static).content == (
            f"当前制品 SHA-256：{'a' * 64}"
        )
        assert app.screen.query_one("#core-channel-plan-prerelease-warning", Static).content == (
            "这是预发布核心; 仅在接受兼容性风险时继续。"
        )
        assert app.screen.query_one("#core-channel-plan-safety", Static).content == (
            "当前仅预览; 确认后 helper 只切换已验证的 retained release，不访问网络。"
        )
        assert len(app.screen.query("#core-channel-plan-asset")) == 0
        assert len(app.screen.query("#core-channel-plan-sha256")) == 0
        assert len(app.screen.query("#core-channel-plan-trust")) == 0
        assert len(app.screen.query("#core-channel-warning-0")) == 0
        assert str(app.screen.query_one("#confirm-core-channel", Button).label) == ("确认离线切换")

        await pilot.click("#confirm-core-channel")
        await pilot.pause()

        assert app.screen.query_one("#core-update-result-title", Static).content == (
            "sing-box 核心已激活"
        )
        assert len(channels.executions) == 1
        executed_plan, confirmed = channels.executions[0]
        assert executed_plan.kind is CoreChannelPlanKind.SWITCH_RETAINED
        assert confirmed is True


async def test_operator_confirms_acquisition_for_a_missing_preview_release() -> None:
    channels = MissingPreviewChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")
        await pilot.click("#manage-core-channels")
        await pilot.click("#inspect-preview-channel")
        await pilot.pause()

        assert app.screen.query_one("#core-channel-plan-action", Static).content == (
            "操作：下载、校验并激活精确版本"
        )
        assert app.screen.query_one("#core-channel-plan-asset", Static).content == (
            "发行资产：sing-box-1.14.0-alpha.46-linux-amd64.tar.gz"
        )
        assert app.screen.query_one("#core-channel-plan-sha256", Static).content == (
            f"制品 SHA-256：{'b' * 64}"
        )
        assert app.screen.query_one("#core-channel-plan-trust", Static).content == (
            "信任方式：上游 immutable release"
        )
        assert app.screen.query_one("#core-channel-warning-0", Static).content == (
            "这是预发布核心; 仅在接受兼容性风险时继续。"
        )
        assert len(app.screen.query("#core-channel-plan-prerelease-warning")) == 0
        assert str(app.screen.query_one("#confirm-core-channel", Button).label) == (
            "确认下载并激活"
        )
        assert channels.executions == []

        await pilot.click("#confirm-core-channel")
        await pilot.pause()

        assert app.screen.query_one("#core-update-result-version", Static).content == (
            "版本：1.14.0-alpha.46"
        )
        assert len(channels.executions) == 1
        assert channels.executions[0][0].kind is CoreChannelPlanKind.ACQUIRE_AND_ACTIVATE
        assert channels.executions[0][1] is True


async def test_operator_reviews_digest_pinned_stable_acquisition_before_confirming() -> None:
    channels = MissingStableChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")
        await pilot.click("#manage-core-channels")
        await pilot.click("#inspect-stable-channel")
        await pilot.pause()

        assert app.screen.query_one("#core-channel-plan-asset", Static).content == (
            "发行资产：sing-box-1.13.14-linux-amd64.tar.gz"
        )
        assert app.screen.query_one("#core-channel-plan-sha256", Static).content == (
            f"制品 SHA-256：{'f' * 64}"
        )
        assert app.screen.query_one("#core-channel-plan-trust", Static).content == (
            "信任方式：Stable 摘要冻结"
        )
        assert app.screen.query_one("#core-channel-warning-0", Static).content == (
            "上游 Stable release 可变；本次操作只接受上方已冻结的 SHA-256。"  # noqa: RUF001
        )
        assert str(app.screen.query_one("#confirm-core-channel", Button).label) == (
            "确认下载并激活"
        )
        assert channels.executions == []


async def test_unexpected_retained_switch_result_is_unknown_and_not_disclosed() -> None:
    channels = UnexpectedRetainedPreviewChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")
        await pilot.click("#manage-core-channels")
        await pilot.click("#inspect-preview-channel")
        await pilot.pause()
        await pilot.click("#confirm-core-channel")
        await pilot.pause()

        assert app.screen.query_one("#core-update-error-title", Static).content == (
            "无法确认核心激活结果"
        )
        assert app.screen.query_one("#core-update-error-details", Static).content == (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert "检查 current 链接" in str(
            app.screen.query_one("#core-update-error-safety", Static).content
        )
        assert len(app.screen.query("#confirm-core-channel")) == 0
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-core-channel-switch-error" not in rendered_text


async def test_leaving_channel_selection_discards_stale_planning_completion() -> None:
    channels = BlockingPlanningChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        await open_channel_selection(app, pilot)
        await pilot.click("#inspect-stable-channel")
        await wait_for_thread_event(channels.planning_started)

        await pilot.press("escape")
        channels.release_planning.set()
        await wait_for_thread_event(channels.planning_returned)
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert not app.screen.query("#core-channel-current")
        assert not app.screen.query("#core-channel-plan")
        assert not app.screen.query("#core-channel-planning-error")


async def test_channel_planning_completion_waits_for_help_and_is_consumed_once() -> None:
    channels = BlockingPlanningChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        await open_channel_selection(app, pilot)
        await pilot.click("#inspect-stable-channel")
        await wait_for_thread_event(channels.planning_started)

        await pilot.press("f1")
        channels.release_planning.set()
        await wait_for_thread_event(channels.planning_returned)
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.screen.query_one("#keyboard-help")
        assert not app.screen.query("#core-channel-current")

        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.query_one("#core-channel-current")

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, CoreChannelSelectionScreen)
        assert not app.screen.query_one("#inspect-stable-channel", Button).disabled
        assert not app.screen.query_one("#inspect-preview-channel", Button).disabled

        await pilot.pause()
        assert isinstance(app.screen, CoreChannelSelectionScreen)


async def test_channel_plan_return_restores_controls_and_allows_another_plan() -> None:
    channels = AlreadyCurrentChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        await open_channel_selection(app, pilot)
        await pilot.click("#inspect-stable-channel")
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("escape")

        assert isinstance(app.screen, CoreChannelSelectionScreen)
        assert not app.screen.query_one("#inspect-stable-channel", Button).disabled
        assert not app.screen.query_one("#inspect-preview-channel", Button).disabled

        await pilot.click("#inspect-preview-channel")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.screen.query_one("#core-channel-current-title", Static).content == (
            "Preview 已是当前版本"
        )
        assert [request.channel for request in channels.requests] == [
            CoreReleaseChannel.STABLE,
            CoreReleaseChannel.PREVIEW,
        ]


async def test_channel_planning_error_return_restores_controls_and_allows_retry() -> None:
    channels = FailsOncePlanningChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        await open_channel_selection(app, pilot)
        await pilot.click("#inspect-stable-channel")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.screen.query_one("#core-channel-planning-error")
        await pilot.press("escape")

        assert isinstance(app.screen, CoreChannelSelectionScreen)
        assert not app.screen.query_one("#inspect-stable-channel", Button).disabled
        assert not app.screen.query_one("#inspect-preview-channel", Button).disabled

        await pilot.click("#inspect-stable-channel")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.screen.query_one("#core-channel-current")
        assert channels.attempts == EXPECTED_PLANNING_ATTEMPTS


async def test_superseded_channel_planning_result_cannot_open_an_obsolete_plan() -> None:
    channels = AlreadyCurrentChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        selection = await open_channel_selection(app, pilot)
        obsolete_plan = channels.plan(
            PlanCoreChannelRequest(
                channel=CoreReleaseChannel.STABLE,
                architecture=ArtifactArchitecture.AMD64,
            )
        )
        selection._planning_generation = 2

        selection._show_plan(1, obsolete_plan)
        await pilot.pause()

        assert app.screen is selection
        assert not app.screen.query("#core-channel-current")
