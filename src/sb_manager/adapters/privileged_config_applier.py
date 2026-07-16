"""Unprivileged configuration applier backed by the fixed root helper."""

import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile

from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    CommitResult,
    RollbackResult,
)

HELPER_SCHEMA_VERSION = 1
HELPER_TIMEOUT_SECONDS = 120


class PrivilegedHelperError(ConfigurationApplyError):
    """Base error for an unavailable or untrusted helper result."""


class PrivilegedHelperExecutionError(PrivilegedHelperError):
    """The helper command could not complete one request."""


class PrivilegedHelperProtocolError(PrivilegedHelperError):
    """The helper returned a response outside the exact public schema."""


class PrivilegedConfigurationApplier:
    """Stage deterministic JSON and restore the helper's typed transaction result."""

    def __init__(
        self,
        *,
        incoming_directory: Path,
        helper_command: Sequence[str],
        apply_lock: ApplyLock | None = None,
    ) -> None:
        if not helper_command:
            raise ValueError("Privileged helper command must not be empty")
        self._incoming_directory = incoming_directory
        self._helper_command = tuple(helper_command)
        self._apply_lock = apply_lock or FileApplyLock(
            incoming_directory.parent / "client-config-apply.lock"
        )

    def apply(self, document: Mapping[str, object]) -> ApplyTransactionResult:
        content = (
            json.dumps(
                document,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
        sha256 = hashlib.sha256(content).hexdigest()
        try:
            with self._apply_lock.acquire():
                config_path = self._stage(content, sha256=sha256)
                try:
                    return self._invoke_helper(sha256=sha256)
                finally:
                    config_path.unlink(missing_ok=True)
                    self._sync_directory(self._incoming_directory)
        except PrivilegedHelperError:
            raise
        except OSError as error:
            raise PrivilegedHelperExecutionError(
                f"Unable to stage helper request: {error}"
            ) from error

    def _stage(self, content: bytes, *, sha256: str) -> Path:
        self._incoming_directory.mkdir(parents=True, exist_ok=True)
        final_path = self._incoming_directory / f"config-{sha256}.json"
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=self._incoming_directory,
                prefix=".config.",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.chmod(0o600)
            temporary_path.replace(final_path)
            temporary_path = None
            self._sync_directory(self._incoming_directory)
            return final_path
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _invoke_helper(self, *, sha256: str) -> ApplyTransactionResult:
        request = json.dumps(
            {
                "schema_version": HELPER_SCHEMA_VERSION,
                "operation": "apply-config",
                "sha256": sha256,
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
            raise PrivilegedHelperExecutionError(
                f"Unable to execute privileged helper: {error}"
            ) from error
        if completed.returncode != 0:
            diagnostics = (completed.stderr or completed.stdout).strip()
            raise PrivilegedHelperExecutionError(
                diagnostics or f"Privileged helper exited with status {completed.returncode}"
            )
        return self._parse_response(completed.stdout)

    @classmethod
    def _parse_response(cls, response_text: str) -> ApplyTransactionResult:
        try:
            response = json.loads(response_text)
        except json.JSONDecodeError as error:
            raise PrivilegedHelperProtocolError(
                f"Privileged helper returned invalid JSON: {error.msg}"
            ) from error
        response_object = cls._object(
            response,
            fields={"schema_version", "status", "transaction"},
            role="response",
        )
        schema_version = response_object["schema_version"]
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or schema_version != HELPER_SCHEMA_VERSION
        ):
            raise PrivilegedHelperProtocolError(
                f"Unsupported helper schema version: {schema_version!r}"
            )
        status = cls._string(response_object["status"], role="status")
        if status not in {"applied", "rejected"}:
            raise PrivilegedHelperProtocolError(f"Unsupported helper status: {status!r}")
        transaction = cls._object(
            response_object["transaction"],
            fields={
                "outcome",
                "validation",
                "commit",
                "runtime_refresh",
                "postcondition",
                "rollback",
            },
            role="transaction",
        )
        try:
            outcome = ApplyOutcome(cls._string(transaction["outcome"], role="outcome"))
        except ValueError as error:
            raise PrivilegedHelperProtocolError(str(error)) from error
        expected_status = "applied" if outcome is ApplyOutcome.APPLIED else "rejected"
        if status != expected_status:
            raise PrivilegedHelperProtocolError(
                f"Helper status {status!r} does not match outcome {outcome.value!r}"
            )
        return ApplyTransactionResult(
            outcome=outcome,
            validation=cls._validation(transaction["validation"]),
            commit=cls._commit(transaction["commit"]),
            runtime_refresh=cls._runtime_refresh(transaction["runtime_refresh"]),
            postcondition=cls._postcondition(transaction["postcondition"]),
            rollback=cls._rollback(transaction["rollback"]),
        )

    @classmethod
    def _validation(cls, value: object) -> ConfigValidationResult:
        item = cls._object(value, fields={"valid", "diagnostics"}, role="validation")
        return ConfigValidationResult(
            valid=cls._boolean(item["valid"], role="validation.valid"),
            diagnostics=cls._string(
                item["diagnostics"],
                role="validation.diagnostics",
            ),
        )

    @classmethod
    def _commit(cls, value: object) -> CommitResult | None:
        if value is None:
            return None
        item = cls._object(value, fields={"success", "diagnostics"}, role="commit")
        return CommitResult(
            success=cls._boolean(item["success"], role="commit.success"),
            diagnostics=cls._string(item["diagnostics"], role="commit.diagnostics"),
        )

    @classmethod
    def _runtime_refresh(cls, value: object) -> RuntimeRefreshResult | None:
        if value is None:
            return None
        item = cls._object(
            value,
            fields={"success", "diagnostics"},
            role="runtime_refresh",
        )
        return RuntimeRefreshResult(
            success=cls._boolean(item["success"], role="runtime_refresh.success"),
            diagnostics=cls._string(
                item["diagnostics"],
                role="runtime_refresh.diagnostics",
            ),
        )

    @classmethod
    def _postcondition(cls, value: object) -> RuntimePostcondition | None:
        if value is None:
            return None
        item = cls._object(
            value,
            fields={"healthy", "diagnostics"},
            role="postcondition",
        )
        return RuntimePostcondition(
            healthy=cls._boolean(item["healthy"], role="postcondition.healthy"),
            diagnostics=cls._string(
                item["diagnostics"],
                role="postcondition.diagnostics",
            ),
        )

    @classmethod
    def _rollback(cls, value: object) -> RollbackResult | None:
        if value is None:
            return None
        item = cls._object(
            value,
            fields={"success", "diagnostics", "recovery_instructions"},
            role="rollback",
        )
        raw_instructions = item["recovery_instructions"]
        if not isinstance(raw_instructions, list) or not all(
            isinstance(instruction, str) for instruction in raw_instructions
        ):
            raise PrivilegedHelperProtocolError(
                "rollback.recovery_instructions must be a string list"
            )
        return RollbackResult(
            success=cls._boolean(item["success"], role="rollback.success"),
            diagnostics=cls._string(item["diagnostics"], role="rollback.diagnostics"),
            recovery_instructions=tuple(raw_instructions),
        )

    @staticmethod
    def _object(value: object, *, fields: set[str], role: str) -> dict[str, object]:
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            raise PrivilegedHelperProtocolError(f"Helper {role} must be an object")
        if set(value) != fields:
            raise PrivilegedHelperProtocolError(
                f"Helper {role} fields must be exactly {sorted(fields)}"
            )
        return value

    @staticmethod
    def _string(value: object, *, role: str) -> str:
        if not isinstance(value, str):
            raise PrivilegedHelperProtocolError(f"Helper {role} must be a string")
        return value

    @staticmethod
    def _boolean(value: object, *, role: str) -> bool:
        if not isinstance(value, bool):
            raise PrivilegedHelperProtocolError(f"Helper {role} must be a boolean")
        return value

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
