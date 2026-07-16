"""Root-side core activation from one fixed incoming directory."""

import hashlib
import hmac
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.artifacts.installation import CoreActivation, CoreDistributionInstaller
from sb_manager.artifacts.staging import CoreArtifactStager
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    ArtifactIntegrityError,
    CoreArtifactRequest,
    VerifiedCoreArtifact,
)

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024
SHA256_HEX_LENGTH = 64


class PrivilegedInputError(RuntimeError):
    """An unprivileged request or incoming file violates fixed policy."""


@dataclass(frozen=True, slots=True)
class ActivateCoreRequest:
    """Allowlisted values needed to identify one already trusted archive."""

    version: str
    architecture: ArtifactArchitecture
    sha256: str


@dataclass(frozen=True, slots=True)
class PrivilegedCoreInstallPolicy:
    """Root-owned paths that cannot be selected by an incoming request."""

    incoming_directory: Path
    working_directory: Path
    installation_root: Path
    lock_path: Path


class PrivilegedCoreInstallService:
    """Copy, re-verify, stage, and atomically activate one incoming core archive."""

    def __init__(self, *, policy: PrivilegedCoreInstallPolicy) -> None:
        self._policy = policy

    def activate_core(self, request: ActivateCoreRequest) -> CoreActivation:
        self._validate_request(request)
        self._require_incoming_directory()
        self._policy.working_directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        if self._policy.working_directory.is_symlink():
            raise PrivilegedInputError("Private working directory must not be a symlink")
        self._policy.working_directory.chmod(0o700)

        asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
        incoming_path = self._policy.incoming_directory / asset_name
        private_archive = self._copy_and_verify(
            incoming_path,
            expected_sha256=request.sha256,
        )
        staged_directory: Path | None = None
        try:
            staged = CoreArtifactStager().stage(
                VerifiedCoreArtifact(
                    version=request.version,
                    architecture=request.architecture,
                    asset_name=asset_name,
                    archive_path=private_archive,
                    sha256=request.sha256,
                ),
                destination_directory=self._policy.working_directory / "staging",
            )
            staged_directory = staged.distribution_directory.parent
            return CoreDistributionInstaller(
                installation_root=self._policy.installation_root,
                apply_lock=FileApplyLock(self._policy.lock_path),
            ).activate(staged)
        finally:
            private_archive.unlink(missing_ok=True)
            if staged_directory is not None:
                shutil.rmtree(staged_directory, ignore_errors=True)

    @staticmethod
    def _validate_request(request: ActivateCoreRequest) -> None:
        try:
            CoreArtifactRequest(
                version=request.version,
                architecture=request.architecture,
            )
        except ValueError as error:
            raise PrivilegedInputError(str(error)) from error
        if len(request.sha256) != SHA256_HEX_LENGTH or any(
            character not in "0123456789abcdef" for character in request.sha256
        ):
            raise PrivilegedInputError("Core archive SHA-256 must be 64 lowercase hex characters")

    def _require_incoming_directory(self) -> None:
        incoming = self._policy.incoming_directory
        if not incoming.is_dir() or incoming.is_symlink():
            raise PrivilegedInputError(
                f"Incoming artifact directory must be a real directory: {incoming}"
            )

    def _copy_and_verify(self, source_path: Path, *, expected_sha256: str) -> Path:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(source_path, flags)
        except OSError as error:
            raise PrivilegedInputError(
                f"Incoming core archive must be a regular file: {source_path}"
            ) from error

        private_path: Path | None = None
        try:
            source_stat = os.fstat(descriptor)
            if not stat.S_ISREG(source_stat.st_mode):
                raise PrivilegedInputError(
                    f"Incoming core archive must be a regular file: {source_path}"
                )
            if source_stat.st_size > MAX_ARCHIVE_BYTES:
                raise PrivilegedInputError(
                    f"Incoming core archive exceeds {MAX_ARCHIVE_BYTES} bytes"
                )

            digest = hashlib.sha256()
            with (
                os.fdopen(descriptor, "rb", closefd=False) as source,
                NamedTemporaryFile(
                    mode="wb",
                    dir=self._policy.working_directory,
                    prefix=".incoming-core.",
                    delete=False,
                ) as destination,
            ):
                private_path = Path(destination.name)
                copied_bytes = 0
                while chunk := source.read(COPY_CHUNK_BYTES):
                    copied_bytes += len(chunk)
                    if copied_bytes > MAX_ARCHIVE_BYTES:
                        raise PrivilegedInputError(
                            f"Incoming core archive exceeds {MAX_ARCHIVE_BYTES} bytes"
                        )
                    digest.update(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())

            actual_sha256 = digest.hexdigest()
            if not hmac.compare_digest(actual_sha256, expected_sha256):
                raise ArtifactIntegrityError(
                    f"SHA-256 mismatch for {source_path.name}: "
                    f"expected {expected_sha256}, got {actual_sha256}"
                )
            private_path.chmod(0o400)
            verified_path = private_path
            private_path = None
            return verified_path
        finally:
            os.close(descriptor)
            if private_path is not None:
                private_path.unlink(missing_ok=True)
