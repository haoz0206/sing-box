"""Root-side core activation from one fixed incoming directory."""

import shutil
from dataclasses import dataclass
from pathlib import Path

from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.artifacts.installation import CoreActivation, CoreDistributionInstaller
from sb_manager.artifacts.staging import CoreArtifactStager
from sb_manager.privileged.errors import PrivilegedInputError
from sb_manager.privileged.incoming import (
    VerifiedIncomingFileCopier,
    prepare_private_directory,
    require_real_directory,
)
from sb_manager.seams.artifact_source import (
    CoreArtifactRequest,
    VerifiedCoreArtifact,
)
from sb_manager.seams.core_activator import CoreActivationRequest
from sb_manager.seams.core_switcher import CoreSwitchRequest

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
SHA256_HEX_LENGTH = 64


@dataclass(frozen=True, slots=True)
class PrivilegedCoreInstallPolicy:
    """Root-owned paths that cannot be selected by an incoming request."""

    incoming_directory: Path
    working_directory: Path
    installation_root: Path
    lock_path: Path


class PrivilegedCoreInstallService:
    """Activate an incoming archive or switch one exact retained core release."""

    def __init__(self, *, policy: PrivilegedCoreInstallPolicy) -> None:
        self._policy = policy

    def activate_core(self, request: CoreActivationRequest) -> CoreActivation:
        self._validate_request(request)
        require_real_directory(self._policy.incoming_directory, role="Incoming artifact directory")
        prepare_private_directory(self._policy.working_directory)

        asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
        incoming_path = self._policy.incoming_directory / asset_name
        private_archive = VerifiedIncomingFileCopier(
            working_directory=self._policy.working_directory
        ).copy(
            incoming_path,
            expected_sha256=request.sha256,
            maximum_bytes=MAX_ARCHIVE_BYTES,
            prefix=".incoming-core.",
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

    def switch_core(self, request: CoreSwitchRequest) -> CoreActivation:
        """Switch only between identities already trusted by the local catalog."""

        return CoreDistributionInstaller(
            installation_root=self._policy.installation_root,
            apply_lock=FileApplyLock(self._policy.lock_path),
        ).switch(
            target=request.target,
            expected_active=request.expected_active,
        )

    @staticmethod
    def _validate_request(request: CoreActivationRequest) -> None:
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
