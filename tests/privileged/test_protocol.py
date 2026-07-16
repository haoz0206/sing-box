import json
from pathlib import Path

import pytest

from sb_manager.artifacts.installation import CoreActivation
from sb_manager.privileged.config_apply import ApplyConfigRequest
from sb_manager.privileged.core_install import ActivateCoreRequest
from sb_manager.privileged.protocol import (
    PrivilegedProtocolError,
    PrivilegeRequiredError,
    execute_privileged_request,
)
from sb_manager.seams.artifact_source import ArtifactArchitecture
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import ApplyOutcome, ApplyTransactionResult, CommitResult


class RecordingCoreActivator:
    def __init__(self) -> None:
        self.requests: list[ActivateCoreRequest] = []

    def activate_core(self, request: ActivateCoreRequest) -> CoreActivation:
        self.requests.append(request)
        return CoreActivation(
            version=request.version,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/release"),
            binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
            activated_target="versions/release",
            previous_target=None,
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
        ActivateCoreRequest(
            version="1.14.0-alpha.45",
            architecture=ArtifactArchitecture.AMD64,
            sha256="a" * 64,
        )
    ]
    assert json.loads(result) == {
        "schema_version": 1,
        "status": "activated",
        "version": "1.14.0-alpha.45",
        "binary_path": "/opt/sing-box-manager/core/current/sing-box",
        "previous_target": None,
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
            }
        ),
        effective_user_id=0,
        core_activator=RecordingCoreActivator(),
        config_applier=applier,
    )

    assert applier.requests == [ApplyConfigRequest(sha256=sha256)]
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
