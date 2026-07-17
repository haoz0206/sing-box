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


class DashboardRecommendationKind(str, Enum):
    """Stable explanation identity rendered by presentation adapters."""

    RECHECK_READINESS = "recheck-readiness"
    RECHECK_RUNTIME = "recheck-runtime"
    RECHECK_CERTIFICATES = "recheck-certificates"
    RESOLVE_READINESS = "resolve-readiness"
    INSPECT_RUNTIME = "inspect-runtime"
    RESOLVE_CERTIFICATES = "resolve-certificates"
    ADD_PROFILE = "add-profile"
    WAIT_FOR_INSPECTIONS = "wait-for-inspections"
    REVIEW_DRAFTS = "review-drafts"
    REVIEW_CERTIFICATES = "review-certificates"
    VERIFY_RUNTIME = "verify-runtime"


@dataclass(frozen=True, slots=True)
class DashboardAction:
    """One executable operator action independent of rendered wording."""

    kind: DashboardActionKind
    profile_id: str | None = None


@dataclass(frozen=True, slots=True)
class DashboardRecommendation:
    """One semantic explanation and its optional executable action."""

    kind: DashboardRecommendationKind
    action: DashboardAction | None
    draft_count: int = 0


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
            kind=DashboardRecommendationKind.RECHECK_READINESS,
            action=DashboardAction(
                kind=DashboardActionKind.RECHECK_READINESS,
            ),
        )
    if evidence.runtime is DashboardProbeState.FAILED:
        return DashboardRecommendation(
            kind=DashboardRecommendationKind.RECHECK_RUNTIME,
            action=DashboardAction(
                kind=DashboardActionKind.RECHECK_RUNTIME,
            ),
        )
    if evidence.certificates is DashboardProbeState.FAILED:
        return DashboardRecommendation(
            kind=DashboardRecommendationKind.RECHECK_CERTIFICATES,
            action=DashboardAction(
                kind=DashboardActionKind.RECHECK_CERTIFICATES,
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
            kind=DashboardRecommendationKind.RESOLVE_READINESS,
            action=DashboardAction(
                kind=DashboardActionKind.OPEN_READINESS,
            ),
        )
    if (
        isinstance(evidence.runtime, HostDiagnosticsReport)
        and evidence.runtime.condition is HostCondition.UNHEALTHY
    ):
        return DashboardRecommendation(
            kind=DashboardRecommendationKind.INSPECT_RUNTIME,
            action=DashboardAction(
                kind=DashboardActionKind.OPEN_RUNTIME_DIAGNOSTICS,
            ),
        )
    if (
        isinstance(evidence.certificates, CertificateDiagnosticsReport)
        and evidence.certificates.condition is CertificateDiagnosticCondition.ACTION_REQUIRED
    ):
        return DashboardRecommendation(
            kind=DashboardRecommendationKind.RESOLVE_CERTIFICATES,
            action=(
                DashboardAction(
                    kind=DashboardActionKind.OPEN_DIAGNOSTICS,
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
            kind=DashboardRecommendationKind.ADD_PROFILE,
            action=DashboardAction(
                kind=DashboardActionKind.ADD_PROFILE,
            ),
        )
    if any(
        probe is DashboardProbeState.PENDING
        for probe in (evidence.runtime, evidence.readiness, evidence.certificates)
    ):
        return DashboardRecommendation(
            kind=DashboardRecommendationKind.WAIT_FOR_INSPECTIONS,
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
            kind=DashboardRecommendationKind.REVIEW_DRAFTS,
            action=(
                DashboardAction(
                    kind=DashboardActionKind.APPLY_DRAFT,
                    profile_id=draft_profiles[0].profile_id,
                )
                if evidence.profile_apply_available
                else None
            ),
            draft_count=len(draft_profiles),
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
            kind=DashboardRecommendationKind.REVIEW_CERTIFICATES,
            action=(
                DashboardAction(
                    kind=DashboardActionKind.OPEN_DIAGNOSTICS,
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
            kind=DashboardRecommendationKind.VERIFY_RUNTIME,
            action=DashboardAction(
                kind=DashboardActionKind.OPEN_RUNTIME_DIAGNOSTICS,
            ),
        )
    return DashboardRecommendation(
        kind=DashboardRecommendationKind.VERIFY_RUNTIME,
        action=(
            DashboardAction(
                kind=DashboardActionKind.OPEN_DIAGNOSTICS,
            )
            if evidence.diagnostics_available
            else None
        ),
    )
