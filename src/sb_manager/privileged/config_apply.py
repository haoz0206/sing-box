"""Fixed-policy privileged configuration validation and transactional apply."""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.adapters.sing_box_validator import SingBoxConfigValidator
from sb_manager.privileged.config_policy import ManagedConfigurationPolicy
from sb_manager.privileged.errors import PrivilegedInputError
from sb_manager.privileged.incoming import (
    VerifiedIncomingFileCopier,
    prepare_private_directory,
    require_real_directory,
)
from sb_manager.seams.runtime import Runtime
from sb_manager.transactions.apply import (
    ApplyCoordinator,
    ApplyTransactionResult,
    ConfigTargetPrecondition,
)
from sb_manager.transactions.staging import ConfigurationStager

MAX_CONFIG_BYTES = 4 * 1024 * 1024
SHA256_HEX_LENGTH = 64


@dataclass(frozen=True, slots=True)
class ApplyConfigRequest:
    """Identify one exact incoming configuration without selecting a destination."""

    sha256: str
    expected_config_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class PrivilegedConfigApplyPolicy:
    """Fixed paths for one host's configuration transaction."""

    incoming_directory: Path
    working_directory: Path
    config_path: Path
    core_binary: Path
    lock_path: Path


class PrivilegedConfigApplyService:
    """Re-verify incoming JSON and reuse the tested host apply transaction."""

    def __init__(
        self,
        *,
        policy: PrivilegedConfigApplyPolicy,
        runtime: Runtime,
        document_policy: ManagedConfigurationPolicy | None = None,
    ) -> None:
        self._policy = policy
        self._runtime = runtime
        self._document_policy = document_policy or ManagedConfigurationPolicy()

    def apply_config(self, request: ApplyConfigRequest) -> ApplyTransactionResult:
        self._validate_request(request)
        require_real_directory(
            self._policy.incoming_directory,
            role="Incoming configuration directory",
        )
        prepare_private_directory(self._policy.working_directory)
        incoming_path = self._policy.incoming_directory / f"config-{request.sha256}.json"
        private_config = VerifiedIncomingFileCopier(
            working_directory=self._policy.working_directory
        ).copy(
            incoming_path,
            expected_sha256=request.sha256,
            maximum_bytes=MAX_CONFIG_BYTES,
            prefix=".incoming-config.",
        )
        try:
            document = self._load_document(private_config)
            self._document_policy.validate(document)
            with FileApplyLock(self._policy.lock_path).acquire():
                return ApplyCoordinator(
                    config_path=self._policy.config_path,
                    stager=ConfigurationStager(
                        parent=self._policy.working_directory / "config-staging"
                    ),
                    validator=SingBoxConfigValidator(binary=self._policy.core_binary),
                    runtime=self._runtime,
                ).apply(
                    document,
                    precondition=(
                        ConfigTargetPrecondition.matching_sha256(request.expected_config_sha256)
                        if request.expected_config_sha256 is not None
                        else ConfigTargetPrecondition.absent()
                    ),
                )
        finally:
            private_config.unlink(missing_ok=True)

    @staticmethod
    def _validate_request(request: ApplyConfigRequest) -> None:
        if len(request.sha256) != SHA256_HEX_LENGTH or any(
            character not in "0123456789abcdef" for character in request.sha256
        ):
            raise PrivilegedInputError("Configuration SHA-256 must be 64 lowercase hex characters")
        expected = request.expected_config_sha256
        if expected is not None and (
            len(expected) != SHA256_HEX_LENGTH
            or any(character not in "0123456789abcdef" for character in expected)
        ):
            raise PrivilegedInputError(
                "Expected configuration SHA-256 must be 64 lowercase hex characters"
            )

    @staticmethod
    def _load_document(path: Path) -> dict[str, object]:
        try:
            raw_document = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=PrivilegedConfigApplyService._unique_object,
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise PrivilegedInputError(
                f"Incoming configuration is not valid JSON: {error}"
            ) from error
        if not isinstance(raw_document, dict) or not all(
            isinstance(key, str) for key in raw_document
        ):
            raise PrivilegedInputError("Incoming configuration must be a JSON object")
        return raw_document

    @staticmethod
    def _unique_object(pairs: Iterable[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise PrivilegedInputError(f"Incoming configuration has duplicate field: {key}")
            result[key] = value
        return result
