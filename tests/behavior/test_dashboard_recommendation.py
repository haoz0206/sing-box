from sb_manager.application.certificate_diagnostics import (
    CertificateDiagnosticCondition,
    CertificateDiagnosticsReport,
)
from sb_manager.application.dashboard import (
    DashboardAction,
    DashboardActionKind,
    DashboardEvidence,
    DashboardProbeState,
    DashboardRecommendation,
    DashboardRecommendationKind,
    recommend_dashboard_action,
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


def test_failed_readiness_is_the_first_action_when_multiple_probes_fail() -> None:
    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=ManagedInstallation.empty(),
            runtime=DashboardProbeState.FAILED,
            readiness=DashboardProbeState.FAILED,
            certificates=DashboardProbeState.FAILED,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.RECHECK_READINESS,
        action=DashboardAction(
            kind=DashboardActionKind.RECHECK_READINESS,
        ),
    )


def test_failed_runtime_is_rechecked_before_certificate_evidence() -> None:
    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=ManagedInstallation.empty(),
            runtime=DashboardProbeState.FAILED,
            readiness=DashboardProbeState.NOT_CONFIGURED,
            certificates=DashboardProbeState.FAILED,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.RECHECK_RUNTIME,
        action=DashboardAction(
            kind=DashboardActionKind.RECHECK_RUNTIME,
        ),
    )


def test_failed_certificate_probe_produces_a_direct_recheck_action() -> None:
    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=ManagedInstallation.empty(),
            runtime=DashboardProbeState.NOT_CONFIGURED,
            readiness=DashboardProbeState.NOT_CONFIGURED,
            certificates=DashboardProbeState.FAILED,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.RECHECK_CERTIFICATES,
        action=DashboardAction(
            kind=DashboardActionKind.RECHECK_CERTIFICATES,
        ),
    )


def test_blocking_readiness_opens_its_evidence_before_unhealthy_runtime() -> None:
    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=ManagedInstallation.empty(),
            runtime=HostDiagnosticsReport(
                condition=HostCondition.UNHEALTHY,
                summary="服务异常",
                diagnostics="inactive",
                recovery_instructions=("检查服务",),
            ),
            readiness=HostReadinessReport(
                items=(
                    HostReadinessItem(
                        code=HostReadinessItemCode.PRIVILEGED_HELPER,
                        state=ReadinessState.ACTION_REQUIRED,
                        title="最小权限 helper",
                        summary="尚未部署",
                        diagnostics="helper missing",
                        guidance="安装最小权限策略",
                    ),
                )
            ),
            certificates=DashboardProbeState.NOT_CONFIGURED,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.RESOLVE_READINESS,
        action=DashboardAction(
            kind=DashboardActionKind.OPEN_READINESS,
        ),
    )


def test_unhealthy_runtime_opens_diagnostics_after_readiness_is_clear() -> None:
    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=ManagedInstallation.empty(),
            runtime=HostDiagnosticsReport(
                condition=HostCondition.UNHEALTHY,
                summary="服务异常",
                diagnostics="inactive",
                recovery_instructions=("检查服务",),
            ),
            readiness=HostReadinessReport(items=()),
            certificates=DashboardProbeState.NOT_CONFIGURED,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.INSPECT_RUNTIME,
        action=DashboardAction(
            kind=DashboardActionKind.OPEN_RUNTIME_DIAGNOSTICS,
        ),
    )


def test_urgent_certificate_evidence_opens_the_diagnostics_center() -> None:
    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=ManagedInstallation.empty(),
            runtime=DashboardProbeState.NOT_CONFIGURED,
            readiness=HostReadinessReport(items=()),
            certificates=CertificateDiagnosticsReport(
                condition=CertificateDiagnosticCondition.ACTION_REQUIRED,
                summary="1 个证书需要处理",
                diagnostics="certificate expired",
                guidance="处理已过期证书",
            ),
            diagnostics_available=True,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.RESOLVE_CERTIFICATES,
        action=DashboardAction(
            kind=DashboardActionKind.OPEN_DIAGNOSTICS,
        ),
    )


