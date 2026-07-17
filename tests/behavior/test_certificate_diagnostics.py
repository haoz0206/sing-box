from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sb_manager.application.certificate_diagnostics import (
    CertificateDiagnosticCondition,
    CertificateDiagnosticsService,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.certificate_source import (
    CertificateInspection,
    CertificateInspectionError,
    CertificateMaterialState,
    CertificateObservation,
    CertificateTarget,
    CertificateTargetKind,
)
from sb_manager.tls.catalog import AcmeTlsIntent, OperatorFileTlsIntent


class RecordingCertificateSource:
    def __init__(self, observations: tuple[CertificateObservation, ...] = ()) -> None:
        self.observations = observations
        self.requested: tuple[CertificateTarget, ...] | None = None

    def inspect(self, targets: tuple[CertificateTarget, ...]) -> CertificateInspection:
        self.requested = targets
        return CertificateInspection(observations=self.observations)


class FailingCertificateSource:
    def inspect(self, targets: tuple[CertificateTarget, ...]) -> CertificateInspection:
        raise CertificateInspectionError("privileged helper timed out")


def test_profiles_without_managed_x509_tls_skip_certificate_observation() -> None:
    source = RecordingCertificateSource()
    service = CertificateDiagnosticsService(source=source)
    installation = ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(
            ManagedProfile(
                profile_id="reality",
                profile_name="Reality",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
        ),
    )

    report = service.inspect(installation)

    assert report.condition is CertificateDiagnosticCondition.HEALTHY
    assert report.summary == "当前没有需要检查的托管 X.509 证书"
    assert source.requested is None


def test_enabled_applied_tls_profiles_request_deduplicated_public_certificate_targets() -> None:
    now = datetime(2026, 7, 17, 0, 0, tzinfo=timezone.utc)
    operator_target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="files.example.com",
        location=Path("/etc/sing-box-manager/tls/server.crt"),
    )
    acme_target = CertificateTarget(
        kind=CertificateTargetKind.CERTMAGIC_ACME,
        server_name="acme.example.com",
        location=Path("/var/lib/sing-box-manager/acme"),
    )
    source = RecordingCertificateSource(
        (
            CertificateObservation(
                target=operator_target,
                state=CertificateMaterialState.AVAILABLE,
                source_label="operator file",
                diagnostics="",
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=90),
                dns_names=("files.example.com",),
            ),
            CertificateObservation(
                target=acme_target,
                state=CertificateMaterialState.AVAILABLE,
                source_label="CertMagic ACME cache",
                diagnostics="",
                not_valid_before=now - timedelta(days=1),
                not_valid_after=now + timedelta(days=60),
                dns_names=("acme.example.com",),
            ),
        )
    )
    operator_intent = OperatorFileTlsIntent(
        server_name=operator_target.server_name,
        certificate_path=operator_target.location,
        key_path=Path("/etc/sing-box-manager/tls/server.key"),
    )
    acme_intent = AcmeTlsIntent(
        server_name=acme_target.server_name,
        email="operator@example.com",
        data_directory=acme_target.location,
    )
    profiles = (
        ManagedProfile(
            profile_id="operator",
            profile_name="文件证书",
            protocol=ProtocolKind.VLESS_TLS,
            listen_port=4433,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
            tls_intent=operator_intent,
        ),
        ManagedProfile(
            profile_id="acme",
            profile_name="ACME 证书",
            protocol=ProtocolKind.HYSTERIA2,
            listen_port=8443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
            tls_intent=acme_intent,
        ),
        ManagedProfile(
            profile_id="duplicate",
            profile_name="共享文件证书",
            protocol=ProtocolKind.VMESS_TLS,
            listen_port=9443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
            tls_intent=operator_intent,
        ),
        ManagedProfile(
            profile_id="paused",
            profile_name="暂停",
            protocol=ProtocolKind.TUIC,
            listen_port=10443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
            enabled=False,
            tls_intent=acme_intent,
        ),
    )
    service = CertificateDiagnosticsService(source=source, now=lambda: now)

    report = service.inspect(ManagedInstallation(schema_version=1, revision=1, profiles=profiles))

    assert source.requested == (operator_target, acme_target)
    assert report.condition is CertificateDiagnosticCondition.HEALTHY
    assert report.summary == "2 个托管证书有效期均正常"
    assert "文件证书、共享文件证书" in report.diagnostics


