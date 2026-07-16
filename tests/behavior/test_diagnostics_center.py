from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.diagnostics_center import (
    DiagnosticCode,
    DiagnosticCondition,
    DiagnosticsCenterService,
)
from sb_manager.application.host_diagnostics import (
    HostCondition,
    HostDiagnosticsReport,
)
from sb_manager.application.host_readiness import (
    HostReadinessItem,
    HostReadinessItemCode,
    HostReadinessReport,
    ReadinessState,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import RealityMaterial
from sb_manager.seams.config_target import ConfigTargetInspectionError, LiveConfigObservation


class FixedConfigurationTargetInspector:
    def __init__(self, observation: LiveConfigObservation) -> None:
        self.observation = observation

    def inspect(self) -> LiveConfigObservation:
        return self.observation


class FailingConfigurationTargetInspector:
    def inspect(self) -> LiveConfigObservation:
        raise ConfigTargetInspectionError("helper inspection timed out")


class FixedHostReadiness:
    def __init__(self, report: HostReadinessReport) -> None:
        self.report = report

    def inspect(self) -> HostReadinessReport:
        return self.report


class FixedHostDiagnostics:
    def __init__(self, report: HostDiagnosticsReport) -> None:
        self.report = report

    def inspect(self) -> HostDiagnosticsReport:
        return self.report


class CorruptStateStore:
    def load(self) -> ManagedInstallation:
        raise ValueError("invalid desired-state JSON")

    def save(self, installation: ManagedInstallation) -> None:
        raise AssertionError("diagnostics must remain read-only")


class FailingHostReadiness:
    def inspect(self) -> HostReadinessReport:
        raise OSError("sudo helper unavailable")


class FailingHostDiagnostics:
    def inspect(self) -> HostDiagnosticsReport:
        raise OSError("systemctl timed out")


def ready_item(code: HostReadinessItemCode, title: str) -> HostReadinessItem:
    return HostReadinessItem(
        code=code,
        state=ReadinessState.READY,
        title=title,
        summary=f"{title}可用",
        diagnostics="ready",
        guidance="",
    )


def empty_config_inspector() -> FixedConfigurationTargetInspector:
    return FixedConfigurationTargetInspector(LiveConfigObservation(exists=False, sha256=None))


def test_recorded_live_configuration_identity_is_reported_as_healthy() -> None:
    expected_sha256 = "a" * 64
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(
            ManagedInstallation(
                schema_version=1,
                revision=3,
                profiles=(),
                expected_config_sha256=expected_sha256,
            )
        ),
        config_inspector=FixedConfigurationTargetInspector(
            LiveConfigObservation(exists=True, sha256=expected_sha256)
        ),
        host_readiness=FixedHostReadiness(HostReadinessReport(items=())),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    report = center.inspect()

    live_configuration = report.items[1]
    assert live_configuration.code is DiagnosticCode.LIVE_CONFIGURATION
    assert live_configuration.condition is DiagnosticCondition.HEALTHY
    assert live_configuration.summary == "实时配置身份与 desired state 记录一致"
    assert live_configuration.diagnostics == f"当前配置 SHA-256：{expected_sha256}"
    assert live_configuration.guidance == ""


def test_changed_live_configuration_identity_requires_operator_action() -> None:
    expected_sha256 = "a" * 64
    observed_sha256 = "b" * 64
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(
            ManagedInstallation(
                schema_version=1,
                revision=3,
                profiles=(),
                expected_config_sha256=expected_sha256,
            )
        ),
        config_inspector=FixedConfigurationTargetInspector(
            LiveConfigObservation(exists=True, sha256=observed_sha256)
        ),
        host_readiness=FixedHostReadiness(HostReadinessReport(items=())),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    report = center.inspect()

    live_configuration = report.items[1]
    assert live_configuration.condition is DiagnosticCondition.ACTION_REQUIRED
    assert live_configuration.summary == "实时配置已在 manager 记录后发生变化"
    assert live_configuration.diagnostics == (
        f"记录的 SHA-256：{expected_sha256}，当前 SHA-256：{observed_sha256}"
    )
    assert live_configuration.guidance == (
        "不要直接应用。先备份当前配置并确认外部修改来源。若改动非预期，恢复记录版本后重新检查。"
    )
    assert report.recommended_action == live_configuration.guidance


def test_missing_recorded_live_configuration_requires_recovery() -> None:
    expected_sha256 = "a" * 64
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(
            ManagedInstallation(
                schema_version=1,
                revision=3,
                profiles=(),
                expected_config_sha256=expected_sha256,
            )
        ),
        config_inspector=FixedConfigurationTargetInspector(
            LiveConfigObservation(exists=False, sha256=None)
        ),
        host_readiness=FixedHostReadiness(HostReadinessReport(items=())),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    live_configuration = center.inspect().items[1]

    assert live_configuration.condition is DiagnosticCondition.ACTION_REQUIRED
    assert live_configuration.summary == "desired state 记录的实时配置不存在"
    assert live_configuration.diagnostics == f"记录的 SHA-256：{expected_sha256}，配置目标不存在"
    assert live_configuration.guidance == (
        "不要创建空文件或直接应用。先确认配置目标路径和挂载状态，再从已知正常版本恢复。"
    )


def test_untracked_existing_configuration_requires_explicit_adoption() -> None:
    observed_sha256 = "b" * 64
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=FixedConfigurationTargetInspector(
            LiveConfigObservation(exists=True, sha256=observed_sha256)
        ),
        host_readiness=FixedHostReadiness(HostReadinessReport(items=())),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    live_configuration = center.inspect().items[1]

    assert live_configuration.condition is DiagnosticCondition.ACTION_REQUIRED
    assert live_configuration.summary == "发现尚未由 manager 接管的现有配置"
    assert live_configuration.diagnostics == f"当前配置 SHA-256：{observed_sha256}"
    assert live_configuration.guidance == (
        "打开现有配置接管流程，先审查并确认这个精确指纹。接管不会导入或改写配置。"
    )


def test_empty_configuration_target_is_healthy_when_no_identity_is_recorded() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=FixedConfigurationTargetInspector(
            LiveConfigObservation(exists=False, sha256=None)
        ),
        host_readiness=FixedHostReadiness(HostReadinessReport(items=())),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    live_configuration = center.inspect().items[1]

    assert live_configuration.condition is DiagnosticCondition.HEALTHY
    assert live_configuration.summary == "配置目标不存在，desired state 也未记录实时配置"
    assert live_configuration.diagnostics == "没有待核对的实时配置身份"
    assert live_configuration.guidance == ""


def test_configuration_identity_probe_failure_keeps_independent_evidence() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=FailingConfigurationTargetInspector(),
        host_readiness=FixedHostReadiness(
            HostReadinessReport(items=(ready_item(HostReadinessItemCode.CORE, "sing-box 核心"),))
        ),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    report = center.inspect()

    assert tuple(item.code for item in report.items) == (
        DiagnosticCode.DESIRED_STATE,
        DiagnosticCode.LIVE_CONFIGURATION,
        DiagnosticCode.CORE,
        DiagnosticCode.RUNTIME,
    )
    live_configuration = report.items[1]
    assert live_configuration.condition is DiagnosticCondition.ACTION_REQUIRED
    assert live_configuration.summary == "无法核对实时配置身份"
    assert live_configuration.diagnostics == "helper inspection timed out"
    assert live_configuration.guidance == (
        "确认配置目标读取权限或最小权限 helper 后重新检查。在身份未知时不要应用配置。"
    )
    assert report.items[-1].condition is DiagnosticCondition.HEALTHY


def test_diagnostics_center_aggregates_healthy_desired_host_and_runtime_evidence() -> None:
    applied = ManagedProfile(
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
    )
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(
            ManagedInstallation(
                schema_version=1,
                revision=4,
                profiles=(applied,),
                expected_config_sha256="a" * 64,
            )
        ),
        config_inspector=FixedConfigurationTargetInspector(
            LiveConfigObservation(exists=True, sha256="a" * 64)
        ),
        host_readiness=FixedHostReadiness(
            HostReadinessReport(
                items=(
                    ready_item(HostReadinessItemCode.CONFIG_TARGET, "配置目标"),
                    ready_item(HostReadinessItemCode.PRIVILEGED_HELPER, "最小权限 helper"),
                    ready_item(HostReadinessItemCode.CORE, "sing-box 核心"),
                )
            )
        ),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    report = center.inspect()

    assert report.condition is DiagnosticCondition.HEALTHY
    assert tuple(item.code for item in report.items) == (
        DiagnosticCode.DESIRED_STATE,
        DiagnosticCode.LIVE_CONFIGURATION,
        DiagnosticCode.CONFIG_TARGET,
        DiagnosticCode.PRIVILEGED_HELPER,
        DiagnosticCode.CORE,
        DiagnosticCode.RUNTIME,
    )
    assert report.action_required_count == 0
    assert report.attention_count == 0
    assert report.recommended_action == "当前无需处理，可以安全继续操作"
    desired_state = report.items[0]
    assert desired_state.summary == ("desired state revision 4 可读取，1 个已应用配置，0 个草案")
    assert desired_state.condition is DiagnosticCondition.HEALTHY


def test_diagnostics_center_prioritizes_inconsistent_applied_desired_state() -> None:
    incomplete = ManagedProfile(
        profile_id="profile-1",
        profile_name="损坏的配置",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=None,
        port_selection=PortSelection.AUTOMATIC,
        status=ProfileStatus.APPLIED,
        protocol_material=None,
    )
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(
            ManagedInstallation(
                schema_version=1,
                revision=9,
                profiles=(incomplete,),
                expected_config_sha256=None,
            )
        ),
        config_inspector=empty_config_inspector(),
        host_readiness=FixedHostReadiness(HostReadinessReport(items=())),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    report = center.inspect()

    desired_state = report.items[0]
    assert desired_state.condition is DiagnosticCondition.ACTION_REQUIRED
    assert desired_state.summary == "desired state 存在 3 个一致性问题"
    assert desired_state.diagnostics == (
        "profile-1: 已应用配置缺少监听端口; "
        "profile-1: 已应用配置缺少协议凭据; "
        "已应用配置存在，但缺少 managed configuration fingerprint"
    )
    assert desired_state.guidance == (
        "不要直接编辑 JSON。先恢复 desired-state 备份，或移除并重新创建受影响配置。"
    )
    assert report.condition is DiagnosticCondition.ACTION_REQUIRED
    assert report.recommended_action == desired_state.guidance


def test_corrupt_desired_state_does_not_hide_independent_host_evidence() -> None:
    center = DiagnosticsCenterService(
        state_store=CorruptStateStore(),
        config_inspector=FixedConfigurationTargetInspector(
            LiveConfigObservation(exists=True, sha256="b" * 64)
        ),
        host_readiness=FixedHostReadiness(
            HostReadinessReport(items=(ready_item(HostReadinessItemCode.CORE, "sing-box 核心"),))
        ),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    report = center.inspect()

    assert tuple(item.code for item in report.items) == (
        DiagnosticCode.DESIRED_STATE,
        DiagnosticCode.CORE,
        DiagnosticCode.RUNTIME,
    )
    desired_state = report.items[0]
    assert desired_state.condition is DiagnosticCondition.ACTION_REQUIRED
    assert desired_state.summary == "无法读取 manager desired state"
    assert desired_state.diagnostics == "invalid desired-state JSON"
    assert desired_state.guidance == (
        "不要覆盖现有文件。检查 state.json.bak，确认内容后恢复兼容的 desired state。"
    )
    assert report.items[-1].condition is DiagnosticCondition.HEALTHY


def test_readiness_probe_failure_is_one_actionable_check_and_runtime_still_runs() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        host_readiness=FailingHostReadiness(),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    report = center.inspect()

    assert tuple(item.code for item in report.items) == (
        DiagnosticCode.DESIRED_STATE,
        DiagnosticCode.LIVE_CONFIGURATION,
        DiagnosticCode.HOST_READINESS,
        DiagnosticCode.RUNTIME,
    )
    readiness = report.items[2]
    assert readiness.condition is DiagnosticCondition.ACTION_REQUIRED
    assert readiness.summary == "无法完成主机准备度检查"
    assert readiness.diagnostics == "sudo helper unavailable"
    assert readiness.guidance == ("重新运行检查，若持续失败，确认 helper、core 与配置目标权限。")
    assert report.items[-1].condition is DiagnosticCondition.HEALTHY


def test_runtime_probe_failure_is_reported_without_discarding_readiness_results() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        host_readiness=FixedHostReadiness(
            HostReadinessReport(items=(ready_item(HostReadinessItemCode.CORE, "sing-box 核心"),))
        ),
        host_diagnostics=FailingHostDiagnostics(),
    )

    report = center.inspect()

    assert tuple(item.code for item in report.items) == (
        DiagnosticCode.DESIRED_STATE,
        DiagnosticCode.LIVE_CONFIGURATION,
        DiagnosticCode.CORE,
        DiagnosticCode.RUNTIME,
    )
    runtime = report.items[-1]
    assert runtime.condition is DiagnosticCondition.ACTION_REQUIRED
    assert runtime.summary == "无法完成 sing-box 运行状态检查"
    assert runtime.diagnostics == "systemctl timed out"
    assert runtime.guidance == (
        "确认 init system 和 sing-box 服务名称后重新检查，不要在状态未知时应用配置。"
    )


def test_duplicate_profile_identity_is_reported_before_lifecycle_actions() -> None:
    drafts = tuple(
        ManagedProfile(
            profile_id="profile-1",
            profile_name=name,
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=port,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
        )
        for name, port in (("手机", 4433), ("平板", 8443))
    )
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=2, profiles=drafts)
        ),
        config_inspector=empty_config_inspector(),
        host_readiness=FixedHostReadiness(HostReadinessReport(items=())),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    report = center.inspect()

    desired_state = report.items[0]
    assert desired_state.condition is DiagnosticCondition.ACTION_REQUIRED
    assert desired_state.summary == "desired state 存在 1 个一致性问题"
    assert desired_state.diagnostics == "重复的 profile ID: profile-1"


