from pathlib import Path

import pytest

from sb_manager.adapters.domain_resolution import BoundedSocketDomainResolutionInspector
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.domain_resolution import (
    DomainResolutionInspectionError,
    DomainResolutionResult,
)
from sb_manager.tls.catalog import AcmeTlsIntent


def profile(profile_id: str, server_address: str) -> ManagedProfile:
    return ManagedProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address=server_address,
    )


def test_public_domains_are_normalized_deduplicated_and_resolved_once() -> None:
    inspector = BoundedSocketDomainResolutionInspector(timeout_seconds=5)
    installation = ManagedInstallation(
        schema_version=1,
        revision=3,
        profiles=(
            profile("profile-1", "LOCALHOST."),
            profile("profile-2", "localhost"),
            profile("profile-3", "127.0.0.1"),
        ),
    )

    observation = inspector.inspect(installation)

    assert len(observation.results) == 1
    result = observation.results[0]
    assert result.domain == "localhost"
    assert result.error is None
    assert "127.0.0.1" in result.addresses or "::1" in result.addresses
    assert observation.skipped_ip_addresses == 1


def test_tls_server_name_is_checked_when_public_address_is_an_ip() -> None:
    inspector = BoundedSocketDomainResolutionInspector(timeout_seconds=5)
    tls_profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="profile-1",
        protocol=ProtocolKind.HYSTERIA2,
        listen_port=443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="127.0.0.1",
        tls_intent=AcmeTlsIntent(
            server_name="LOCALHOST.",
            email="operator@example.com",
            data_directory=Path("/var/lib/sing-box-manager/acme"),
        ),
    )

    observation = inspector.inspect(
        ManagedInstallation(schema_version=1, revision=1, profiles=(tls_profile,))
    )

    assert tuple(result.domain for result in observation.results) == ("localhost",)
    assert observation.results[0].error is None
    assert observation.skipped_ip_addresses == 1


def test_dns_worker_has_one_bounded_total_runtime() -> None:
    inspector = BoundedSocketDomainResolutionInspector(timeout_seconds=0)

    with pytest.raises(
        DomainResolutionInspectionError,
        match="Unable to resolve public domains",
    ):
        inspector.inspect(
            ManagedInstallation(
                schema_version=1,
                revision=1,
                profiles=(profile("profile-1", "localhost"),),
            )
        )


def test_resolution_result_cannot_mix_addresses_and_failure_evidence() -> None:
    with pytest.raises(ValueError, match="cannot contain both addresses and an error"):
        DomainResolutionResult(
            domain="proxy.example.com",
            addresses=("203.0.113.10",),
            error="temporary failure",
        )


def test_resolution_result_requires_addresses_or_failure_evidence() -> None:
    with pytest.raises(ValueError, match="requires addresses or an error"):
        DomainResolutionResult(
            domain="proxy.example.com",
            addresses=(),
            error=None,
        )


def test_repeated_ip_endpoints_are_counted_once() -> None:
    inspector = BoundedSocketDomainResolutionInspector(timeout_seconds=5)

    observation = inspector.inspect(
        ManagedInstallation(
            schema_version=1,
            revision=2,
            profiles=(
                profile("profile-1", "127.0.0.1"),
                profile("profile-2", "127.0.0.1"),
            ),
        )
    )

    assert observation.results == ()
    assert observation.skipped_ip_addresses == 1


def test_url_is_reported_as_invalid_domain_without_becoming_probe_failure() -> None:
    inspector = BoundedSocketDomainResolutionInspector(timeout_seconds=5)

    observation = inspector.inspect(
        ManagedInstallation(
            schema_version=1,
            revision=1,
            profiles=(profile("profile-1", "https://proxy.example.com"),),
        )
    )

    assert observation.results == (
        DomainResolutionResult(
            domain="https://proxy.example.com",
            addresses=(),
            error="invalid domain syntax",
        ),
    )