def test_expired_certificate_requires_action() -> None:
    now = datetime(2026, 7, 17, 0, 0, tzinfo=timezone.utc)
    target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="expired.example.com",
        location=Path("/etc/sing-box-manager/tls/expired.crt"),
    )
    source = RecordingCertificateSource(
        (
            CertificateObservation(
                target=target,
                state=CertificateMaterialState.AVAILABLE,
                source_label="operator file",
                diagnostics="",
                not_valid_before=now - timedelta(days=91),
                not_valid_after=now - timedelta(days=1),
                dns_names=(target.server_name,),
            ),
        )
    )
    profile = ManagedProfile(
        profile_id="expired",
        profile_name="已过期",
        protocol=ProtocolKind.TROJAN,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        tls_intent=OperatorFileTlsIntent(
            server_name=target.server_name,
            certificate_path=target.location,
            key_path=Path("/etc/sing-box-manager/tls/expired.key"),
        ),
    )

    report = CertificateDiagnosticsService(source=source, now=lambda: now).inspect(
        ManagedInstallation(schema_version=1, revision=1, profiles=(profile,))
    )

    assert report.condition is CertificateDiagnosticCondition.ACTION_REQUIRED
    assert report.summary == "1 个托管证书已过期"
    assert "已过期 1 天" in report.diagnostics
    assert "立即更新" in report.guidance


@pytest.mark.parametrize(
    ("remaining_days", "condition", "summary"),
    [
        (
            7,
            CertificateDiagnosticCondition.ACTION_REQUIRED,
            "1 个托管证书将在 7 天内过期",
        ),
        (
            30,
            CertificateDiagnosticCondition.ATTENTION,
            "1 个托管证书将在 30 天内过期",
        ),
    ],
)
def test_certificate_expiry_thresholds_are_actionable_before_outage(
    remaining_days: int,
    condition: CertificateDiagnosticCondition,
    summary: str,
) -> None:
    now = datetime(2026, 7, 17, 0, 0, tzinfo=timezone.utc)
    target = CertificateTarget(
        kind=CertificateTargetKind.CERTMAGIC_ACME,
        server_name="renew.example.com",
        location=Path("/var/lib/sing-box-manager/acme"),
    )
    source = RecordingCertificateSource(
        (
            CertificateObservation(
                target=target,
                state=CertificateMaterialState.AVAILABLE,
                source_label="CertMagic ACME cache",
                diagnostics="",
                not_valid_before=now - timedelta(days=60),
                not_valid_after=now + timedelta(days=remaining_days),
                dns_names=(target.server_name,),
            ),
        )
    )
    profile = ManagedProfile(
        profile_id="renew",
        profile_name="待续期",
        protocol=ProtocolKind.HYSTERIA2,
        listen_port=8443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        tls_intent=AcmeTlsIntent(
            server_name=target.server_name,
            email="operator@example.com",
            data_directory=target.location,
        ),
    )

    report = CertificateDiagnosticsService(source=source, now=lambda: now).inspect(
        ManagedInstallation(schema_version=1, revision=1, profiles=(profile,))
    )

    assert report.condition is condition
    assert report.summary == summary
    assert f"剩余 {remaining_days} 天" in report.diagnostics


