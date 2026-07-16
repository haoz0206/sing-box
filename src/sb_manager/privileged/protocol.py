"""Versioned JSON protocol for the single-shot privileged helper."""

import json
from collections.abc import Iterable
from typing import Protocol

from sb_manager.artifacts.installation import CoreActivation
from sb_manager.privileged.core_install import ActivateCoreRequest
from sb_manager.seams.artifact_source import ArtifactArchitecture, CoreArtifactRequest

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


class PrivilegeRequiredError(PermissionError):
    """The helper process is not running with effective root privileges."""


class PrivilegedProtocolError(ValueError):
    """A helper request does not match the exact allowlisted schema."""


class CoreActivator(Protocol):
    def activate_core(self, request: ActivateCoreRequest) -> CoreActivation: ...


def execute_privileged_request(
    request_text: str,
    *,
    effective_user_id: int,
    core_activator: CoreActivator,
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
    if set(raw_request) != ACTIVATE_CORE_FIELDS:
        raise PrivilegedProtocolError(
            f"Request fields must be exactly {sorted(ACTIVATE_CORE_FIELDS)}"
        )
    schema_version = raw_request["schema_version"]
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != REQUEST_SCHEMA_VERSION
    ):
        raise PrivilegedProtocolError(f"Unsupported privileged schema version: {schema_version!r}")
    if raw_request["operation"] != "activate-core":
        raise PrivilegedProtocolError(f"Unsupported operation: {raw_request['operation']!r}")

    version = _required_string(raw_request, "version")
    architecture_value = _required_string(raw_request, "architecture")
    sha256 = _required_string(raw_request, "sha256")
    try:
        architecture = ArtifactArchitecture(architecture_value)
        CoreArtifactRequest(version=version, architecture=architecture)
    except ValueError as error:
        raise PrivilegedProtocolError(str(error)) from error
    if len(sha256) != SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in sha256
    ):
        raise PrivilegedProtocolError("SHA-256 must be 64 lowercase hex characters")

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
