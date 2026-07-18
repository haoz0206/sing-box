from pathlib import Path

from textual.widgets import Button, Static

from sb_manager.application.core_update import (
    CoreChannelPlan,
    CoreChannelPlanKind,
    CoreUpdatePlan,
    CoreUpdateResult,
    CoreUpdateWarning,
    PlanCoreChannelRequest,
    PlanCoreUpdateRequest,
)
from sb_manager.artifacts.installation import CoreActivation, CoreReleaseIdentity
from sb_manager.seams.artifact_source import ArtifactArchitecture, CoreReleaseChannel
from sb_manager.ui.app import ManagerApp


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
                version="1.14.0-alpha.46",
                architecture=request.architecture,
                allow_prerelease=True,
                asset_name="sing-box-1.14.0-alpha.46-linux-amd64.tar.gz",
                source="SagerNet/sing-box immutable GitHub release",
                mutates_host=False,
                warnings=(CoreUpdateWarning.PRERELEASE_COMPATIBILITY_RISK,),
            ),
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


class UnexpectedRetainedPreviewChannels(RetainedPreviewChannels):
    def execute(self, plan: CoreChannelPlan, *, confirmed: bool) -> CoreUpdateResult:
        self.executions.append((plan, confirmed))
        raise RuntimeError("token=private-core-channel-switch-error")


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
        assert app.screen.query_one("#core-channel-plan-prerelease-warning", Static).content == (
            "这是预发布核心; 仅在接受兼容性风险时继续。"
        )
        assert str(app.screen.query_one("#confirm-core-channel", Button).label) == (
            "确认下载并激活"
        )

        await pilot.click("#confirm-core-channel")
        await pilot.pause()

        assert app.screen.query_one("#core-update-result-version", Static).content == (
            "版本：1.14.0-alpha.46"
        )
        assert len(channels.executions) == 1
        assert channels.executions[0][0].kind is CoreChannelPlanKind.ACQUIRE_AND_ACTIVATE


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
