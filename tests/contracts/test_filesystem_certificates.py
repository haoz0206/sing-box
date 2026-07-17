from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from sb_manager.adapters.filesystem_certificates import FilesystemCertificateSource
from sb_manager.seams.certificate_source import (
    CertificateMaterialState,
    CertificateTarget,
    CertificateTargetKind,
)


def write_certificate(
    path: Path,
    *,
    server_name: str,
    not_valid_before: datetime,
    not_valid_after: datetime,
) -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, server_name)])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(1001)
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(server_name)]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))


def test_operator_certificate_returns_only_public_validity_evidence(tmp_path: Path) -> None:
    trusted_root = tmp_path / "tls"
    certificate_path = trusted_root / "server.crt"
    not_valid_before = datetime(2026, 7, 1, tzinfo=timezone.utc)
    not_valid_after = datetime(2026, 10, 1, tzinfo=timezone.utc)
    write_certificate(
        certificate_path,
        server_name="proxy.example.com",
        not_valid_before=not_valid_before,
        not_valid_after=not_valid_after,
    )
    target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="proxy.example.com",
        location=certificate_path,
    )

    inspection = FilesystemCertificateSource(trusted_roots=(trusted_root,)).inspect((target,))

    assert len(inspection.observations) == 1
    observation = inspection.observations[0]
    assert observation.state is CertificateMaterialState.AVAILABLE
    assert observation.not_valid_before == not_valid_before
    assert observation.not_valid_after == not_valid_after
    assert observation.dns_names == ("proxy.example.com",)
    assert "PRIVATE KEY" not in observation.diagnostics


def test_certmagic_cache_finds_matching_acme_leaf_without_reading_keys(
    tmp_path: Path,
) -> None:
    acme_root = tmp_path / "acme"
    certificate_path = (
        acme_root
        / "certificates"
        / "acme-v02.api.letsencrypt.org-directory"
        / "proxy.example.com"
        / "proxy.example.com.crt"
    )
    not_valid_before = datetime(2026, 7, 1, tzinfo=timezone.utc)
    not_valid_after = datetime(2026, 9, 29, tzinfo=timezone.utc)
    write_certificate(
        certificate_path,
        server_name="proxy.example.com",
        not_valid_before=not_valid_before,
        not_valid_after=not_valid_after,
    )
    (certificate_path.parent / "proxy.example.com.key").write_text(
        "DO NOT READ",
        encoding="utf-8",
    )
    target = CertificateTarget(
        kind=CertificateTargetKind.CERTMAGIC_ACME,
        server_name="proxy.example.com",
        location=acme_root,
    )

    inspection = FilesystemCertificateSource(trusted_roots=(acme_root,)).inspect((target,))

    observation = inspection.observations[0]
    assert observation.state is CertificateMaterialState.AVAILABLE
    assert observation.source_label == "CertMagic ACME cache"
    assert observation.not_valid_after == not_valid_after
    assert "DO NOT READ" not in observation.diagnostics


def test_operator_certificate_symlink_cannot_escape_trusted_root(tmp_path: Path) -> None:
    trusted_root = tmp_path / "tls"
    trusted_root.mkdir()
    external_certificate = tmp_path / "external.crt"
    write_certificate(
        external_certificate,
        server_name="proxy.example.com",
        not_valid_before=datetime(2026, 7, 1, tzinfo=timezone.utc),
        not_valid_after=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    certificate_path = trusted_root / "proxy.crt"
    certificate_path.symlink_to(external_certificate)
    target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="proxy.example.com",
        location=certificate_path,
    )

    observation = (
        FilesystemCertificateSource(trusted_roots=(trusted_root,))
        .inspect((target,))
        .observations[0]
    )

    assert observation.state is CertificateMaterialState.UNAVAILABLE
    assert "symbolic link" in observation.diagnostics
    assert "BEGIN CERTIFICATE" not in observation.diagnostics


def test_operator_certificate_must_cover_declared_server_name(tmp_path: Path) -> None:
    trusted_root = tmp_path / "tls"
    certificate_path = trusted_root / "proxy.crt"
    write_certificate(
        certificate_path,
        server_name="other.example.com",
        not_valid_before=datetime(2026, 7, 1, tzinfo=timezone.utc),
        not_valid_after=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="proxy.example.com",
        location=certificate_path,
    )

    observation = (
        FilesystemCertificateSource(trusted_roots=(trusted_root,))
        .inspect((target,))
        .observations[0]
    )

    assert observation.state is CertificateMaterialState.INVALID
    assert "does not cover" in observation.diagnostics


def test_certmagic_cache_selects_latest_matching_public_leaf(tmp_path: Path) -> None:
    acme_root = tmp_path / "acme"
    first = acme_root / "certificates" / "issuer-one" / "proxy" / "proxy.crt"
    latest = acme_root / "certificates" / "issuer-two" / "proxy" / "proxy.crt"
    write_certificate(
        first,
        server_name="proxy.example.com",
        not_valid_before=datetime(2026, 6, 1, tzinfo=timezone.utc),
        not_valid_after=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    write_certificate(
        latest,
        server_name="proxy.example.com",
        not_valid_before=datetime(2026, 7, 1, tzinfo=timezone.utc),
        not_valid_after=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    write_certificate(
        acme_root / "certificates" / "issuer" / "other" / "other.crt",
        server_name="other.example.com",
        not_valid_before=datetime(2026, 7, 1, tzinfo=timezone.utc),
        not_valid_after=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    target = CertificateTarget(
        kind=CertificateTargetKind.CERTMAGIC_ACME,
        server_name="proxy.example.com",
        location=acme_root,
    )

    observation = (
        FilesystemCertificateSource(trusted_roots=(acme_root,)).inspect((target,)).observations[0]
    )

    assert observation.state is CertificateMaterialState.AVAILABLE
    assert observation.not_valid_after == datetime(2026, 10, 1, tzinfo=timezone.utc)
