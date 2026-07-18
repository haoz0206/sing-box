import json
from collections.abc import Collection
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sb_manager.artifacts.installation import CoreActivation, CoreReleaseIdentity
from sb_manager.privileged.config_apply import ApplyConfigRequest
from sb_manager.privileged.protocol import (
    PrivilegedProtocolError,
    PrivilegeRequiredError,
    execute_privileged_request,
)
from sb_manager.seams.artifact_source import ArtifactArchitecture
from sb_manager.seams.certificate_source import (
    CertificateInspection,
    CertificateMaterialState,
    CertificateObservation,
    CertificateTarget,
    CertificateTargetKind,
)
from sb_manager.seams.config_target import LiveConfigObservation
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.core_activator import CoreActivationRequest
from sb_manager.seams.core_switcher import CoreSwitchRequest
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import ApplyOutcome, ApplyTransactionResult, CommitResult


class RecordingCoreActivator:
    def __init__(self) -> None:
        self.requests: list[CoreActivationRequest] = []

    def activate_core(self, request: CoreActivationRequest) -> CoreActivation:
        self.requests.append(request)
        return CoreActivation(
            version=request.version,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/release"),
            binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
            activated_target="versions/release",
            previous_target=None,
        )


class RecordingCoreSwitcher:
    def __init__(self) -> None:
        self.requests: list[CoreSwitchRequest] = []

    def switch_core(self, request: CoreSwitchRequest) -> CoreActivation:
        self.requests.append(request)
        return CoreActivation(
            version=request.target.version,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/stable"),
            binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
            activated_target="versions/stable",
            previous_target="versions/preview",
        )


class RecordingConfigApplier:
    def __init__(self) -> None:
        self.requests: list[ApplyConfigRequest] = []

    def apply_config(self, request: ApplyConfigRequest) -> ApplyTransactionResult:
        self.requests.append(request)
        return ApplyTransactionResult(
            outcome=ApplyOutcome.APPLIED,
            validation=ConfigValidationResult(valid=True, diagnostics="configuration valid"),
            runtime_refresh=RuntimeRefreshResult(
                success=True,
                diagnostics="service refreshed",
            ),
            postcondition=RuntimePostcondition(
                healthy=True,
                diagnostics="service active",
            ),
            rollback=None,
            commit=CommitResult(success=True, diagnostics="configuration committed"),
        )


class RecordingConfigInspector:
    def __init__(self) -> None:
        self.inspections = 0

    def inspect(self) -> LiveConfigObservation:
        self.inspections += 1
        return LiveConfigObservation(exists=True, sha256="c" * 64)


class RecordingCertificateSource:
    def __init__(self) -> None:
        self.targets: tuple[CertificateTarget, ...] = ()

    def inspect(self, targets: Collection[CertificateTarget]) -> CertificateInspection:
        self.targets = tuple(targets)
        target = self.targets[0]
        return CertificateInspection(
            observations=(
                CertificateObservation(
                    target=target,
                    state=CertificateMaterialState.AVAILABLE,
                    source_label="operator file",
                    diagnostics="Leaf public certificate decoded",
                    not_valid_before=datetime(2026, 7, 1, tzinfo=timezone.utc),
                    not_valid_after=datetime(2026, 10, 1, tzinfo=timezone.utc),
                    dns_names=("proxy.example.com",),
                ),
            )
        )


def valid_request_json() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "operation": "activate-core",
            "version": "1.14.0-alpha.45",
            "architecture": "amd64",
            "sha256": "a" * 64,
        }
    )


def test_root_request_executes_one_allowlisted_operation_and_returns_redacted_json() -> None:
    activator = RecordingCoreActivator()

    result = execute_privileged_request(
        valid_request_json(),
        effective_user_id=0,
        core_activator=activator,
    )

    assert activator.requests == [
        CoreActivationRequest(
            version="1.14.0-alpha.45",
            architecture=ArtifactArchitecture.AMD64,
            sha256="a" * 64,
        )
    ]
    assert json.loads(result) == {
        "schema_version": 1,
        "status": "activated",
        "activation": {
            "version": "1.14.0-alpha.45",
            "distribution_directory": "/opt/sing-box-manager/core/versions/release",
            "binary_path": "/opt/sing-box-manager/core/current/sing-box",
            "activated_target": "versions/release",
            "previous_target": None,
        },
    }


def test_root_switch_request_accepts_only_exact_release_identities() -> None:
    switcher = RecordingCoreSwitcher()

    result = execute_privileged_request(
        json.dumps(
            {
                "schema_version": 1,
                "operation": "switch-core",
                "target": {
                    "version": "1.13.14",
                    "architecture": "amd64",
                    "sha256": "a" * 64,
                },
                "expected_active": {
                    "version": "1.14.0-alpha.46",
                    "architecture": "amd64",
                    "sha256": "b" * 64,
                },
            }
        ),
        effective_user_id=0,
        core_activator=RecordingCoreActivator(),
        core_switcher=switcher,
    )

    assert switcher.requests == [
        CoreSwitchRequest(
            target=CoreReleaseIdentity(
                version="1.13.14",
                architecture=ArtifactArchitecture.AMD64,
                source_sha256="a" * 64,
            ),
            expected_active=CoreReleaseIdentity(
                version="1.14.0-alpha.46",
                architecture=ArtifactArchitecture.AMD64,
                source_sha256="b" * 64,
            ),
        )
    ]
    assert json.loads(result) == {
        "schema_version": 1,
        "status": "switched",
        "activation": {
            "version": "1.13.14",
            "distribution_directory": "/opt/sing-box-manager/core/versions/stable",
            "binary_path": "/opt/sing-box-manager/core/current/sing-box",
            "activated_target": "versions/stable",
            "previous_target": "versions/preview",
        },
    }


