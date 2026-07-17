"""Unprivileged certificate evidence adapter backed by the fixed root helper."""

import json
import subprocess
from collections.abc import Collection, Iterable, Sequence
from datetime import datetime
from pathlib import Path

from sb_manager.seams.certificate_source import (
    CertificateInspection,
    CertificateInspectionError,
    CertificateMaterialState,
    CertificateObservation,
    CertificateTarget,
    CertificateTargetKind,
)

HELPER_SCHEMA_VERSION = 1
HELPER_TIMEOUT_SECONDS = 30
_OBSERVATION_FIELDS = {
    "target",
    "state",
    "source_label",
    "diagnostics",
    "not_valid_before",
    "not_valid_after",
    "dns_names",
}
_TARGET_FIELDS = {"kind", "server_name", "location"}


class PrivilegedCertificateExecutionError(CertificateInspectionError):
    """The helper process could not return trustworthy certificate evidence."""


class PrivilegedCertificateProtocolError(CertificateInspectionError):
    """The helper response did not match the exact public evidence schema."""


class PrivilegedCertificateSource:
    """Request public validity metadata without returning PEM or private keys."""

    def __init__(self, *, helper_command: Sequence[str]) -> None:
        if not helper_command:
            raise ValueError("Privileged helper command must not be empty")
        self._helper_command = tuple(helper_command)

    def inspect(self, targets: Collection[CertificateTarget]) -> CertificateInspection:
        requested = tuple(targets)
        request = json.dumps(
            {
                "schema_version": HELPER_SCHEMA_VERSION,
                "operation": "inspect-certificates",
                "targets": [
                    {
                        "kind": target.kind.value,
                        "server_name": target.server_name,
                        "location": str(target.location),
                    }
                    for target in requested
                ],
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
            raise PrivilegedCertificateExecutionError(
                f"Unable to execute privileged helper: {error}"
            ) from error
        if completed.returncode != 0:
            diagnostics = (completed.stderr or completed.stdout).strip()
            raise PrivilegedCertificateExecutionError(
                diagnostics or f"Privileged helper exited with status {completed.returncode}"
            )
        return self._parse_response(completed.stdout, requested=requested)

    @classmethod
    def _parse_response(
        cls,
        response_text: str,
        *,
        requested: tuple[CertificateTarget, ...],
    ) -> CertificateInspection:
        try:
            response = json.loads(response_text, object_pairs_hook=cls._unique_object)
        except json.JSONDecodeError as error:
            raise PrivilegedCertificateProtocolError(
                f"Privileged helper returned invalid JSON: {error.msg}"
            ) from error
        response_object = cls._object(
            response,
            fields={"schema_version", "status", "observations"},
            role="response",
        )
        if response_object["schema_version"] != HELPER_SCHEMA_VERSION:
            raise PrivilegedCertificateProtocolError("Unsupported helper schema version")
        if response_object["status"] != "observed":
            raise PrivilegedCertificateProtocolError("Unsupported helper status")
        raw_observations = response_object["observations"]
        if not isinstance(raw_observations, list):
            raise PrivilegedCertificateProtocolError("Helper observations must be a list")
        observations = tuple(cls._observation(item) for item in raw_observations)
        returned_targets = tuple(observation.target for observation in observations)
        if returned_targets != requested:
            raise PrivilegedCertificateProtocolError(
                "Helper observations must exactly match requested certificate targets"
            )
        return CertificateInspection(observations=observations)

    @classmethod
    def _observation(cls, value: object) -> CertificateObservation:
        item = cls._object(value, fields=_OBSERVATION_FIELDS, role="observation")
        target_item = cls._object(item["target"], fields=_TARGET_FIELDS, role="target")
        kind_value = cls._string(target_item["kind"], role="target.kind")
        try:
            kind = CertificateTargetKind(kind_value)
        except ValueError as error:
            raise PrivilegedCertificateProtocolError(
                f"Unsupported helper certificate target kind: {kind_value!r}"
            ) from error
        state_value = cls._string(item["state"], role="observation.state")
        try:
            state = CertificateMaterialState(state_value)
        except ValueError as error:
            raise PrivilegedCertificateProtocolError(
                f"Unsupported helper certificate state: {state_value!r}"
            ) from error
        dns_names = item["dns_names"]
        if not isinstance(dns_names, list) or not all(isinstance(name, str) for name in dns_names):
            raise PrivilegedCertificateProtocolError(
                "Helper observation.dns_names must be a list of strings"
            )
        try:
            return CertificateObservation(
                target=CertificateTarget(
                    kind=kind,
                    server_name=cls._string(target_item["server_name"], role="target.server_name"),
                    location=Path(cls._string(target_item["location"], role="target.location")),
                ),
                state=state,
                source_label=cls._string(item["source_label"], role="observation.source_label"),
                diagnostics=cls._string(item["diagnostics"], role="observation.diagnostics"),
                not_valid_before=cls._optional_datetime(
                    item["not_valid_before"], role="observation.not_valid_before"
                ),
                not_valid_after=cls._optional_datetime(
                    item["not_valid_after"], role="observation.not_valid_after"
                ),
                dns_names=tuple(dns_names),
            )
        except ValueError as error:
            raise PrivilegedCertificateProtocolError(str(error)) from error

    @staticmethod
    def _optional_datetime(value: object, *, role: str) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise PrivilegedCertificateProtocolError(f"Helper {role} must be null or string")
        try:
            return datetime.fromisoformat(value)
        except ValueError as error:
            raise PrivilegedCertificateProtocolError(
                f"Helper {role} must be an ISO 8601 datetime"
            ) from error

    @staticmethod
    def _unique_object(pairs: Iterable[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise PrivilegedCertificateProtocolError(
                    f"Helper response contains duplicate field: {key}"
                )
            result[key] = value
        return result

    @staticmethod
    def _object(value: object, *, fields: set[str], role: str) -> dict[str, object]:
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            raise PrivilegedCertificateProtocolError(f"Helper {role} must be an object")
        if set(value) != fields:
            raise PrivilegedCertificateProtocolError(
                f"Helper {role} fields must be exactly {sorted(fields)}"
            )
        return value

    @staticmethod
    def _string(value: object, *, role: str) -> str:
        if not isinstance(value, str):
            raise PrivilegedCertificateProtocolError(f"Helper {role} must be a string")
        return value
