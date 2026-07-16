"""Atomic activation and conflict-aware rollback for staged core distributions."""

import os
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkdtemp

from sb_manager.artifacts.inspection import CoreBinaryInspector
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.artifact_source import CoreArtifactRequest, StagedCoreArtifact

SHA256_HEX_LENGTH = 64


class CoreInstallError(RuntimeError):
    """A staged distribution cannot be safely activated."""


class CoreRollbackConflictError(CoreInstallError):
    """The activation being rolled back is no longer current."""


@dataclass(frozen=True, slots=True)
class CoreActivation:
    """Evidence needed to inspect or roll back one atomic activation."""

    version: str
    distribution_directory: Path
    binary_path: Path
    activated_target: str
    previous_target: str | None


@dataclass(frozen=True, slots=True)
class CoreRollback:
    """Active target after a successful rollback."""

    active_target: str | None
    binary_path: Path | None


class CoreDistributionInstaller:
    """Own versioned copies and switch one relative ``current`` symlink."""

    def __init__(self, *, installation_root: Path, apply_lock: ApplyLock) -> None:
        self._installation_root = installation_root
        self._versions_directory = installation_root / "versions"
        self._current_path = installation_root / "current"
        self._apply_lock = apply_lock
        self._inspector = CoreBinaryInspector()

    def activate(self, staged: StagedCoreArtifact) -> CoreActivation:
        with self._apply_lock.acquire():
            self._validate_staged(staged)
            self._inspector.verify(staged.binary_path, staged.version)
            self._versions_directory.mkdir(parents=True, exist_ok=True)
            release_name = f"{staged.version}-{staged.source_sha256}"
            distribution_directory = self._versions_directory / release_name
            if not distribution_directory.exists():
                self._copy_distribution(staged, distribution_directory)
            installed_binary = distribution_directory / "sing-box"
            self._inspector.verify(installed_binary, staged.version)

            previous_target = self._current_target()
            activated_target = f"versions/{release_name}"
            self._switch_current(activated_target)
            return CoreActivation(
                version=staged.version,
                distribution_directory=distribution_directory,
                binary_path=self._current_path / "sing-box",
                activated_target=activated_target,
                previous_target=previous_target,
            )

    def rollback(self, activation: CoreActivation) -> CoreRollback:
        with self._apply_lock.acquire():
            current_target = self._current_target()
            if current_target != activation.activated_target:
                raise CoreRollbackConflictError(
                    f"Activation {activation.activated_target} is no longer current; "
                    f"found {current_target!r}"
                )
            self._switch_current(activation.previous_target)
            return CoreRollback(
                active_target=activation.previous_target,
                binary_path=(
                    self._current_path / "sing-box"
                    if activation.previous_target is not None
                    else None
                ),
            )

    @staticmethod
    def _validate_staged(staged: StagedCoreArtifact) -> None:
        if len(staged.source_sha256) != SHA256_HEX_LENGTH or any(
            character not in "0123456789abcdef" for character in staged.source_sha256
        ):
            raise CoreInstallError("Staged artifact SHA-256 is invalid")
        try:
            CoreArtifactRequest(version=staged.version, architecture=staged.architecture)
        except ValueError as error:
            raise CoreInstallError(
                f"Staged artifact version is invalid: {staged.version!r}"
            ) from error
        distribution = staged.distribution_directory
        if not distribution.is_dir() or distribution.is_symlink():
            raise CoreInstallError(f"Staged distribution is not a directory: {distribution}")
        expected_binary = distribution / "sing-box"
        if staged.binary_path != expected_binary:
            raise CoreInstallError("Staged binary is outside its distribution")
        for path in distribution.rglob("*"):
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise CoreInstallError(f"Staged distribution contains an unsafe entry: {path}")

    def _copy_distribution(
        self,
        staged: StagedCoreArtifact,
        destination: Path,
    ) -> None:
        temporary_root = Path(mkdtemp(dir=self._versions_directory, prefix=f".{destination.name}."))
        temporary_distribution = temporary_root / "distribution"
        try:
            shutil.copytree(staged.distribution_directory, temporary_distribution)
            self._inspector.verify(temporary_distribution / "sing-box", staged.version)
            temporary_distribution.replace(destination)
        finally:
            shutil.rmtree(temporary_root, ignore_errors=True)

    def _current_target(self) -> str | None:
        if self._current_path.is_symlink():
            return str(self._current_path.readlink())
        if self._current_path.exists():
            raise CoreInstallError(f"Current core path is not a symlink: {self._current_path}")
        return None

    def _switch_current(self, target: str | None) -> None:
        if target is None:
            self._current_path.unlink(missing_ok=True)
            self._sync_directory(self._installation_root)
            return
        temporary_link = self._installation_root / f".current.{secrets.token_hex(16)}"
        try:
            temporary_link.symlink_to(target, target_is_directory=True)
            temporary_link.replace(self._current_path)
            self._sync_directory(self._installation_root)
        finally:
            temporary_link.unlink(missing_ok=True)

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