def test_non_root_request_is_rejected_before_service_invocation() -> None:
    activator = RecordingCoreActivator()

    with pytest.raises(PrivilegeRequiredError, match="root"):
        execute_privileged_request(
            valid_request_json(),
            effective_user_id=1000,
            core_activator=activator,
        )

    assert activator.requests == []


def test_apply_config_request_cannot_select_host_policy_and_returns_outcome() -> None:
    applier = RecordingConfigApplier()
    sha256 = "b" * 64

    result = execute_privileged_request(
        json.dumps(
            {
                "schema_version": 1,
                "operation": "apply-config",
                "sha256": sha256,
                "expected_config_sha256": None,
            }
        ),
        effective_user_id=0,
        core_activator=RecordingCoreActivator(),
        config_applier=applier,
    )

    assert applier.requests == [ApplyConfigRequest(sha256=sha256, expected_config_sha256=None)]
    assert json.loads(result) == {
        "schema_version": 1,
        "status": "applied",
        "transaction": {
            "outcome": "applied",
            "validation": {"valid": True, "diagnostics": "configuration valid"},
            "commit": {"success": True, "diagnostics": "configuration committed"},
            "runtime_refresh": {"success": True, "diagnostics": "service refreshed"},
            "postcondition": {"healthy": True, "diagnostics": "service active"},
            "rollback": None,
        },
    }


def test_inspect_config_returns_only_existence_and_fingerprint() -> None:
    inspector = RecordingConfigInspector()

    result = execute_privileged_request(
        json.dumps({"schema_version": 1, "operation": "inspect-config"}),
        effective_user_id=0,
        core_activator=RecordingCoreActivator(),
        config_inspector=inspector,
    )

    assert inspector.inspections == 1
    assert json.loads(result) == {
        "schema_version": 1,
        "status": "observed",
        "config": {"exists": True, "sha256": "c" * 64},
    }


def test_inspect_certificates_returns_only_public_validity_evidence() -> None:
    source = RecordingCertificateSource()

    result = execute_privileged_request(
        json.dumps(
            {
                "schema_version": 1,
                "operation": "inspect-certificates",
                "targets": [
                    {
                        "kind": "operator-file",
                        "server_name": "proxy.example.com",
                        "location": "/etc/sing-box-manager/tls/proxy.crt",
                    }
                ],
            }
        ),
        effective_user_id=0,
        core_activator=RecordingCoreActivator(),
        certificate_source=source,
    )

    assert source.targets == (
        CertificateTarget(
            kind=CertificateTargetKind.OPERATOR_FILE,
            server_name="proxy.example.com",
            location=Path("/etc/sing-box-manager/tls/proxy.crt"),
        ),
    )
    assert json.loads(result) == {
        "schema_version": 1,
        "status": "observed",
        "observations": [
            {
                "target": {
                    "kind": "operator-file",
                    "server_name": "proxy.example.com",
                    "location": "/etc/sing-box-manager/tls/proxy.crt",
                },
                "state": "available",
                "source_label": "operator file",
                "diagnostics": "Leaf public certificate decoded",
                "not_valid_before": "2026-07-01T00:00:00+00:00",
                "not_valid_after": "2026-10-01T00:00:00+00:00",
                "dns_names": ["proxy.example.com"],
            }
        ],
    }


@pytest.mark.parametrize(
    "target",
    (
        {
            "kind": "operator-file",
            "server_name": "proxy.example.com",
            "location": "relative/proxy.crt",
        },
        {
            "kind": "operator-file",
            "server_name": "proxy.example.com",
            "location": "/etc/sing-box-manager/tls/proxy.crt",
            "key_path": "/etc/sing-box-manager/tls/proxy.key",
        },
    ),
)
def test_inspect_certificates_rejects_relative_locations_and_private_key_fields(
    target: dict[str, object],
) -> None:
    source = RecordingCertificateSource()

    with pytest.raises(PrivilegedProtocolError):
        execute_privileged_request(
            json.dumps(
                {
                    "schema_version": 1,
                    "operation": "inspect-certificates",
                    "targets": [target],
                }
            ),
            effective_user_id=0,
            core_activator=RecordingCoreActivator(),
            certificate_source=source,
        )

    assert source.targets == ()


@pytest.mark.parametrize(
    "document",
    (
        {
            "schema_version": True,
            "operation": "activate-core",
            "version": "1.14.0",
            "architecture": "amd64",
            "sha256": "a" * 64,
        },
        {
            "schema_version": 2,
            "operation": "activate-core",
            "version": "1.14.0",
            "architecture": "amd64",
            "sha256": "a" * 64,
        },
        {
            "schema_version": 1,
            "operation": "run-command",
            "version": "1.14.0",
            "architecture": "amd64",
            "sha256": "a" * 64,
        },
        {
            "schema_version": 1,
            "operation": "activate-core",
            "version": "1.14.0",
            "architecture": "amd64",
            "sha256": "a" * 64,
            "target": "/tmp/attacker-selected",
        },
    ),
)
def test_unknown_schema_operation_or_field_is_rejected(document: dict[str, object]) -> None:
    with pytest.raises(PrivilegedProtocolError):
        execute_privileged_request(
            json.dumps(document),
            effective_user_id=0,
            core_activator=RecordingCoreActivator(),
        )


def test_duplicate_json_fields_are_rejected() -> None:
    request = (
        '{"schema_version":1,"operation":"activate-core",'
        '"version":"1.14.0","architecture":"amd64",'
        f'"sha256":"{"a" * 64}","sha256":"{"b" * 64}"}}'
    )

    with pytest.raises(PrivilegedProtocolError, match="duplicate"):
        execute_privileged_request(
            request,
            effective_user_id=0,
            core_activator=RecordingCoreActivator(),
        )
