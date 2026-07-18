"""Unprivileged client for the privileged core activation operation."""

import json
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

from sb_manager.artifacts.installation import CoreActivation, CoreReleaseIdentity
from sb_manager.seams.core_activator import (
    CoreActivationError,
    CoreActivationRequest,
)
from sb_manager.seams.core_switcher import CoreSwitchError, CoreSwitchRequest

HELPER_SCHEMA_VERSION = 1
HELPER_TIMEOUT_SECONDS = 120


class PrivilegedCoreActivatorError(CoreActivationError, CoreSwitchError):
    """Base error for a failed or untrusted privileged activation."""


class PrivilegedCoreHelperExecutionError(PrivilegedCoreActivatorError):
    """The helper process could not complete the activation request."""


class PrivilegedCoreHelperProtocolError(PrivilegedCoreActivatorError):
    """The helper response did not match the exact activation schema."""


class PrivilegedCoreActivator:
    """Request exact activation or retained switching through one fixed helper."""

    def __init__(self, *, helper_command: Sequence[str]) -> None:
        if not helper_command:
            raise ValueError("Privileged helper command must not be empty")
        self._helper_command = tuple(helper_command)

    def activate_core(self, request: CoreActivationRequest) -> CoreActivation:
        return self._invoke(
            request_document={
                "schema_version": HELPER_SCHEMA_VERSION,
                "operation": "activate-core",
                "version": request.version,
                "architecture": request.architecture.value,
                "sha256": request.sha256,
            },
            expected_status="activated",
            expected_version=request.version,
        )

    def switch_core(self, request: CoreSwitchRequest) -> CoreActivation:
        return self._invoke(
            request_document={
                "schema_version": HELPER_SCHEMA_VERSION,
                "operation": "switch-core",
                "target": self._identity_document(request.target),
                "expected_active": self._identity_document(request.expected_active),
            },
            expected_status="switched",
            expected_version=request.target.version,
        )

    def _invoke(
        self,
        *,
        request_document: dict[str, object],
        expected_status: str,
        expected_version: str,
    ) -> CoreActivation:
        request_text = json.dumps(request_document, separators=(",", ":"), sort_keys=True)
        try:
            completed = subprocess.run(
                list(self._helper_command),
                input=request_text,
                check=False,
                capture_output=True,
                text=True,
                timeout=HELPER_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PrivilegedCoreHelperExecutionError(
                f"Unable to execute privileged helper: {error}"
            ) from error
        if completed.returncode != 0:
            diagnostics = (completed.stderr or completed.stdout).strip()
            raise PrivilegedCoreHelperExecutionError(
                diagnostics or f"Privileged helper exited with status {completed.returncode}"
            )
        return self._parse_response(
            completed.stdout,
            expected_status=expected_status,
            expected_version=expected_version,
        )

    @classmethod
    def _parse_response(
        cls,
        response_text: str,
        *,
        expected_status: str,
        expected_version: str,
    ) -> CoreActivation:
        try:
            response = json.loads(response_text, object_pairs_hook=cls._unique_object)
        except json.JSONDecodeError as error:
            raise PrivilegedCoreHelperProtocolError(
                f"Privileged helper returned invalid JSON: {error.msg}"
            ) from error
        response_object = cls._object(
            response,
            fields={"schema_version", "status", "activation"},
            role="response",
        )
        schema_version = response_object["schema_version"]
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or schema_version != HELPER_SCHEMA_VERSION
        ):
            raise PrivilegedCoreHelperProtocolError(
                f"Unsupported helper schema version: {schema_version!r}"
            )
        status = cls._string(response_object["status"], role="status")
        if status != expected_status:
            raise PrivilegedCoreHelperProtocolError(f"Unsupported helper status: {status!r}")
        item = cls._object(
            response_object["activation"],
            fields={
                "version",
                "distribution_directory",
                "binary_path",
                "activated_target",
                "previous_target",
            },
            role="activation",
        )
        version = cls._string(item["version"], role="activation.version")
        if version != expected_version:
            raise PrivilegedCoreHelperProtocolError(
                f"Helper activation version {version!r} does not match request {expected_version!r}"
            )
        previous_target = item["previous_target"]
        if previous_target is not None:
            previous_target = cls._string(
                previous_target,
                role="activation.previous_target",
            )
        return CoreActivation(
            version=version,
            distribution_directory=Path(
                cls._string(
                    item["distribution_directory"],
                    role="activation.distribution_directory",
                )
            ),
            binary_path=Path(cls._string(item["binary_path"], role="activation.binary_path")),
            activated_target=cls._string(
                item["activated_target"],
                role="activation.activated_target",
            ),
            previous_target=previous_target,
        )

    @staticmethod
    def _identity_document(identity: CoreReleaseIdentity) -> dict[str, object]:
        return {
            "version": identity.version,
            "architecture": identity.architecture.value,
            "sha256": identity.source_sha256,
        }

    @staticmethod
    def _unique_object(pairs: Iterable[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise PrivilegedCoreHelperProtocolError(
                    f"Helper response contains duplicate field: {key}"
                )
            result[key] = value
        return result

    @staticmethod
    def _object(value: object, *, fields: set[str], role: str) -> dict[str, object]:
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            raise PrivilegedCoreHelperProtocolError(f"Helper {role} must be an object")
        if set(value) != fields:
            raise PrivilegedCoreHelperProtocolError(
                f"Helper {role} fields must be exactly {sorted(fields)}"
            )
        return value

    @staticmethod
    def _string(value: object, *, role: str) -> str:
        if not isinstance(value, str):
            raise PrivilegedCoreHelperProtocolError(f"Helper {role} must be a string")
        return value