@pytest.mark.parametrize(
    ("state", "condition", "summary"),
    [
        (
            CertificateMaterialState.MISSING,
            CertificateDiagnosticCondition.ACTION_REQUIRED,
            "1 个托管证书材料缺失",
        ),
        (
            CertificateMaterialState.INVALID,
            CertificateDiagnosticCondition.ACTION_REQUIRED,
            "1 个托管证书材料无效",
        ),
        (
            CertificateMaterialState.UNAVAILABLE,
            CertificateDiagnosticCondition.ATTENTION,
            "1 个托管证书状态无法确认",
        ),
    ],
)
def test_missing_invalid_and_unavailable_material_remain_distinct(
    state: CertificateMaterialState,
    condition: CertificateDiagnosticCondition,
    summary: str,
) -> None:
    target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="material.example.com",
        location=Path("/etc/sing-box-manager/tls/material.crt"),
    )
    source = RecordingCertificateSource(
        (
            CertificateObservation(
                target=target,
                state=state,
                source_label="operator file",
                diagnostics=(
                    "permission denied" if state is CertificateMaterialState.UNAVAILABLE else ""
                ),
            ),
        )
    )
    profile = ManagedProfile(
        profile_id="material",
        profile_name="证书材料",
        protocol=ProtocolKind.ANYTLS,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        tls_intent=OperatorFileTlsIntent(
            server_name=target.server_name,
            certificate_path=target.location,
            key_path=Path("/etc/sing-box-manager/tls/material.key"),
        ),
    )

    report = CertificateDiagnosticsService(source=source).inspect(
        ManagedInstallation(schema_version=1, revision=1, profiles=(profile,))
    )

    assert report.condition is condition
    assert report.summary == summary
    assert "证书材料" in report.diagnostics


def test_certificate_that_is_not_yet_valid_requires_action() -> None:
    now = datetime(2026, 7, 17, 0, 0, tzinfo=timezone.utc)
    target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="future.example.com",
        location=Path("/etc/sing-box-manager/tls/future.crt"),
    )
    source = RecordingCertificateSource(
        (
            CertificateObservation(
                target=target,
                state=CertificateMaterialState.AVAILABLE,
                source_label="operator file",
                diagnostics="",
                not_valid_before=now + timedelta(days=1),
                not_valid_after=now + timedelta(days=91),
                dns_names=(target.server_name,),
            ),
        )
    )
    profile = ManagedProfile(
        profile_id="future",
        profile_name="尚未生效",
        protocol=ProtocolKind.VLESS_TLS,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        tls_intent=OperatorFileTlsIntent(
            server_name=target.server_name,
            certificate_path=target.location,
            key_path=Path("/etc/sing-box-manager/tls/future.key"),
        ),
    )

    report = CertificateDiagnosticsService(source=source, now=lambda: now).inspect(
        ManagedInstallation(schema_version=1, revision=1, profiles=(profile,))
    )

    assert report.condition is CertificateDiagnosticCondition.ACTION_REQUIRED
    assert report.summary == "1 个托管证书尚未生效"
    assert "2026-07-18" in report.diagnostics


def test_unavailable_certificate_source_is_attention_not_false_health() -> None:
    profile = ManagedProfile(
        profile_id="tls",
        profile_name="TLS",
        protocol=ProtocolKind.VLESS_TLS,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        tls_intent=OperatorFileTlsIntent(
            server_name="tls.example.com",
            certificate_path=Path("/etc/sing-box-manager/tls/server.crt"),
            key_path=Path("/etc/sing-box-manager/tls/server.key"),
        ),
    )

    report = CertificateDiagnosticsService(source=FailingCertificateSource()).inspect(
        ManagedInstallation(schema_version=1, revision=1, profiles=(profile,))
    )

    assert report.condition is CertificateDiagnosticCondition.ATTENTION
    assert report.summary == "无法检查托管证书有效期"
    assert report.diagnostics == "privileged helper timed out"


