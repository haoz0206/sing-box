"""Typed operator recommendations for the dashboard's safest next action."""

from dataclasses import dataclass
from enum import Enum

from sb_manager.application.certificate_diagnostics import (
    CertificateDiagnosticCondition,
    CertificateDiagnosticsReport,
)
from sb_manager.application.host_diagnostics import HostCondition, HostDiagnosticsReport
from sb_manager.application.host_readiness import HostReadinessReport
from sb_manager.domain.installation import ManagedInstallation, ProfileStatus


class DashboardProbeState(str, Enum):
    """A dashboard observation that did not return typed evidence."""

    NOT_CONFIGURED = "not-configured"
    PENDING = "pending"
    FAILED = "failed"


class DashboardActionKind(str, Enum):
    """Stable action identity consumed by presentation adapters."""

    RECHECK_READINESS = "recheck-readiness"
    RECHECK_RUNTIME = "recheck-runtime"
    RECHECK_CERTIFICATES = "recheck-certificates"
    OPEN_READINESS = "open-readiness"
    OPEN_RUNTIME_DIAGNOSTICS = "open-runtime-diagnostics"
    OPEN_DIAGNOSTICS = "open-diagnostics"
    APPLY_DRAFT = "apply-draft"
    ADD_PROFILE = "add-profile"


@dataclass(frozen=True, slots=True)
class DashboardAction:
    """One executable operator action with presentation-ready wording."""

    kind: DashboardActionKind
    label: str
    profile_id: str | None = None


@dataclass(frozen=True, slots=True)
class DashboardRecommendation:
    """The dashboard explanation and its optional executable action."""

    summary: str
    action: DashboardAction | None


@dataclass(frozen=True, slots=True)
class DashboardEvidence:
    """Independent evidence used to choose the dashboard's next action."""

    installation: ManagedInstallation
    runtime: DashboardProbeState | HostDiagnosticsReport
    readiness: DashboardProbeState | HostReadinessReport
    certificates: DashboardProbeState | CertificateDiagnosticsReport
    diagnostics_available: bool = False
    profile_apply_available: bool = False


def recommend_dashboard_action(evidence: DashboardEvidence) -> DashboardRecommendation:
    """Choose one safe action without coupling navigation to rendered text."""
    for rule in (
        _failed_probe_recommendation,
        _blocking_evidence_recommendation,
        _initial_or_pending_recommendation,
        _draft_recommendation,
        _certificate_attention_recommendation,
    ):
        if recommendation := rule(evidence):
            return recommendation
    return _steady_state_recommendation(evidence)


def _failed_probe_recommendation(
    evidence: DashboardEvidence,
) -> DashboardRecommendation | None:
    if evidence.readiness is DashboardProbeState.FAILED:
        return DashboardRecommendation(
            summary="先重新检查主机准备度",
            action=DashboardAction(
                kind=DashboardActionKind.RECHECK_READINESS,
                label="立即重新检查主机准备度",
            ),
        )
    if evidence.runtime is DashboardProbeState.FAILED:
        return DashboardRecommendation(
            summary="先重新检查服务状态",
            action=DashboardAction(
                kind=DashboardActionKind.RECHECK_RUNTIME,
                label="立即重新检查服务状态",
            ),
        )
    if evidence.certificates is DashboardProbeState.FAILED:
        return DashboardRecommendation(
            summary="先重新检查证书维护状态",
            action=DashboardAction(
                kind=DashboardActionKind.RECHECK_CERTIFICATES,
                label="立即重新检查证书",
            ),
        )
    return None


def _blocking_evidence_recommendation(
    evidence: DashboardEvidence,
) -> DashboardRecommendation | None:
    if (
        isinstance(evidence.readiness, HostReadinessReport)
        and not evidence.readiness.ready_for_apply
    ):
        return DashboardRecommendation(
            summary=evidence.readiness.recommended_action,
            action=DashboardAction(
                kind=DashboardActionKind.OPEN_READINESS,
                label="查看主机准备度",
            ),
        )
    if (
        isinstance(evidence.runtime, HostDiagnosticsReport)
        and evidence.runtime.condition is HostCondition.UNHEALTHY
    ):
        return DashboardRecommendation(
            summary="先检查 sing-box 服务，再进行配置变更",
            action=DashboardAction(
                kind=DashboardActionKind.OPEN_RUNTIME_DIAGNOSTICS,
                label="查看服务诊断",
            ),
        )
    if (
        isinstance(evidence.certificates, CertificateDiagnosticsReport)
        and evidence.certificates.condition is CertificateDiagnosticCondition.ACTION_REQUIRED
    ):
        return DashboardRecommendation(
            summary=evidence.certificates.guidance,
            action=(
                DashboardAction(
                    kind=DashboardActionKind.OPEN_DIAGNOSTICS,
                    label="打开诊断中心",
                )
                if evidence.diagnostics_available
                else None
            ),
        )
    return None


def _initial_or_pending_recommendation(
    evidence: DashboardEvidence,
) -> DashboardRecommendation | None:
    if not evidence.installation.profiles:
        return DashboardRecommendation(
            summary="创建第一个配置",
            action=DashboardAction(
                kind=DashboardActionKind.ADD_PROFILE,
                label="创建第一个配置",
            ),
        )
    if any(
        probe is DashboardProbeState.PENDING
        for probe in (evidence.runtime, evidence.readiness, evidence.certificates)
    ):
        return DashboardRecommendation(
            summary="正在检查主机状态",
            action=None,
        )
    return None


def _draft_recommendation(
    evidence: DashboardEvidence,
) -> DashboardRecommendation | None:
    draft_profiles = tuple(
        profile
        for profile in evidence.installation.profiles
        if profile.status is ProfileStatus.DRAFT
    )
    if draft_profiles:
        return DashboardRecommendation(
            summary=f"先审阅并应用 {len(draft_profiles)} 个草案",
            action=(
                DashboardAction(
                    kind=DashboardActionKind.APPLY_DRAFT,
                    label="审阅并应用草案",
                    profile_id=draft_profiles[0].profile_id,
                )
                if evidence.profile_apply_available
                else None
            ),
        )
    return None


def _certificate_attention_recommendation(
    evidence: DashboardEvidence,
) -> DashboardRecommendation | None:
    if (
        isinstance(evidence.certificates, CertificateDiagnosticsReport)
        and evidence.certificates.condition is CertificateDiagnosticCondition.ATTENTION
    ):
        return DashboardRecommendation(
            summary=evidence.certificates.guidance,
            action=(
                DashboardAction(
                    kind=DashboardActionKind.OPEN_DIAGNOSTICS,
                    label="打开诊断中心",
                )
                if evidence.diagnostics_available
                else None
            ),
        )
    return None


def _steady_state_recommendation(
    evidence: DashboardEvidence,
) -> DashboardRecommendation:
    if isinstance(evidence.runtime, HostDiagnosticsReport):
        return DashboardRecommendation(
            summary="配置已应用，确认服务状态",
            action=DashboardAction(
                kind=DashboardActionKind.OPEN_RUNTIME_DIAGNOSTICS,
                label="查看服务状态",
            ),
        )
    return DashboardRecommendation(
        summary="配置已应用，确认服务状态",
        action=(
            DashboardAction(
                kind=DashboardActionKind.OPEN_DIAGNOSTICS,
                label="打开诊断中心",
            )
            if evidence.diagnostics_available
            else None
        ),
    )
