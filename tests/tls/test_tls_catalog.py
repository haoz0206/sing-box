from pathlib import Path

import pytest

from sb_manager.tls.catalog import (
    AcmeTlsHandler,
    AcmeTlsIntent,
    OperatorFileTlsHandler,
    OperatorFileTlsIntent,
    TlsArtifacts,
    TlsCatalog,
    TlsClientPolicy,
    TlsMaterialError,
)


def test_catalog_materializes_a_shared_acme_certificate_provider(tmp_path: Path) -> None:
    catalog = TlsCatalog((AcmeTlsHandler(),))
    intent = AcmeTlsIntent(
        server_name="vpn.example.com",
        email="operator@example.com",
        data_directory=tmp_path / "acme",
    )

    artifacts = catalog.materialize(intent, tag="tls-profile-3")

    assert artifacts == TlsArtifacts(
        server={
            "enabled": True,
            "server_name": "vpn.example.com",
            "certificate_provider": "tls-profile-3",
        },
        certificate_providers=(
            {
                "type": "acme",
                "tag": "tls-profile-3",
                "domain": ["vpn.example.com"],
                "email": "operator@example.com",
                "data_directory": str(tmp_path / "acme"),
                "key_type": "p256",
            },
        ),
        client=TlsClientPolicy(
            server_name="vpn.example.com",
            insecure=False,
        ),
    )


def test_catalog_materializes_operator_provided_certificate_files(tmp_path: Path) -> None:
    certificate_path = tmp_path / "server.crt"
    key_path = tmp_path / "server.key"
    certificate_path.write_text(
        "-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    key_path.write_text(
        "-----BEGIN PRIVATE KEY-----\nfixture\n-----END PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    catalog = TlsCatalog((OperatorFileTlsHandler(),))
    intent = OperatorFileTlsIntent(
        server_name="vpn.example.com",
        certificate_path=certificate_path,
        key_path=key_path,
    )

    artifacts = catalog.materialize(intent, tag="unused-for-files")

    assert artifacts == TlsArtifacts(
        server={
            "enabled": True,
            "server_name": "vpn.example.com",
            "certificate_path": str(certificate_path),
            "key_path": str(key_path),
        },
        certificate_providers=(),
        client=TlsClientPolicy(
            server_name="vpn.example.com",
            insecure=False,
        ),
    )


def test_operator_certificate_reports_a_missing_private_key(tmp_path: Path) -> None:
    certificate_path = tmp_path / "server.crt"
    certificate_path.write_text(
        "-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    missing_key_path = tmp_path / "server.key"
    catalog = TlsCatalog((OperatorFileTlsHandler(),))

    with pytest.raises(TlsMaterialError) as caught:
        catalog.materialize(
            OperatorFileTlsIntent(
                server_name="vpn.example.com",
                certificate_path=certificate_path,
                key_path=missing_key_path,
            ),
            tag="unused-for-files",
        )

    assert caught.value.path == missing_key_path
    assert caught.value.role == "private-key"
