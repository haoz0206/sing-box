from sb_manager.application.host_readiness import (
    HostAccessMode,
    HostReadinessItemCode,
    HostReadinessService,
    ReadinessState,
)
from sb_manager.seams.config_target import (
    ConfigTargetInspectionError,
    LiveConfigObservation,
)
from sb_manager.seams.core_status import CoreStatusObservation

EXPECTED_ACTION_REQUIRED_ITEMS = 2


class StubConfigInspector:
    def __init__(
        self,
        observation: LiveConfigObservation | None = None,
        error: ConfigTargetInspectionError | None = None,
    ) -> None:
        self.observation = observation
        self.error = error
        self.calls = 0

    def inspect(self) -> LiveConfigObservation:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.observation is not None
        return self.observation


class StubCoreStatusInspector:
    def __init__(self, observation: CoreStatusObservation) -> None:
        self.observation = observation
        self.calls = 0

    def inspect(self) -> CoreStatusObservation:
        self.calls += 1
        return self.observation


def test_privileged_readiness_reports_one_helper_check_and_an_available_core() -> None:
    helper = StubConfigInspector(LiveConfigObservation(exists=False, sha256=None))
    core = StubCoreStatusInspector(
        CoreStatusObservation(
            available=True,
            version="1.14.0",
            diagnostics="sing-box version 1.14.0",
        )
    )
    readiness = HostReadinessService(
        access_mode=HostAccessMode.PRIVILEGED,
        config_inspector=helper,
        privileged_inspector=helper,
        core_inspector=core,
    )

    report = readiness.inspect()

    assert report.ready_for_apply is True
    assert report.recommended_action == "开始创建或应用配置"
    assert [(item.code, item.state) for item in report.items] == [
        (HostReadinessItemCode.PRIVILEGED_HELPER, ReadinessState.READY),
        (HostReadinessItemCode.CORE, ReadinessState.READY),
    ]
    assert report.items[1].summary == "sing-box 1.14.0 已可用"
    assert helper.calls == 1
    assert core.calls == 1


def test_privileged_readiness_prioritizes_policy_install_before_core_install() -> None:
    helper = StubConfigInspector(error=ConfigTargetInspectionError("sudo: helper not found"))
    core = StubCoreStatusInspector(
        CoreStatusObservation(
            available=False,
            version=None,
            diagnostics="sing-box executable not found",
        )
    )
    readiness = HostReadinessService(
        access_mode=HostAccessMode.PRIVILEGED,
        config_inspector=helper,
        privileged_inspector=helper,
        core_inspector=core,
    )

    report = readiness.inspect()

    assert report.ready_for_apply is False
    assert report.action_required_count == EXPECTED_ACTION_REQUIRED_ITEMS
    assert report.recommended_action == "安装最小权限策略"
    assert [(item.code, item.state) for item in report.items] == [
        (HostReadinessItemCode.PRIVILEGED_HELPER, ReadinessState.ACTION_REQUIRED),
        (HostReadinessItemCode.CORE, ReadinessState.ACTION_REQUIRED),
    ]
    assert "--authorization sudo 或 doas" in report.items[0].guidance
    assert "--group sing-box-manager --confirm" in report.items[0].guidance
    assert report.items[0].diagnostics == "sudo: helper not found"


def test_direct_mode_keeps_missing_helper_as_non_blocking_core_update_guidance() -> None:
    direct_target = StubConfigInspector(LiveConfigObservation(exists=False, sha256=None))
    helper = StubConfigInspector(error=ConfigTargetInspectionError("helper unavailable"))
    core = StubCoreStatusInspector(
        CoreStatusObservation(
            available=True,
            version="1.13.0",
            diagnostics="sing-box version 1.13.0",
        )
    )
    readiness = HostReadinessService(
        access_mode=HostAccessMode.DIRECT,
        config_inspector=direct_target,
        privileged_inspector=helper,
        core_inspector=core,
    )

    report = readiness.inspect()

    assert report.ready_for_apply is True
    assert report.action_required_count == 0
    assert report.recommended_action == "安装最小权限策略以启用核心升级"
    assert [(item.code, item.state) for item in report.items] == [
        (HostReadinessItemCode.CONFIG_TARGET, ReadinessState.READY),
        (HostReadinessItemCode.PRIVILEGED_HELPER, ReadinessState.ATTENTION),
        (HostReadinessItemCode.CORE, ReadinessState.READY),
    ]


def test_direct_mode_prioritizes_an_unreadable_config_target_over_helper_attention() -> None:
    direct_target = StubConfigInspector(
        error=ConfigTargetInspectionError("permission denied: config.json")
    )
    helper = StubConfigInspector(error=ConfigTargetInspectionError("helper unavailable"))
    core = StubCoreStatusInspector(
        CoreStatusObservation(
            available=True,
            version="1.13.0",
            diagnostics="sing-box version 1.13.0",
        )
    )
    readiness = HostReadinessService(
        access_mode=HostAccessMode.DIRECT,
        config_inspector=direct_target,
        privileged_inspector=helper,
        core_inspector=core,
    )

    report = readiness.inspect()

    assert report.ready_for_apply is False
    assert report.recommended_action == "修复配置目标权限或改用最小权限模式"
    assert report.items[0].state is ReadinessState.ACTION_REQUIRED
    assert "--apply-mode privileged" in report.items[0].guidance
