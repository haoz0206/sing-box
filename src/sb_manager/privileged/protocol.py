"""Versioned JSON protocol for the single-shot privileged helper."""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from sb_manager.artifacts.installation import CoreActivation, CoreReleaseIdentity
from sb_manager.privileged.config_apply import ApplyConfigRequest
from sb_manager.seams.artifact_source import ArtifactArchitecture, CoreArtifactRequest
from sb_manager.seams.certificate_source import (
    CertificateInspection,
    CertificateSource,
    CertificateTarget,
    CertificateTargetKind,
)
from sb_manager.seams.config_target import (
    ConfigurationTargetInspector,
    LiveConfigObservation,
)
from sb_manager.seams.core_activator import CoreActivationRequest
from sb_manager.seams.core_switcher import CoreSwitcher, CoreSwitchRequest
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
SWITCH_CORE_FIELDS = {"schema_version", "operation", "target", "expected_active"}
CORE_IDENTITY_FIELDS = {"version", "architecture", "sha256"}
APPLY_CONFIG_FIELDS = {
    "schema_version",
    "operation",
    "sha256",
    "expected_config_sha256",
}
INSPECT_CONFIG_FIELDS = {"schema_version", "operation"}
INSPECT_CERTIFICATES_FIELDS = {"schema_version", "operation", "targets"}
CERTIFICATE_TARGET_FIELDS = {"kind", "server_name", "location"}
MAX_CERTIFICATE_TARGETS = 64


class PrivilegeRequiredError(PermissionError):
    """The helper process is not running with effective root privileges."""


class PrivilegedProtocolError(ValueError):
    """A helper request does not match the exact allowlisted schema."""


class CoreActivator(Protocol):
    def activate_core(self, request: CoreActivationRequest) -> CoreActivation: ...


class ConfigApplier(Protocol):
    def apply_config(self, request: ApplyConfigRequest) -> ApplyTransactionResult: ...


