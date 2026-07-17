from pathlib import Path

from textual.pilot import Pilot
from textual.widgets import Button, Input, Static

from sb_manager.application.core_update import (
    CoreUpdatePlan,
    CoreUpdateResult,
    PlanCoreUpdateRequest,
)
from sb_manager.artifacts.installation import CoreActivation
from sb_manager.seams.artifact_source import ArtifactArchitecture
from sb_manager.seams.core_activator import CoreActivationError
from sb_manager.ui.app import ManagerApp

VERSION = "1.14.0-alpha.45"


class RecordingCoreUpdater:
    def __init__(self) -> None:
        self.plan_requests: list[PlanCoreUpdateRequest] = []
        self.executions: list[tuple[CoreUpdatePlan, bool]] = []

    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        self.plan_requests.append(request)
        return CoreUpdatePlan(
            version=request.version,
            architecture=request.architecture,
            allow_prerelease=request.allow_prerelease,
            asset_name=f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz",
            source="SagerNet/sing-box immutable GitHub release",
            mutates_host=False,
            warnings=("这是预发布核心; 仅在接受兼容性风险时继续。",),
        )

    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
        self.executions.append((plan, confirmed))
        return CoreUpdateResult(
            activation=CoreActivation(
                version=plan.version,
                distribution_directory=Path(
                    "/opt/sing-box-manager/core/versions/1.14.0-alpha.45-release"
                ),
                binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
                activated_target="versions/1.14.0-alpha.45-release",
                previous_target="versions/1.14.0-alpha.44-release",
            )
        )


class FailingCoreUpdater(RecordingCoreUpdater):
    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
        assert confirmed
        raise CoreActivationError("sudo authorization denied")


class UnexpectedCoreUpdater(RecordingCoreUpdater):
    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
        assert confirmed
        raise RuntimeError("token=private-core-update-worker-error")


async def open_core_plan(
    app: ManagerApp,
    updater: RecordingCoreUpdater,
    pilot: Pilot[None],
) -> None:
    await pilot.click("#manage-core")
    await pilot.click("#core-version")
    await pilot.press(*VERSION)
    await pilot.click("#allow-prerelease")
    await pilot.click("#preview-core-update")
    assert updater.plan_requests == [
        PlanCoreUpdateRequest(
            version=VERSION,
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        )
    ]


async def test_operator_can_preview_an_exact_core_update_without_mutation() -> None:
    updater = RecordingCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        assert str(app.screen.query_one("#manage-core", Button).label) == (
            "安装或升级 sing-box 核心"
        )
        await pilot.click("#manage-core")
        assert app.screen.query_one("#core-update-form-title", Static).content == (
            "安装或升级 sing-box 核心"
        )
        assert app.screen.query_one("#core-version", Input).placeholder == (
            "精确版本，例如 1.14.0-alpha.45"
        )
        await pilot.click("#core-version")
        await pilot.press(*VERSION)
        await pilot.click("#allow-prerelease")
        await pilot.click("#preview-core-update")

        assert updater.plan_requests[0].architecture is ArtifactArchitecture.AMD64
        assert app.screen.query_one("#core-update-plan-title", Static).content == (
            "确认核心更新计划"
        )
        assert app.screen.query_one("#core-update-plan-safety", Static).content == (
            "当前仅预览; 尚未下载文件，也不会修改服务器。"
        )


async def test_confirmed_core_update_runs_and_shows_activation_evidence() -> None:
    updater = RecordingCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await open_core_plan(app, updater, pilot)
        await pilot.click("#confirm-core-update")
        await pilot.pause(0.1)

        assert updater.executions[0][1] is True
        assert app.screen.query_one("#core-update-result-title", Static).content == (
            "sing-box 核心已激活"
        )
        assert app.screen.query_one("#core-update-result-version", Static).content == (
            f"版本：{VERSION}"
        )
        assert app.screen.query_one("#core-update-result-previous", Static).content == (
            "上一个激活目标：versions/1.14.0-alpha.44-release"
        )


async def test_unknown_privileged_activation_result_is_not_reported_as_safe() -> None:
    updater = FailingCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await open_core_plan(app, updater, pilot)
        await pilot.click("#confirm-core-update")
        await pilot.pause(0.1)

        assert app.screen.query_one("#core-update-error-title", Static).content == (
            "无法确认核心激活结果"
        )
        assert app.screen.query_one("#core-update-error-details", Static).content == (
            "sudo authorization denied"
        )
        assert "检查 current 链接" in str(
            app.screen.query_one("#core-update-error-safety", Static).content
        )


async def test_unexpected_core_update_failure_is_unknown_and_not_disclosed() -> None:
    updater = UnexpectedCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await open_core_plan(app, updater, pilot)
        await pilot.click("#confirm-core-update")
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
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-core-update-worker-error" not in rendered_text