def test_mixed_certificate_failures_preserve_independent_evidence() -> None:
    missing_target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="missing.example.com",
        location=Path("/etc/sing-box-manager/tls/missing.crt"),
    )
    unavailable_target = CertificateTarget(
        kind=CertificateTargetKind.CERTMAGIC_ACME,
        server_name="unknown.example.com",
        location=Path("/var/lib/sing-box-manager/acme"),
    )
    source = RecordingCertificateSource(
        (
            CertificateObservation(
                target=missing_target,
                state=CertificateMaterialState.MISSING,
                source_label="operator file",
                diagnostics="file not found",
            ),
            CertificateObservation(
                target=unavailable_target,
                state=CertificateMaterialState.UNAVAILABLE,
                source_label="CertMagic ACME cache",
                diagnostics="permission denied",
            ),
        )
    )
    profiles = (
        ManagedProfile(
            profile_id="missing",
            profile_name="缺失证书",
            protocol=ProtocolKind.VLESS_TLS,
            listen_port=4433,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
            tls_intent=OperatorFileTlsIntent(
                server_name=missing_target.server_name,
                certificate_path=missing_target.location,
                key_path=Path("/etc/sing-box-manager/tls/missing.key"),
            ),
        ),
        ManagedProfile(
            profile_id="unknown",
            profile_name="状态未知",
            protocol=ProtocolKind.HYSTERIA2,
            listen_port=8443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
            tls_intent=AcmeTlsIntent(
                server_name=unavailable_target.server_name,
                email="operator@example.com",
                data_directory=unavailable_target.location,
            ),
        ),
    )

    report = CertificateDiagnosticsService(source=source).inspect(
        ManagedInstallation(schema_version=1, revision=1, profiles=profiles)
    )

    assert report.condition is CertificateDiagnosticCondition.ACTION_REQUIRED
    assert report.summary == "1 个托管证书材料缺失"
    assert "缺失证书" in report.diagnostics
    assert "状态未知" in report.diagnostics
    assert "permission denied" in report.diagnostics


def test_expired_certificate_has_priority_over_adjacent_unavailable_evidence() -> None:
    now = datetime(2026, 7, 17, tzinfo=timezone.utc)
    expired_target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="expired.example.com",
        location=Path("/etc/sing-box-manager/tls/expired.crt"),
    )
    unavailable_target = CertificateTarget(
        kind=CertificateTargetKind.CERTMAGIC_ACME,
        server_name="unknown.example.com",
        location=Path("/var/lib/sing-box-manager/acme"),
    )
    source = RecordingCertificateSource(
        (
            CertificateObservation(
                target=expired_target,
                state=CertificateMaterialState.AVAILABLE,
                source_label="operator file",
                diagnostics="",
                not_valid_before=now - timedelta(days=91),
                not_valid_after=now - timedelta(days=1),
                dns_names=(expired_target.server_name,),
            ),
            CertificateObservation(
                target=unavailable_target,
                state=CertificateMaterialState.UNAVAILABLE,
                source_label="CertMagic ACME cache",
                diagnostics="permission denied",
            ),
        )
    )
    profiles = (
        ManagedProfile(
            profile_id="expired",
            profile_name="已过期",
            protocol=ProtocolKind.VLESS_TLS,
            listen_port=4433,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
            tls_intent=OperatorFileTlsIntent(
                server_name=expired_target.server_name,
                certificate_path=expired_target.location,
                key_path=Path("/etc/sing-box-manager/tls/expired.key"),
            ),
        ),
        ManagedProfile(
            profile_id="unknown",
            profile_name="状态未知",
            protocol=ProtocolKind.HYSTERIA2,
            listen_port=8443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
            tls_intent=AcmeTlsIntent(
                server_name=unavailable_target.server_name,
                email="operator@example.com",
                data_directory=unavailable_target.location,
            ),
        ),
    )

    report = CertificateDiagnosticsService(source=source, now=lambda: now).inspect(
        ManagedInstallation(schema_version=1, revision=1, profiles=profiles)
    )

    assert report.condition is CertificateDiagnosticCondition.ACTION_REQUIRED
    assert report.summary == "1 个托管证书已过期"
    assert "已过期" in report.diagnostics
    assert "状态未知" in report.diagnostics