def test_draft_review_is_actionable_before_certificate_attention() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=3,
        profiles=(
            ManagedProfile(
                profile_id="draft-phone",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=None,
                port_selection=PortSelection.AUTOMATIC,
                status=ProfileStatus.DRAFT,
            ),
        ),
    )

    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=installation,
            runtime=DashboardProbeState.NOT_CONFIGURED,
            readiness=HostReadinessReport(items=()),
            certificates=CertificateDiagnosticsReport(
                condition=CertificateDiagnosticCondition.ATTENTION,
                summary="证书将在 30 天内到期",
                diagnostics="20 days remaining",
                guidance="安排证书续期检查",
            ),
            profile_apply_available=True,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.REVIEW_DRAFTS,
        action=DashboardAction(
            kind=DashboardActionKind.APPLY_DRAFT,
            profile_id="draft-phone",
        ),
        draft_count=1,
    )


def test_certificate_attention_remains_actionable_when_there_are_no_drafts() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=4,
        profiles=(
            ManagedProfile(
                profile_id="phone",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
        ),
    )
    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=installation,
            runtime=DashboardProbeState.NOT_CONFIGURED,
            readiness=HostReadinessReport(items=()),
            certificates=CertificateDiagnosticsReport(
                condition=CertificateDiagnosticCondition.ATTENTION,
                summary="证书将在 30 天内到期",
                diagnostics="20 days remaining",
                guidance="安排证书续期检查",
            ),
            diagnostics_available=True,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.REVIEW_CERTIFICATES,
        action=DashboardAction(
            kind=DashboardActionKind.OPEN_DIAGNOSTICS,
        ),
    )


def test_empty_dashboard_starts_the_guided_profile_journey() -> None:
    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=ManagedInstallation.empty(),
            runtime=DashboardProbeState.NOT_CONFIGURED,
            readiness=DashboardProbeState.NOT_CONFIGURED,
            certificates=DashboardProbeState.NOT_CONFIGURED,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.ADD_PROFILE,
        action=DashboardAction(
            kind=DashboardActionKind.ADD_PROFILE,
        ),
    )


def test_applied_profile_can_open_healthy_runtime_evidence() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=4,
        profiles=(
            ManagedProfile(
                profile_id="phone",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
        ),
    )

    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=installation,
            runtime=HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="服务正常",
                diagnostics="active",
                recovery_instructions=(),
            ),
            readiness=HostReadinessReport(items=()),
            certificates=DashboardProbeState.NOT_CONFIGURED,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.VERIFY_RUNTIME,
        action=DashboardAction(
            kind=DashboardActionKind.OPEN_RUNTIME_DIAGNOSTICS,
        ),
    )


def test_applied_profile_waits_for_pending_observations_without_guessing() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=4,
        profiles=(
            ManagedProfile(
                profile_id="phone",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
        ),
    )

    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=installation,
            runtime=DashboardProbeState.PENDING,
            readiness=DashboardProbeState.PENDING,
            certificates=DashboardProbeState.PENDING,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.WAIT_FOR_INSPECTIONS,
        action=None,
    )


def test_empty_dashboard_can_start_planning_while_host_checks_are_pending() -> None:
    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=ManagedInstallation.empty(),
            runtime=DashboardProbeState.PENDING,
            readiness=DashboardProbeState.PENDING,
            certificates=DashboardProbeState.PENDING,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.ADD_PROFILE,
        action=DashboardAction(
            kind=DashboardActionKind.ADD_PROFILE,
        ),
    )


def test_applied_profile_without_host_tools_keeps_a_non_executable_summary() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=4,
        profiles=(
            ManagedProfile(
                profile_id="phone",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
        ),
    )

    recommendation = recommend_dashboard_action(
        DashboardEvidence(
            installation=installation,
            runtime=DashboardProbeState.NOT_CONFIGURED,
            readiness=DashboardProbeState.NOT_CONFIGURED,
            certificates=DashboardProbeState.NOT_CONFIGURED,
        )
    )

    assert recommendation == DashboardRecommendation(
        kind=DashboardRecommendationKind.VERIFY_RUNTIME,
        action=None,
    )
