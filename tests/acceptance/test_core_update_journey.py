import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from typing import cast

from textual.pilot import Pilot
from textual.widgets import Button, Footer, Input, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.core_update import (
    CorePrereleaseConsentRequiredError,
    CoreUpdatePlan,
    CoreUpdateResult,
    CoreUpdateService,
    CoreUpdateWarning,
    PlanCoreUpdateRequest,
)
from sb_manager.application.protocol_compatibility import (
    CoreTargetIncompatibleWithDesiredState,
    ProtocolCompatibilityPolicy,
)
from sb_manager.artifacts.installation import CoreActivation
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
    PlannedCoreArtifact,
    VerifiedCoreArtifact,
)
from sb_manager.seams.core_activator import CoreActivationError, CoreActivationRequest
from sb_manager.ui.app import ManagerApp, ManagerAppInterfaceTools
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.core_artifact_copy import TRUST_COPY, WARNING_COPY

VERSION = "1.14.0-alpha.45"
STABLE_VERSION = "1.13.14"
PREVIEW_SHA256 = "a" * 64
STABLE_SHA256 = "b" * 64


class SentinelCompatibilityPolicy(ProtocolCompatibilityPolicy):
    def require_profiles_supported(
        self,
        profiles: object,
        *,
        target_version: str,
    ) -> None:
        error = CoreTargetIncompatibleWithDesiredState(
            target_version=target_version,
            blocking_profile_ids=("private-id-sentinel",),
            blocking_profile_names=("Surge 手机",),
        )
        error.args = ("raw-exception-sentinel material-sentinel inbound-json-sentinel",)
        raise error


class CoreUpdateMarkerCatalog:
    """Render markers across the complete core-update journey."""

    def text(self, key: UiText, /, **values: object) -> str:
        markers = {
            "common.cancel": "目录取消确认",
            "core_update.open": "目录打开核心更新",
            "core_update.form.title": "目录核心更新",
            "core_update.form.guidance": "目录核心更新说明",
            "core_update.form.version_placeholder": "目录精确版本",
            "core_update.form.preview": "目录预览计划",
            "core_update.form.planning": "目录正在冻结制品摘要",
            "core_update.form.error.invalid_version": "目录版本格式错误",
            "core_update.form.error.prerelease_consent": "目录预发布确认",
            "core_update.plan.title": "目录核心计划",
            "core_update.plan.sha256": f"目录 SHA-256 {values.get('sha256', '')}",
            "core_update.plan.trust": f"目录信任方式 {values.get('trust', '')}",
            "core_update.trust.immutable": "目录 immutable 信任",
            "core_update.trust.digest_pinned": "目录 Stable 摘要信任",
            "core_update.plan.warning.prerelease": "目录预发布风险",
            "core_update.plan.warning.mutable_release": "目录 Stable 可变警告",
            "core_update.plan.safety": "目录计划安全说明",
            "core_update.plan.confirm": "目录确认激活",
            "core_update.result.title": "目录激活成功",
            "core_update.planning_error.title": "目录计划错误",
            "core_update.planning_error.details": "目录计划错误详情",
            "core_update.planning_error.safety": "目录计划错误安全说明",
            "core_update.error.unknown.title": "目录结果未知",
            "core_update.error.unknown.safety": "目录未知安全说明",
        }
        if marker := markers.get(key.value):
            return marker
        if key.value == "core_update.result.version":
            return f"目录版本 {values['version']}"
        if key.value == "core_update.result.previous":
            return f"目录上一个目标 {values['target']}"
        return SIMPLIFIED_CHINESE.text(key, **values)


