"""Versioned JSON protocol for the single-shot privileged helper."""

import json
from collections.abc import Iterable
from typing import Protocol

from sb_manager.artifacts.installation import CoreActivation
from sb_manager.privileged.config_apply import ApplyConfigRequest
from sb_manager.privileged.core_install import ActivateCoreRequest
from sb_manager.seams.artifact_source import ArtifactArchitecture, CoreArtifactRequest
from sb_manager.transactions.apply import ApplyOutcome, ApplyTransactionResult

REQUEST_SCHEMA_VERSION = 1
MAX_REQUEST_BYTES = 16 * 1024
SHA256_HEX_LENGTH = 64
ACTIVATE_CORE_FIELDS = {
    "schema_version",
    "operation",
    "version",
    "architecture",
    "sha256",
}
APPLY_CONFIG_FIELDS = {
    "schema_version",
    "operation",
    "sha256",
}


class PrivilegeRequiredError(PermissionError):
    """The helper process is not running with effective root privileges."""


class PrivilegedProtocolError(ValueError):
    """A helper request does not match the exact allowlisted schema."""


class CoreActivator(Protocol):
    def activate_core(self, request: ActivateCoreRequest) -> CoreActivation: ...


class ConfigApplier(Protocol):
    def apply_config(self, request: ApplyConfigRequest) -> ApplyTransactionResult: ...


def execute_privileged_request(
    request_text: str,
    *,
    effective_user_id: int,
    core_activator: CoreActivator,
    config_applier: ConfigApplier | None = None,
) -> str:
    """Authorize, parse, execute, and serialize one privileged operation."""
    if effective_user_id != 0:
        raise PrivilegeRequiredError("Privileged helper must run as root")
    if len(request_text.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise PrivilegedProtocolError(f"Request exceeds {MAX_REQUEST_BYTES} bytes")

    try:
        raw_request = json.loads(request_text, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as error:
        raise PrivilegedProtocolError(f"Request is not valid JSON: {error.msg}") from error
    if not isinstance(raw_request, dict):
        raise PrivilegedProtocolError("Request must be a JSON object")
    operation = raw_request.get("operation")
    expected_fields = (
        {
            "activate-core": ACTIVATE_CORE_FIELDS,
            "apply-config": APPLY_CONFIG_FIELDS,
        }.get(operation)
        if isinstance(operation, str)
        else None
    )
    if expected_fields is None:
        raise PrivilegedProtocolError(f"Unsupported operation: {operation!r}")
    if set(raw_request) != expected_fields:
        raise PrivilegedProtocolError(f"Request fields must be exactly {sorted(expected_fields)}")
    schema_version = raw_request["schema_version"]
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != REQUEST_SCHEMA_VERSION
    ):
        raise PrivilegedProtocolError(f"Unsupported privileged schema version: {schema_version!r}")
    sha256 = _required_sha256(raw_request)
    if operation == "apply-config":
        if config_applier is None:
            raise PrivilegedProtocolError("apply-config operation is not available")
        return _serialize_config_result(
            config_applier.apply_config(ApplyConfigRequest(sha256=sha256))
        )

    version = _required_string(raw_request, "version")
    architecture_value = _required_string(raw_request, "architecture")
    try:
        architecture = ArtifactArchitecture(architecture_value)
        CoreArtifactRequest(version=version, architecture=architecture)
    except ValueError as error:
        raise PrivilegedProtocolError(str(error)) from error
    activation = core_activator.activate_core(
        ActivateCoreRequest(
            version=version,
            architecture=architecture,
            sha256=sha256,
        )
    )
    return json.dumps(
        {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "status": "activated",
            "version": activation.version,
            "binary_path": str(activation.binary_path),
            "previous_target": activation.previous_target,
        },
        sort_keys=True,
    )


def _unique_object(pairs: Iterable[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PrivilegedProtocolError(f"Request contains duplicate field: {key}")
        result[key] = value
    return result


def _required_string(request: dict[str, object], field: str) -> str:
    value = request[field]
    if not isinstance(value, str):
        raise PrivilegedProtocolError(f"Request field {field} must be a string")
    return value


def _required_sha256(request: dict[str, object]) -> str:
    sha256 = _required_string(request, "sha256")
    if len(sha256) != SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in sha256
    ):
        raise PrivilegedProtocolError("SHA-256 must be 64 lowercase hex characters")
    return sha256


def _serialize_config_result(result: ApplyTransactionResult) -> str:
    return json.dumps(
        {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "status": "applied" if result.outcome is ApplyOutcome.APPLIED else "rejected",
            "transaction": {
                "outcome": result.outcome.value,
                "validation": {
                    "valid": result.validation.valid,
                    "diagnostics": result.validation.diagnostics,
                },
                "commit": (
                    {
                        "success": result.commit.success,
                        "diagnostics": result.commit.diagnostics,
                    }
                    if result.commit is not None
                    else None
                ),
                "runtime_refresh": (
                    {
                        "success": result.runtime_refresh.success,
                        "diagnostics": result.runtime_refresh.diagnostics,
                    }
                    if result.runtime_refresh is not None
                    else None
                ),
                "postcondition": (
                    {
                        "healthy": result.postcondition.healthy,
                        "diagnostics": result.postcondition.diagnostics,
                    }
                    if result.postcondition is not None
                    else None
                ),
                "rollback": (
                    {
                        "success": result.rollback.success,
                        "diagnostics": result.rollback.diagnostics,
                        "recovery_instructions": list(result.rollback.recovery_instructions),
                    }
                    if result.rollback is not None
                    else None
                ),
            },
        },
        sort_keys=True,
    )
