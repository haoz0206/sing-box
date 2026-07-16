"""Unprivileged config identity adapter backed by the fixed root helper."""

import json
import subprocess
from collections.abc import Iterable, Sequence

from sb_manager.seams.config_target import (
    ConfigTargetInspectionError,
    LiveConfigObservation,
)

HELPER_SCHEMA_VERSION = 1
HELPER_TIMEOUT_SECONDS = 30


class PrivilegedConfigInspectionExecutionError(ConfigTargetInspectionError):
    """The helper process could not return a trustworthy observation."""


class PrivilegedConfigInspectionProtocolError(ConfigTargetInspectionError):
    """The helper response did not match the exact observation schema."""


class PrivilegedConfigurationTargetInspector:
    """Request only existence and SHA-256; never return live configuration content."""

    def __init__(self, *, helper_command: Sequence[str]) -> None:
        if not helper_command:
            raise ValueError("Privileged helper command must not be empty")
        self._helper_command = tuple(helper_command)

    def inspect(self) -> LiveConfigObservation:
        request = json.dumps(
            {
                "schema_version": HELPER_SCHEMA_VERSION,
                "operation": "inspect-config",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            completed = subprocess.run(
                list(self._helper_command),
                input=request,
                check=False,
                capture_output=True,
                text=True,
                timeout=HELPER_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PrivilegedConfigInspectionExecutionError(
                f"Unable to execute privileged helper: {error}"
            ) from error
        if completed.returncode != 0:
            diagnostics = (completed.stderr or completed.stdout).strip()
            raise PrivilegedConfigInspectionExecutionError(
                diagnostics or f"Privileged helper exited with status {completed.returncode}"
            )
        return self._parse_response(completed.stdout)

    @classmethod
    def _parse_response(cls, response_text: str) -> LiveConfigObservation:
        try:
            response = json.loads(response_text, object_pairs_hook=cls._unique_object)
        except json.JSONDecodeError as error:
            raise PrivilegedConfigInspectionProtocolError(
                f"Privileged helper returned invalid JSON: {error.msg}"
            ) from error
        response_object = cls._object(
            response,
            fields={"schema_version", "status", "config"},
            role="response",
        )
        if response_object["schema_version"] != HELPER_SCHEMA_VERSION:
            raise PrivilegedConfigInspectionProtocolError("Unsupported helper schema version")
        if response_object["status"] != "observed":
            raise PrivilegedConfigInspectionProtocolError("Unsupported helper status")
        config = cls._object(
            response_object["config"],
            fields={"exists", "sha256"},
            role="config",
        )
        exists = config["exists"]
        sha256 = config["sha256"]
        if not isinstance(exists, bool):
            raise PrivilegedConfigInspectionProtocolError("Helper config.exists must be boolean")
        if sha256 is not None and not isinstance(sha256, str):
            raise PrivilegedConfigInspectionProtocolError(
                "Helper config.sha256 must be null or string"
            )
        try:
            return LiveConfigObservation(exists=exists, sha256=sha256)
        except ValueError as error:
            raise PrivilegedConfigInspectionProtocolError(str(error)) from error

    @staticmethod
    def _unique_object(pairs: Iterable[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise PrivilegedConfigInspectionProtocolError(
                    f"Helper response contains duplicate field: {key}"
                )
            result[key] = value
        return result

    @staticmethod
    def _object(value: object, *, fields: set[str], role: str) -> dict[str, object]:
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            raise PrivilegedConfigInspectionProtocolError(f"Helper {role} must be an object")
        if set(value) != fields:
            raise PrivilegedConfigInspectionProtocolError(
                f"Helper {role} fields must be exactly {sorted(fields)}"
            )
        return value
