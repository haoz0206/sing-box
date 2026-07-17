from datetime import datetime, timezone
from pathlib import Path

import pytest

from sb_manager.seams.certificate_source import (
    CertificateMaterialState,
    CertificateObservation,
    CertificateTarget,
    CertificateTargetKind,
)


def test_available_certificate_requires_complete_timezone_aware_validity() -> None:
    target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="proxy.example.com",
        location=Path("/etc/sing-box-manager/tls/proxy.crt"),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        CertificateObservation(
            target=target,
            state=CertificateMaterialState.AVAILABLE,
            source_label="operator file",
            diagnostics="",
            not_valid_before=datetime(2026, 7, 1),
            not_valid_after=datetime(2026, 10, 1, tzinfo=timezone.utc),
            dns_names=("proxy.example.com",),
        )


def test_unavailable_certificate_cannot_claim_validity_evidence() -> None:
    target = CertificateTarget(
        kind=CertificateTargetKind.CERTMAGIC_ACME,
        server_name="proxy.example.com",
        location=Path("/var/lib/sing-box-manager/acme"),
    )

    with pytest.raises(ValueError, match="must not include validity"):
        CertificateObservation(
            target=target,
            state=CertificateMaterialState.UNAVAILABLE,
            source_label="CertMagic ACME cache",
            diagnostics="permission denied",
            not_valid_before=datetime(2026, 7, 1, tzinfo=timezone.utc),
            not_valid_after=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