def execute_privileged_request(  # noqa: PLR0912, PLR0913 - allowlisted operation dispatcher
    request_text: str,
    *,
    effective_user_id: int,
    core_activator: CoreActivator,
    core_switcher: CoreSwitcher | None = None,
    config_applier: ConfigApplier | None = None,
    config_inspector: ConfigurationTargetInspector | None = None,
    certificate_source: CertificateSource | None = None,
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
            "switch-core": SWITCH_CORE_FIELDS,
            "apply-config": APPLY_CONFIG_FIELDS,
            "inspect-config": INSPECT_CONFIG_FIELDS,
            "inspect-certificates": INSPECT_CERTIFICATES_FIELDS,
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
    if operation == "inspect-config":
        if config_inspector is None:
            raise PrivilegedProtocolError("inspect-config operation is not available")
        return _serialize_config_observation(config_inspector.inspect())
    if operation == "inspect-certificates":
        if certificate_source is None:
            raise PrivilegedProtocolError("inspect-certificates operation is not available")
        targets = _certificate_targets(raw_request["targets"])
        return _serialize_certificate_inspection(certificate_source.inspect(targets))
    if operation == "switch-core":
        if core_switcher is None:
            raise PrivilegedProtocolError("switch-core operation is not available")
        activation = core_switcher.switch_core(
            CoreSwitchRequest(
                target=_core_identity(raw_request["target"], role="target"),
                expected_active=_core_identity(
                    raw_request["expected_active"],
                    role="expected_active",
                ),
            )
        )
        return _serialize_core_activation(activation, status="switched")

    sha256 = _required_sha256(raw_request)
    if operation == "apply-config":
        if config_applier is None:
            raise PrivilegedProtocolError("apply-config operation is not available")
        return _serialize_config_result(
            config_applier.apply_config(
                ApplyConfigRequest(
                    sha256=sha256,
                    expected_config_sha256=_optional_sha256(
                        raw_request,
                        "expected_config_sha256",
                    ),
                )
            )
        )

    version = _required_string(raw_request, "version")
    architecture_value = _required_string(raw_request, "architecture")
    try:
        architecture = ArtifactArchitecture(architecture_value)
        CoreArtifactRequest(version=version, architecture=architecture)
    except ValueError as error:
        raise PrivilegedProtocolError(str(error)) from error
    activation = core_activator.activate_core(
        CoreActivationRequest(
            version=version,
            architecture=architecture,
            sha256=sha256,
        )
    )
    return _serialize_core_activation(activation, status="activated")


def _serialize_core_activation(activation: CoreActivation, *, status: str) -> str:
    return json.dumps(
        {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "status": status,
            "activation": {
                "version": activation.version,
                "distribution_directory": str(activation.distribution_directory),
                "binary_path": str(activation.binary_path),
                "activated_target": activation.activated_target,
                "previous_target": activation.previous_target,
            },
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


def _optional_sha256(request: dict[str, object], field: str) -> str | None:
    value = request[field]
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) != SHA256_HEX_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PrivilegedProtocolError(
            f"Request field {field} must be null or 64 lowercase hex characters"
        )
    return value


def _core_identity(value: object, *, role: str) -> CoreReleaseIdentity:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PrivilegedProtocolError(f"Core {role} identity must be an object")
    if set(value) != CORE_IDENTITY_FIELDS:
        raise PrivilegedProtocolError(
            f"Core {role} identity fields must be exactly {sorted(CORE_IDENTITY_FIELDS)}"
        )
    version = _required_string(value, "version")
    architecture_value = _required_string(value, "architecture")
    sha256 = _required_sha256(value)
    try:
        architecture = ArtifactArchitecture(architecture_value)
        CoreArtifactRequest(version=version, architecture=architecture)
    except ValueError as error:
        raise PrivilegedProtocolError(str(error)) from error
    return CoreReleaseIdentity(
        version=version,
        architecture=architecture,
        source_sha256=sha256,
    )


def _certificate_targets(value: object) -> tuple[CertificateTarget, ...]:
    if not isinstance(value, list):
        raise PrivilegedProtocolError("Request field targets must be a list")
    if not value or len(value) > MAX_CERTIFICATE_TARGETS:
        raise PrivilegedProtocolError(
            f"Request field targets must contain 1 to {MAX_CERTIFICATE_TARGETS} items"
        )
    targets = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or not all(isinstance(key, str) for key in item):
            raise PrivilegedProtocolError(f"Certificate target {index} must be an object")
        if set(item) != CERTIFICATE_TARGET_FIELDS:
            raise PrivilegedProtocolError(
                f"Certificate target fields must be exactly {sorted(CERTIFICATE_TARGET_FIELDS)}"
            )
        kind_value = item["kind"]
        server_name = item["server_name"]
        location_value = item["location"]
        if not isinstance(kind_value, str):
            raise PrivilegedProtocolError("Certificate target kind must be a string")
        if not isinstance(server_name, str) or not server_name:
            raise PrivilegedProtocolError(
                "Certificate target server_name must be a non-empty string"
            )
        if not isinstance(location_value, str):
            raise PrivilegedProtocolError("Certificate target location must be a string")
        location = Path(location_value)
        if not location.is_absolute():
            raise PrivilegedProtocolError("Certificate target location must be absolute")
        try:
            kind = CertificateTargetKind(kind_value)
        except ValueError as error:
            raise PrivilegedProtocolError(
                f"Unsupported certificate target kind: {kind_value!r}"
            ) from error
        targets.append(CertificateTarget(kind=kind, server_name=server_name, location=location))
    if len(set(targets)) != len(targets):
        raise PrivilegedProtocolError("Certificate targets must not contain duplicates")
    return tuple(targets)


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


def _serialize_config_observation(observation: LiveConfigObservation) -> str:
    return json.dumps(
        {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "status": "observed",
            "config": {
                "exists": observation.exists,
                "sha256": observation.sha256,
            },
        },
        sort_keys=True,
    )


def _serialize_certificate_inspection(inspection: CertificateInspection) -> str:
    return json.dumps(
        {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "status": "observed",
            "observations": [
                {
                    "target": {
                        "kind": observation.target.kind.value,
                        "server_name": observation.target.server_name,
                        "location": str(observation.target.location),
                    },
                    "state": observation.state.value,
                    "source_label": observation.source_label,
                    "diagnostics": observation.diagnostics,
                    "not_valid_before": (
                        observation.not_valid_before.isoformat()
                        if observation.not_valid_before is not None
                        else None
                    ),
                    "not_valid_after": (
                        observation.not_valid_after.isoformat()
                        if observation.not_valid_after is not None
                        else None
                    ),
                    "dns_names": list(observation.dns_names),
                }
                for observation in inspection.observations
            ],
        },
        sort_keys=True,
    )