class RecordingCoreUpdater:
    def __init__(self) -> None:
        self.plan_requests: list[PlanCoreUpdateRequest] = []
        self.executions: list[tuple[CoreUpdatePlan, bool]] = []

    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        self.plan_requests.append(request)
        asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
        prerelease = "-" in request.version.partition("+")[0]
        return CoreUpdatePlan(
            artifact=PlannedCoreArtifact(
                version=request.version,
                architecture=request.architecture,
                asset_name=asset_name,
                download_url=(
                    "https://github.com/SagerNet/sing-box/releases/download/"
                    f"v{request.version}/{asset_name}"
                ),
                sha256=PREVIEW_SHA256 if prerelease else STABLE_SHA256,
                trust_mode=(
                    CoreArtifactTrustMode.IMMUTABLE_RELEASE
                    if prerelease
                    else CoreArtifactTrustMode.DIGEST_PINNED_STABLE
                ),
                release_immutable=prerelease,
                prerelease=prerelease,
            ),
            mutates_host=False,
            warnings=(
                (CoreUpdateWarning.PRERELEASE_COMPATIBILITY_RISK,)
                if prerelease
                else (CoreUpdateWarning.DIGEST_PINNED_MUTABLE_RELEASE,)
            ),
            expected_state_revision=3,
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


class UnexpectedPlanningCoreUpdater(RecordingCoreUpdater):
    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        raise RuntimeError("token=private-core-update-planning-error")


class InvalidVersionCoreUpdater(RecordingCoreUpdater):
    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        raise ValueError("Invalid artifact version: token=private-version-input")


class PrereleaseConsentCoreUpdater(RecordingCoreUpdater):
    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        raise CorePrereleaseConsentRequiredError("private prerelease diagnostics")


class BlockingPlanningCoreUpdater(RecordingCoreUpdater):
    def __init__(self) -> None:
        super().__init__()
        self.planning_started = Event()
        self.release_planning = Event()
        self.planning_returned = Event()

    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        self.planning_started.set()
        if not self.release_planning.wait(timeout=2):
            raise RuntimeError("planning test release timed out")
        plan = super().plan(request)
        self.planning_returned.set()
        return plan


class JourneyArtifactSource:
    def __init__(self) -> None:
        self.inspect_requests: list[CoreArtifactRequest] = []
        self.acquire_calls: list[tuple[PlannedCoreArtifact, Path]] = []

    def inspect(self, request: CoreArtifactRequest) -> PlannedCoreArtifact:
        self.inspect_requests.append(request)
        asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
        return PlannedCoreArtifact(
            version=request.version,
            architecture=request.architecture,
            asset_name=asset_name,
            download_url=f"https://example.invalid/{asset_name}",
            sha256=STABLE_SHA256,
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
        raise AssertionError("an incompatible review must not acquire an artifact")


class JourneyApplyLock:
    @contextmanager
    def acquire(self) -> Iterator[None]:
        yield


class JourneyCoreActivator:
    def __init__(self) -> None:
        self.requests: list[CoreActivationRequest] = []

    def activate_core(self, request: CoreActivationRequest) -> CoreActivation:
        self.requests.append(request)
        raise AssertionError("an incompatible review must not activate a core")


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


async def open_core_form(pilot: Pilot[None]) -> None:
    await pilot.click("#open-operations")
    await pilot.click("#manage-core")


def test_core_artifact_copy_mappings_are_exhaustive() -> None:
    assert set(WARNING_COPY) == set(CoreUpdateWarning)
    assert set(TRUST_COPY) == set(CoreArtifactTrustMode)


async def test_applied_snell_rejects_stable_review_before_artifact_acquisition(
    tmp_path: Path,
) -> None:
    artifacts = JourneyArtifactSource()
    activator = JourneyCoreActivator()
    updater = CoreUpdateService(
        artifact_source=artifacts,
        core_activator=activator,
        incoming_directory=tmp_path / "incoming",
        state_store=MemoryStateStore(installation_with_active_snell()),
        compatibility=SentinelCompatibilityPolicy(),
        apply_lock=JourneyApplyLock(),
    )
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*STABLE_VERSION)
        await pilot.click("#preview-core-update")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.screen.query_one("#core-target-compatibility")
        assert app.screen.query_one("#core-target-version", Static).content == (
            f"目标核心：{STABLE_VERSION}"
        )
        assert app.screen.query_one("#core-target-blockers", Static).content == (
            "阻止切换的配置：Surge 手机"
        )
        rendered = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-id-sentinel" not in rendered
        assert "raw-exception-sentinel" not in rendered
        assert "material-sentinel" not in rendered
        assert "inbound-json-sentinel" not in rendered
        assert not app.screen.query("#core-update-plan")

    assert artifacts.inspect_requests == []
    assert artifacts.acquire_calls == []
    assert activator.requests == []


async def open_core_plan(
    app: ManagerApp,
    updater: RecordingCoreUpdater,
    pilot: Pilot[None],
) -> None:
    await open_core_form(pilot)
    await pilot.click("#core-version")
    await pilot.press(*VERSION)
    await pilot.click("#allow-prerelease")
    await pilot.click("#preview-core-update")
    await pilot.pause()
    assert updater.plan_requests == [
        PlanCoreUpdateRequest(
            version=VERSION,
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        )
    ]


async def test_core_update_copy_catalog_flows_to_form() -> None:
    app = ManagerApp(
        core_updater=RecordingCoreUpdater(),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, CoreUpdateMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")
        assert str(app.screen.query_one("#manage-core", Button).label) == ("目录打开核心更新")
        await pilot.click("#manage-core")

        assert app.screen.query_one("#core-update-form-title", Static).content == ("目录核心更新")
        assert app.screen.query_one("#core-update-form-guidance", Static).content == (
            "目录核心更新说明"
        )
        assert app.screen.query_one("#core-version", Input).placeholder == "目录精确版本"
        assert str(app.screen.query_one("#preview-core-update", Button).label) == ("目录预览计划")


async def test_invalid_core_version_uses_safe_catalog_guidance() -> None:
    app = ManagerApp(
        core_updater=InvalidVersionCoreUpdater(),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, CoreUpdateMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*"latest")
        await pilot.click("#preview-core-update")
        await pilot.pause()

        assert app.screen.query_one("#core-update-form-error", Static).content == (
            "目录版本格式错误"
        )


async def test_prerelease_requires_catalog_rendered_explicit_consent() -> None:
    app = ManagerApp(
        core_updater=PrereleaseConsentCoreUpdater(),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, CoreUpdateMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*VERSION)
        await pilot.click("#preview-core-update")
        await pilot.pause()

        assert app.screen.query_one("#core-update-form-error", Static).content == ("目录预发布确认")


async def test_core_update_copy_catalog_renders_semantic_plan_warning() -> None:
    updater = RecordingCoreUpdater()
    app = ManagerApp(
        core_updater=updater,
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, CoreUpdateMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await open_core_plan(app, updater, pilot)

        assert app.screen.query_one("#core-update-plan-title", Static).content == ("目录核心计划")
        assert app.screen.query_one("#core-update-plan-sha256", Static).content == (
            f"目录 SHA-256 {PREVIEW_SHA256}"
        )
        assert app.screen.query_one("#core-update-plan-trust", Static).content == (
            "目录信任方式 目录 immutable 信任"
        )
        assert app.screen.query_one("#core-update-warning-0", Static).content == ("目录预发布风险")
        assert app.screen.query_one("#core-update-plan-safety", Static).content == (
            "目录计划安全说明"
        )
        assert str(app.screen.query_one("#confirm-core-update", Button).label) == ("目录确认激活")


async def test_core_update_cancel_binding_comes_from_the_interface_catalog() -> None:
    updater = RecordingCoreUpdater()
    app = ManagerApp(
        core_updater=updater,
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, CoreUpdateMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await open_core_plan(app, updater, pilot)

        footer = app.screen.query_one(Footer)
        rendered_footer = " ".join(str(widget.render()) for widget in footer.query("*"))
        assert "目录取消确认" in rendered_footer

        await pilot.press("escape")
        assert app.screen.query_one("#core-version", Input).value == VERSION


async def test_operator_can_preview_an_exact_core_update_without_mutation() -> None:
    updater = RecordingCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")
        assert str(app.screen.query_one("#manage-core", Button).label) == (
            "安装或升级 sing-box 核心"
        )
        await pilot.click("#manage-core")
        assert app.screen.query_one("#core-update-form-title", Static).content == (
            "安装或升级 sing-box 核心"
        )
        assert app.screen.query_one("#core-update-form-guidance", Static).content == (
            "只接受官方精确版本；Stable 优先使用 immutable release，上游可变时会冻结 "  # noqa: RUF001
            "SHA-256 供审阅；Preview 只接受 immutable release。"  # noqa: RUF001
        )
        assert app.screen.query_one("#core-version", Input).placeholder == (
            "精确版本，例如 1.14.0-alpha.45"
        )
        await pilot.click("#core-version")
        await pilot.press(*VERSION)
        await pilot.click("#allow-prerelease")
        await pilot.click("#preview-core-update")
        await pilot.pause()

        assert updater.plan_requests[0].architecture is ArtifactArchitecture.AMD64
        assert app.screen.query_one("#core-update-plan-title", Static).content == (
            "确认核心更新计划"
        )
        assert app.screen.query_one("#core-update-plan-safety", Static).content == (
            "当前仅预览; 尚未下载文件，也不会修改服务器。"
        )
        assert app.screen.query_one("#core-update-plan-sha256", Static).content == (
            f"制品 SHA-256：{PREVIEW_SHA256}"
        )
        assert app.screen.query_one("#core-update-plan-trust", Static).content == (
            "信任方式：上游 immutable release"
        )
        assert app.screen.query_one("#core-update-warning-0", Static).content == (
            "这是预发布核心; 仅在接受兼容性风险时继续。"
        )


async def test_exact_version_planning_is_non_blocking_and_shows_full_digest() -> None:
    updater = BlockingPlanningCoreUpdater()
    app = ManagerApp(
        core_updater=updater,
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, CoreUpdateMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*VERSION)
        await pilot.click("#allow-prerelease")
        await pilot.click("#preview-core-update")
        await pilot.pause()

        await wait_for_thread_event(updater.planning_started)
        assert app.screen.query_one("#preview-core-update", Button).disabled
        assert app.screen.query_one("#core-update-form-error", Static).content == (
            "目录正在冻结制品摘要"
        )

        updater.release_planning.set()
        await wait_for_thread_event(updater.planning_returned)
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.screen.query_one("#core-update-plan-sha256", Static).content == (
            f"目录 SHA-256 {PREVIEW_SHA256}"
        )


async def test_leaving_exact_version_form_discards_stale_planning_completion() -> None:
    updater = BlockingPlanningCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*VERSION)
        await pilot.click("#allow-prerelease")
        await pilot.click("#preview-core-update")
        await pilot.pause()
        await wait_for_thread_event(updater.planning_started)

        await pilot.press("escape")
        updater.release_planning.set()
        await wait_for_thread_event(updater.planning_returned)
        await pilot.pause()

        assert not app.screen.query("#core-update-plan")


async def test_planning_completion_waits_for_keyboard_help_to_close() -> None:
    updater = BlockingPlanningCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*VERSION)
        await pilot.click("#allow-prerelease")
        await pilot.click("#preview-core-update")
        await wait_for_thread_event(updater.planning_started)

        await pilot.press("f1")
        assert app.screen.query_one("#keyboard-help")

        updater.release_planning.set()
        await wait_for_thread_event(updater.planning_returned)
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.screen.query_one("#keyboard-help")
        assert not app.screen.query("#core-update-plan")

        await pilot.press("escape")
        await pilot.pause()

        assert app.screen.query_one("#core-update-plan-sha256", Static).content == (
            f"制品 SHA-256：{PREVIEW_SHA256}"
        )


async def test_stable_review_shows_frozen_digest_trust_and_mutability_warning() -> None:
    updater = RecordingCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*STABLE_VERSION)
        await pilot.click("#preview-core-update")
        await pilot.pause()

        assert app.screen.query_one("#core-update-plan-sha256", Static).content == (
            f"制品 SHA-256：{STABLE_SHA256}"
        )
        assert app.screen.query_one("#core-update-plan-trust", Static).content == (
            "信任方式：Stable 摘要冻结"
        )
        assert app.screen.query_one("#core-update-warning-0", Static).content == (
            "上游 Stable release 可变；本次操作只接受上方已冻结的 SHA-256。"  # noqa: RUF001
        )
        assert updater.executions == []

        await pilot.click("#confirm-core-update")
        await pilot.pause()

        assert updater.executions[0][1] is True


async def test_unexpected_core_update_planning_failure_is_safe_and_not_disclosed() -> None:
    app = ManagerApp(
        core_updater=UnexpectedPlanningCoreUpdater(),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, CoreUpdateMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*VERSION)
        await pilot.click("#allow-prerelease")
        await pilot.click("#preview-core-update")
        await pilot.pause()

        assert app.screen.query_one("#core-update-planning-error-title", Static).content == (
            "目录计划错误"
        )
        assert app.screen.query_one("#core-update-planning-error-details", Static).content == (
            "目录计划错误详情"
        )
        assert app.screen.query_one("#core-update-planning-error-safety", Static).content == (
            "目录计划错误安全说明"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-core-update-planning-error" not in rendered_text


async def test_confirmed_core_update_runs_and_shows_activation_evidence() -> None:
    updater = RecordingCoreUpdater()
    app = ManagerApp(
        core_updater=updater,
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, CoreUpdateMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await open_core_plan(app, updater, pilot)
        await pilot.click("#confirm-core-update")
        await pilot.pause(0.1)

        assert updater.executions[0][1] is True
        assert app.screen.query_one("#core-update-result-title", Static).content == ("目录激活成功")
        assert app.screen.query_one("#core-update-result-version", Static).content == (
            f"目录版本 {VERSION}"
        )
        assert app.screen.query_one("#core-update-result-previous", Static).content == (
            "目录上一个目标 versions/1.14.0-alpha.44-release"
        )


async def test_unknown_privileged_activation_result_is_not_reported_as_safe() -> None:
    updater = FailingCoreUpdater()
    app = ManagerApp(
        core_updater=updater,
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, CoreUpdateMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await open_core_plan(app, updater, pilot)
        await pilot.click("#confirm-core-update")
        await pilot.pause(0.1)

        assert app.screen.query_one("#core-update-error-title", Static).content == ("目录结果未知")
        assert app.screen.query_one("#core-update-error-details", Static).content == (
            "sudo authorization denied"
        )
        assert app.screen.query_one("#core-update-error-safety", Static).content == (
            "目录未知安全说明"
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