def test_missing_stable_profile_identity_is_actionable_migration_evidence() -> None:
    legacy_draft = ManagedProfile(
        profile_id="",
        profile_name="旧配置",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=1, profiles=(legacy_draft,))
        ),
        config_inspector=empty_config_inspector(),
        host_readiness=FixedHostReadiness(HostReadinessReport(items=())),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics="active",
                recovery_instructions=(),
            )
        ),
    )

    desired_state = center.inspect().items[0]

    assert desired_state.condition is DiagnosticCondition.ACTION_REQUIRED
    assert desired_state.diagnostics == "配置缺少稳定 profile ID: 旧配置"


def test_action_required_runtime_guidance_precedes_readiness_attention() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        host_readiness=FixedHostReadiness(
            HostReadinessReport(
                items=(
                    HostReadinessItem(
                        code=HostReadinessItemCode.PRIVILEGED_HELPER,
                        state=ReadinessState.ATTENTION,
                        title="最小权限 helper",
                        summary="直接模式可用，但 helper 尚未安装",
                        diagnostics="policy missing",
                        guidance="安装最小权限策略以启用核心升级",
                    ),
                )
            )
        ),
        host_diagnostics=FixedHostDiagnostics(
            HostDiagnosticsReport(
                condition=HostCondition.UNHEALTHY,
                summary="sing-box 服务未通过健康检查",
                diagnostics="inactive",
                recovery_instructions=(
                    "运行 systemctl restart sing-box.service。",
                    "重新检查服务状态。",
                ),
            )
        ),
    )

    report = center.inspect()

    assert report.condition is DiagnosticCondition.ACTION_REQUIRED
    assert report.attention_count == 1
    assert report.action_required_count == 1
    assert report.recommended_action == (
        "运行 systemctl restart sing-box.service。 重新检查服务状态。"
    )
