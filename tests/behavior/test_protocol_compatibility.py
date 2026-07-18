import pytest

from sb_manager.application.protocol_compatibility import (
    SNELL_V6_INTRODUCTION,
    ActiveCoreProtocolCompatibility,
    CoreTargetIncompatibleWithDesiredState,
    CoreVersionChanged,
    CoreVersionUnknown,
    ProtocolCompatibilityPolicy,
    ProtocolUnsupportedByCore,
)
from sb_manager.domain.installation import (
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.core_status import CoreStatusObservation


class StubCoreStatusInspector:
    def __init__(self, observation: CoreStatusObservation) -> None:
        self.observation = observation
        self.calls = 0

    def inspect(self) -> CoreStatusObservation:
        self.calls += 1
        return self.observation


@pytest.mark.parametrize(
    ("version", "supported"),
    (
        ("1.13.14", False),
        ("1.14.0-alpha.37", False),
        ("1.14.0-alpha.38", True),
        ("1.14.0-alpha.47", True),
        ("1.14.0-beta.1", True),
        ("1.14.0-rc.1", True),
        ("1.14.0", True),
        ("1.15.0-alpha.1", True),
        ("not-a-version", False),
    ),
)
def test_snell_v6_support_uses_the_exact_core_version_window(
    version: str,
    supported: bool,
) -> None:
    policy = ProtocolCompatibilityPolicy()

    assert policy.supports(ProtocolKind.SNELL_V6, version) is supported


@pytest.mark.parametrize(
    "protocol",
    tuple(protocol for protocol in ProtocolKind if protocol is not ProtocolKind.SNELL_V6),
)
def test_existing_protocols_do_not_depend_on_the_core_version(protocol: ProtocolKind) -> None:
    policy = ProtocolCompatibilityPolicy()

    assert policy.supports(protocol, "not-a-version") is True


def test_unsupported_protocol_error_is_structured_and_disclosure_safe() -> None:
    policy = ProtocolCompatibilityPolicy()
    secret_psk = "secret-psk"

    with pytest.raises(ProtocolUnsupportedByCore) as caught:
        policy.require_supported(ProtocolKind.SNELL_V6, "1.13.14")

    assert caught.value.protocol is ProtocolKind.SNELL_V6
    assert caught.value.observed_version == "1.13.14"
    assert caught.value.minimum_version == SNELL_V6_INTRODUCTION
    assert str(caught.value) == "snell-v6 requires 1.14.0-alpha.38; observed 1.13.14"
    assert secret_psk not in str(caught.value)


def test_guard_fails_closed_when_the_core_version_is_unavailable() -> None:
    inspector = StubCoreStatusInspector(
        CoreStatusObservation(
            available=False,
            version=None,
            diagnostics="secret diagnostic",
        )
    )
    guard = ActiveCoreProtocolCompatibility(inspector=inspector)

    with pytest.raises(CoreVersionUnknown) as caught:
        guard.require_protocol(ProtocolKind.SNELL_V6)

    assert caught.value.protocol is ProtocolKind.SNELL_V6
    assert caught.value.observed_version is None
    assert caught.value.minimum_version == SNELL_V6_INTRODUCTION
    assert str(caught.value) == "Core version is unavailable for snell-v6"
    assert "secret diagnostic" not in str(caught.value)


def test_guard_rejects_a_changed_capable_core_version() -> None:
    inspector = StubCoreStatusInspector(
        CoreStatusObservation(
            available=True,
            version="1.14.0-alpha.47",
            diagnostics="sing-box version 1.14.0-alpha.47",
        )
    )
    guard = ActiveCoreProtocolCompatibility(inspector=inspector)

    with pytest.raises(CoreVersionChanged) as caught:
        guard.require_protocol(
            ProtocolKind.SNELL_V6,
            expected_version="1.14.0-alpha.46",
        )

    assert caught.value.expected_version == "1.14.0-alpha.46"
    assert caught.value.observed_version == "1.14.0-alpha.47"
    assert str(caught.value) == ("Core version changed from 1.14.0-alpha.46 to 1.14.0-alpha.47")


def test_guard_checks_support_before_expected_version_identity() -> None:
    guard = ActiveCoreProtocolCompatibility(
        inspector=StubCoreStatusInspector(
            CoreStatusObservation(
                available=True,
                version="1.13.14",
                diagnostics="sing-box version 1.13.14",
            )
        )
    )

    with pytest.raises(ProtocolUnsupportedByCore):
        guard.require_protocol(ProtocolKind.SNELL_V6, expected_version="1.14.0-alpha.47")


def test_guard_does_not_inspect_the_core_for_existing_protocols() -> None:
    inspector = StubCoreStatusInspector(
        CoreStatusObservation(
            available=False,
            version=None,
            diagnostics="core unavailable",
        )
    )
    guard = ActiveCoreProtocolCompatibility(inspector=inspector)

    assert guard.require_protocol(ProtocolKind.VLESS_REALITY) is None
    assert inspector.calls == 0


def test_policy_reports_only_enabled_applied_profiles_blocked_by_a_target() -> None:
    policy = ProtocolCompatibilityPolicy()
    blocking = ManagedProfile(
        profile_id="profile-1",
        profile_name="Snell primary",
        protocol=ProtocolKind.SNELL_V6,
        listen_port=18443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    profiles = (
        blocking,
        ManagedProfile(
            profile_id="profile-2",
            profile_name="Snell paused",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18444,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
            enabled=False,
        ),
        ManagedProfile(
            profile_id="profile-3",
            profile_name="Snell draft",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18445,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
        ),
        ManagedProfile(
            profile_id="profile-4",
            profile_name="Reality",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
        ),
    )

    assert policy.blocking_profiles(profiles, target_version="1.13.14") == (blocking,)


def test_policy_rejects_a_target_with_structured_blocking_profile_identity() -> None:
    policy = ProtocolCompatibilityPolicy()
    profiles = (
        ManagedProfile(
            profile_id="profile-secret-id",
            profile_name="secret profile name",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
        ),
    )

    with pytest.raises(CoreTargetIncompatibleWithDesiredState) as caught:
        policy.require_profiles_supported(profiles, target_version="1.13.14")

    assert caught.value.target_version == "1.13.14"
    assert caught.value.blocking_profile_ids == ("profile-secret-id",)
    assert caught.value.blocking_profile_names == ("secret profile name",)
    assert str(caught.value) == "Core 1.13.14 is incompatible with applied profiles"
    assert "secret" not in str(caught.value)


def test_profile_guard_inspects_only_when_an_active_snell_profile_exists() -> None:
    inspector = StubCoreStatusInspector(
        CoreStatusObservation(
            available=True,
            version="1.14.0-alpha.47",
            diagnostics="sing-box version 1.14.0-alpha.47",
        )
    )
    guard = ActiveCoreProtocolCompatibility(inspector=inspector)
    nonblocking = (
        ManagedProfile(
            profile_id="profile-1",
            profile_name="Snell paused",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
            enabled=False,
        ),
        ManagedProfile(
            profile_id="profile-2",
            profile_name="Reality",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
        ),
    )

    assert guard.require_profiles(nonblocking) is None
    assert inspector.calls == 0


def test_profile_guard_returns_the_observed_version_for_active_snell_profiles() -> None:
    inspector = StubCoreStatusInspector(
        CoreStatusObservation(
            available=True,
            version="1.14.0-alpha.47",
            diagnostics="sing-box version 1.14.0-alpha.47",
        )
    )
    guard = ActiveCoreProtocolCompatibility(inspector=inspector)
    profiles = (
        ManagedProfile(
            profile_id="profile-1",
            profile_name="Snell",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.APPLIED,
        ),
    )

    assert guard.require_profiles(profiles, expected_version="1.14.0-alpha.47") == "1.14.0-alpha.47"
    assert inspector.calls == 1
