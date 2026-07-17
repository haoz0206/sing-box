from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.apply_history import (
    ApplyHistoryCondition,
    ApplyHistoryReport,
)
from sb_manager.application.certificate_diagnostics import (
    CertificateDiagnosticCondition,
    CertificateDiagnosticsReport,
)
from sb_manager.application.diagnostics_center import (
    DiagnosticAction,
    DiagnosticCode,
    DiagnosticCondition,
    DiagnosticsCenterInspectors,
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
from sb_manager.application.listener_diagnostics import (
    ListenerDiagnosticCondition,
    ListenerDiagnosticsReport,
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
from sb_manager.seams.domain_resolution import (
    DomainResolutionInspectionError,
    DomainResolutionObservation,
    DomainResolutionResult,
)
from sb_manager.seams.generated_configuration import (
    GeneratedConfigurationInspectionError,
    GeneratedConfigurationObservation,
)


class FixedConfigurationTargetInspector:
    def __init__(self, observation: LiveConfigObservation) -> None:
        self.observation = observation

    def inspect(self) -> LiveConfigObservation:
        return self.observation


class FailingConfigurationTargetInspector:
    def inspect(self) -> LiveConfigObservation:
        raise ConfigTargetInspectionError("helper inspection timed out")


class FixedDomainResolutionInspector:
    def __init__(self, observation: DomainResolutionObservation) -> None:
        self.observation = observation

    def inspect(self, installation: ManagedInstallation) -> DomainResolutionObservation:
        return self.observation


class FailingDomainResolutionInspector:
    def inspect(self, installation: ManagedInstallation) -> DomainResolutionObservation:
        raise DomainResolutionInspectionError("DNS worker timed out after 5 seconds")


class FixedGeneratedConfigurationInspector:
    def __init__(self, observation: GeneratedConfigurationObservation) -> None:
        self.observation = observation

    def inspect(self, installation: ManagedInstallation) -> GeneratedConfigurationObservation:
        return self.observation


class FailingGeneratedConfigurationInspector:
    def inspect(self, installation: ManagedInstallation) -> GeneratedConfigurationObservation:
        raise GeneratedConfigurationInspectionError("sing-box check timed out")


class FixedListenerDiagnostics:
    def __init__(self, report: ListenerDiagnosticsReport) -> None:
        self.report = report

    def inspect(self, installation: ManagedInstallation) -> ListenerDiagnosticsReport:
        return self.report


class FixedCertificateDiagnostics:
    def __init__(self, report: CertificateDiagnosticsReport) -> None:
        self.report = report

    def inspect(self, installation: ManagedInstallation) -> CertificateDiagnosticsReport:
        return self.report


class FixedApplyHistoryReader:
    def __init__(self, report: ApplyHistoryReport) -> None:
        self.report = report

    def read_recent(self, *, limit: int = 20) -> ApplyHistoryReport:
        return self.report


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


def test_listener_ownership_evidence_is_preserved_as_a_typed_diagnostic_item() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            listener_diagnostics=FixedListenerDiagnostics(
                ListenerDiagnosticsReport(
                    condition=ListenerDiagnosticCondition.ATTENTION,
                    summary="1 个监听端点的进程归属无法确认",
                    diagnostics="TCP 4433：归属未知",
                    guidance="以能读取 /proc 的权限重新检查。",
                )
            )
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

    listener = next(item for item in report.items if item.code is DiagnosticCode.LISTENER_OWNERSHIP)
    assert listener.condition is DiagnosticCondition.ATTENTION
    assert listener.title == "监听端口与进程归属"
    assert listener.summary == "1 个监听端点的进程归属无法确认"
    assert listener.diagnostics == "TCP 4433：归属未知"


def test_certificate_validity_is_preserved_as_a_typed_diagnostic_item() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            certificate_diagnostics=FixedCertificateDiagnostics(
                CertificateDiagnosticsReport(
                    condition=CertificateDiagnosticCondition.ATTENTION,
                    summary="1 个托管证书将在 30 天内过期",
                    diagnostics="TLS：proxy.example.com，有效至 2026-08-01 (剩余 15 天)",
                    guidance="检查 ACME 自动续期并在 7 天阈值前复检。",
                )
            )
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

    certificate = next(
        item for item in report.items if item.code is DiagnosticCode.CERTIFICATE_CONDITION
    )
    assert certificate.condition is DiagnosticCondition.ATTENTION
    assert certificate.title == "托管证书有效期"
    assert certificate.summary == "1 个托管证书将在 30 天内过期"
    assert "proxy.example.com" in certificate.diagnostics


def test_latest_apply_history_condition_is_preserved_as_a_typed_diagnostic_item() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            apply_history=FixedApplyHistoryReader(
                ApplyHistoryReport(
                    condition=ApplyHistoryCondition.ATTENTION,
                    summary="最近一次配置应用未完成",
                    entries=(),
                    diagnostics="validation failed",
                    guidance="修复后重新预览并确认应用。",
                    limit=1,
                )
            )
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

    history = next(item for item in report.items if item.code is DiagnosticCode.APPLY_HISTORY)
    assert history.condition is DiagnosticCondition.ATTENTION
    assert history.title == "配置应用历史"
    assert history.summary == "最近一次配置应用未完成"
    assert history.diagnostics == "validation failed"


def test_unresolved_public_domain_is_actionable_attention_without_hiding_runtime() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            domain_resolution=FixedDomainResolutionInspector(
                DomainResolutionObservation(
                    results=(
                        DomainResolutionResult(
                            domain="proxy.example.com",
                            addresses=(),
                            error="Name or service not known",
                        ),
                    ),
                    skipped_ip_addresses=0,
                )
            )
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

    assert tuple(item.code for item in report.items) == (
        DiagnosticCode.DESIRED_STATE,
        DiagnosticCode.LIVE_CONFIGURATION,
        DiagnosticCode.DOMAIN_RESOLUTION,
        DiagnosticCode.RUNTIME,
    )
    resolution = report.items[-2]
    assert resolution.condition is DiagnosticCondition.ATTENTION
    assert resolution.title == "公开域名解析"
    assert resolution.summary == "1 个公开域名无法解析"
    assert resolution.diagnostics == "proxy.example.com：Name or service not known"
    assert resolution.guidance == (
        "检查域名拼写、A/AAAA 记录和本机 DNS。解析恢复后再签发证书或分享连接。"
    )
    assert report.items[-1].condition is DiagnosticCondition.HEALTHY


def test_resolved_public_domains_are_reported_with_stable_addresses() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            domain_resolution=FixedDomainResolutionInspector(
                DomainResolutionObservation(
                    results=(
                        DomainResolutionResult(
                            domain="proxy.example.com",
                            addresses=("203.0.113.10", "2001:db8::10"),
                            error=None,
                        ),
                    ),
                    skipped_ip_addresses=1,
                )
            )
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

    resolution = center.inspect().items[-2]

    assert resolution.code is DiagnosticCode.DOMAIN_RESOLUTION
    assert resolution.condition is DiagnosticCondition.HEALTHY
    assert resolution.summary == "1 个公开域名可解析，1 个 IP 地址无需 DNS"
    assert resolution.diagnostics == "proxy.example.com → 203.0.113.10, 2001:db8::10"
    assert resolution.guidance == ""


def test_partial_domain_failure_keeps_successful_resolution_evidence() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            domain_resolution=FixedDomainResolutionInspector(
                DomainResolutionObservation(
                    results=(
                        DomainResolutionResult(
                            domain="bad.example.com",
                            addresses=(),
                            error="Name or service not known",
                        ),
                        DomainResolutionResult(
                            domain="good.example.com",
                            addresses=("203.0.113.20",),
                            error=None,
                        ),
                    ),
                    skipped_ip_addresses=0,
                )
            )
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

    resolution = center.inspect().items[-2]

    assert resolution.condition is DiagnosticCondition.ATTENTION
    assert resolution.summary == "1/2 个公开域名无法解析"
    assert resolution.diagnostics == (
        "bad.example.com：Name or service not known; good.example.com → 203.0.113.20"
    )


def test_no_public_domains_is_a_clear_healthy_diagnostic() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            domain_resolution=FixedDomainResolutionInspector(
                DomainResolutionObservation(results=(), skipped_ip_addresses=0)
            )
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

    resolution = center.inspect().items[-2]

    assert resolution.condition is DiagnosticCondition.HEALTHY
    assert resolution.summary == "当前没有需要 DNS 解析的公开域名"
    assert resolution.diagnostics == "未配置域名端点"
    assert resolution.guidance == ""


def test_ip_only_endpoints_are_distinguished_from_missing_public_address() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            domain_resolution=FixedDomainResolutionInspector(
                DomainResolutionObservation(results=(), skipped_ip_addresses=1)
            )
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

    resolution = center.inspect().items[-2]

    assert resolution.condition is DiagnosticCondition.HEALTHY
    assert resolution.summary == "当前使用 1 个 IP 地址，无需 DNS 解析"
    assert resolution.diagnostics == "IP 端点不依赖 DNS"
    assert resolution.guidance == ""


def test_domain_resolution_probe_failure_is_attention_and_keeps_runtime_evidence() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            domain_resolution=FailingDomainResolutionInspector()
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

    resolution = report.items[-2]
    assert resolution.code is DiagnosticCode.DOMAIN_RESOLUTION
    assert resolution.condition is DiagnosticCondition.ATTENTION
    assert resolution.summary == "无法完成公开域名解析检查"
    assert resolution.diagnostics == "DNS worker timed out after 5 seconds"
    assert resolution.guidance == (
        "确认本机 DNS 和网络可用后重新检查。结果未知不会修改 desired state 或运行服务。"
    )
    assert report.items[-1].code is DiagnosticCode.RUNTIME
    assert report.items[-1].condition is DiagnosticCondition.HEALTHY


def test_invalid_generated_configuration_requires_action_without_hiding_other_evidence() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            generated_configuration=FixedGeneratedConfigurationInspector(
                GeneratedConfigurationObservation(
                    valid=False,
                    diagnostics="inbound[0].tls: missing certificate provider",
                )
            )
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

    assert tuple(item.code for item in report.items) == (
        DiagnosticCode.DESIRED_STATE,
        DiagnosticCode.LIVE_CONFIGURATION,
        DiagnosticCode.GENERATED_CONFIGURATION,
        DiagnosticCode.RUNTIME,
    )
    generated = report.items[2]
    assert generated.condition is DiagnosticCondition.ACTION_REQUIRED
    assert generated.summary == "当前 desired state 生成的 sing-box 配置无效"
    assert generated.diagnostics == "inbound[0].tls: missing certificate provider"
    assert generated.guidance == ("不要应用。修复受影响配置或恢复 desired-state 备份后重新检查。")
    assert report.items[-1].condition is DiagnosticCondition.HEALTHY


def test_valid_generated_configuration_is_reported_as_healthy() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            generated_configuration=FixedGeneratedConfigurationInspector(
                GeneratedConfigurationObservation(
                    valid=True,
                    diagnostics="sing-box check completed successfully",
                )
            )
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

    generated = center.inspect().items[2]

    assert generated.code is DiagnosticCode.GENERATED_CONFIGURATION
    assert generated.condition is DiagnosticCondition.HEALTHY
    assert generated.summary == "当前 desired state 可生成有效的 sing-box 配置"
    assert generated.diagnostics == "sing-box check completed successfully"
    assert generated.guidance == ""


def test_generated_configuration_probe_failure_is_actionable_and_keeps_runtime_evidence() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            generated_configuration=FailingGeneratedConfigurationInspector()
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

    generated = report.items[2]
    assert generated.code is DiagnosticCode.GENERATED_CONFIGURATION
    assert generated.condition is DiagnosticCondition.ACTION_REQUIRED
    assert generated.summary == "无法检查 desired state 生成的 sing-box 配置"
    assert generated.diagnostics == "sing-box check timed out"
    assert generated.guidance == (
        "确认 sing-box 核心和临时目录可用后重新检查。在验证结果未知时不要应用。"
    )
    assert report.items[-1].code is DiagnosticCode.RUNTIME
    assert report.items[-1].condition is DiagnosticCondition.HEALTHY


def test_unavailable_core_action_precedes_generated_configuration_probe_failure() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            generated_configuration=FailingGeneratedConfigurationInspector()
        ),
        host_readiness=FixedHostReadiness(
            HostReadinessReport(
                items=(
                    HostReadinessItem(
                        code=HostReadinessItemCode.PRIVILEGED_HELPER,
                        state=ReadinessState.READY,
                        title="最小权限 helper",
                        summary="最小权限 helper 可用",
                        diagnostics="ready",
                        guidance="",
                    ),
                    HostReadinessItem(
                        code=HostReadinessItemCode.CORE,
                        state=ReadinessState.ACTION_REQUIRED,
                        title="sing-box 核心",
                        summary="sing-box 核心尚不可用",
                        diagnostics="sing-box not found",
                        guidance="选择可信版本并安装 sing-box 核心",
                    ),
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

    assert report.recommended_action == "选择可信版本并安装 sing-box 核心"
    assert report.recommended_action_kind is DiagnosticAction.MANAGE_CORE
    assert tuple(item.code for item in report.items)[-2:] == (
        DiagnosticCode.GENERATED_CONFIGURATION,
        DiagnosticCode.RUNTIME,
    )


def test_generated_configuration_is_not_misreported_invalid_when_core_is_unavailable() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        inspectors=DiagnosticsCenterInspectors(
            generated_configuration=FixedGeneratedConfigurationInspector(
                GeneratedConfigurationObservation(
                    valid=False,
                    diagnostics="sing-box executable not found",
                )
            )
        ),
        host_readiness=FixedHostReadiness(
            HostReadinessReport(
                items=(
                    HostReadinessItem(
                        code=HostReadinessItemCode.CORE,
                        state=ReadinessState.ACTION_REQUIRED,
                        title="sing-box 核心",
                        summary="sing-box 核心尚不可用",
                        diagnostics="sing-box not found",
                        guidance="选择可信版本并安装 sing-box 核心",
                    ),
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

    generated = center.inspect().items[-2]

    assert generated.code is DiagnosticCode.GENERATED_CONFIGURATION
    assert generated.condition is DiagnosticCondition.ACTION_REQUIRED
    assert generated.summary == "sing-box 核心不可用，尚未检查生成配置"
    assert generated.diagnostics == "sing-box not found"
    assert generated.guidance == "先安装或修复 sing-box 核心，再重新运行语义检查。"


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
    assert report.recommended_action is None
    desired_state = report.items[0]
    assert desired_state.summary == (
        "desired state revision 4 可读取，1 个在线配置，0 个已暂停配置，0 个草案"
    )
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


def test_missing_core_recommendation_exposes_trusted_install_action() -> None:
    center = DiagnosticsCenterService(
        state_store=MemoryStateStore(),
        config_inspector=empty_config_inspector(),
        host_readiness=FixedHostReadiness(
            HostReadinessReport(
                items=(
                    HostReadinessItem(
                        code=HostReadinessItemCode.PRIVILEGED_HELPER,
                        state=ReadinessState.READY,
                        title="最小权限 helper",
                        summary="最小权限 helper 可用",
                        diagnostics="ready",
                        guidance="",
                    ),
                    HostReadinessItem(
                        code=HostReadinessItemCode.CORE,
                        state=ReadinessState.ACTION_REQUIRED,
                        title="sing-box 核心",
                        summary="sing-box 核心尚不可用",
                        diagnostics="sing-box not found",
                        guidance="选择可信版本并安装 sing-box 核心",
                    ),
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

    assert report.recommended_action_kind is DiagnosticAction.MANAGE_CORE


def test_missing_core_action_is_withheld_until_privileged_helper_is_ready() -> None:
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
                    HostReadinessItem(
                        code=HostReadinessItemCode.CORE,
                        state=ReadinessState.ACTION_REQUIRED,
                        title="sing-box 核心",
                        summary="sing-box 核心尚不可用",
                        diagnostics="sing-box not found",
                        guidance="选择可信版本并安装 sing-box 核心",
                    ),
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

    assert report.recommended_action == "选择可信版本并安装 sing-box 核心"
    assert report.recommended_action_kind is None
