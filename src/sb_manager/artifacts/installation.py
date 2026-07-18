"""Trusted catalog, atomic activation, and rollback for core distributions."""

import json
import os
import secrets
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile, mkdtemp

from sb_manager.artifacts.inspection import CoreBinaryInspector
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    CoreArtifactRequest,
    StagedCoreArtifact,
)

SHA256_HEX_LENGTH = 64
RELEASE_MANIFEST_NAME = ".sb-manager-release.json"
RELEASE_MANIFEST_SCHEMA_VERSION = 1


class CoreInstallError(RuntimeError):
    """A staged distribution cannot be safely activated."""


class CoreRollbackConflictError(CoreInstallError):
    """The activation being rolled back is no longer current."""


class CoreSwitchConflictError(CoreInstallError):
    """The active installed release no longer matches the reviewed switch plan."""


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


@dataclass(frozen=True, slots=True)
class CoreReleaseIdentity:
    """Exact manager-installed release identity without a caller-selected path."""

    version: str
    architecture: ArtifactArchitecture
    source_sha256: str


@dataclass(frozen=True, slots=True)
class InstalledCoreRelease:
    """One manifest-backed immutable distribution eligible for exact switching."""

    version: str
    architecture: ArtifactArchitecture
    source_sha256: str
    distribution_directory: Path
    target: str
    active: bool


class CoreInstallationCatalog:
    """List only manager-manifested distributions whose binary identity verifies."""

    def __init__(self, *, installation_root: Path) -> None:
        self._installation_root = installation_root
        self._versions_directory = installation_root / "versions"
        self._current_path = installation_root / "current"
        self._inspector = CoreBinaryInspector()

    def list_installed(self) -> tuple[InstalledCoreRelease, ...]:
        if not self._versions_directory.exists():
            return ()
        if not self._versions_directory.is_dir() or self._versions_directory.is_symlink():
            raise CoreInstallError(
                f"Core versions path is not a real directory: {self._versions_directory}"
            )
        current_target = _current_target(self._current_path)
        releases = []
        for distribution_directory in self._versions_directory.iterdir():
            if not distribution_directory.is_dir() or distribution_directory.is_symlink():
                continue
            manifest_path = distribution_directory / RELEASE_MANIFEST_NAME
            if not manifest_path.is_file() or manifest_path.is_symlink():
                continue
            manifest = _read_release_manifest(manifest_path)
            version = _manifest_string(manifest, "version")
            source_sha256 = _manifest_sha256(manifest)
            try:
                architecture = ArtifactArchitecture(_manifest_string(manifest, "architecture"))
                CoreArtifactRequest(version=version, architecture=architecture)
            except ValueError as error:
                raise CoreInstallError(
                    f"Installed core manifest is invalid: {manifest_path}"
                ) from error
            release_name = f"{version}-{source_sha256}"
            if distribution_directory.name != release_name:
                raise CoreInstallError(
                    f"Installed core manifest does not match directory: {distribution_directory}"
                )
            self._inspector.verify(distribution_directory / "sing-box", version)
            target = f"versions/{release_name}"
            releases.append(
                InstalledCoreRelease(
                    version=version,
                    architecture=architecture,
                    source_sha256=source_sha256,
                    distribution_directory=distribution_directory,
                    target=target,
                    active=target == current_target,
                )
            )
        return tuple(sorted(releases, key=lambda release: (release.version, release.source_sha256)))


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
            if self._versions_directory.is_symlink() or not self._versions_directory.is_dir():
                raise CoreInstallError(
                    f"Core versions path is not a real directory: {self._versions_directory}"
                )
            release_name = f"{staged.version}-{staged.source_sha256}"
            distribution_directory = self._versions_directory / release_name
            if distribution_directory.is_symlink() or (
                distribution_directory.exists() and not distribution_directory.is_dir()
            ):
                raise CoreInstallError(
                    f"Installed core path is not a real directory: {distribution_directory}"
                )
            if not distribution_directory.exists():
                self._copy_distribution(staged, distribution_directory)
            installed_binary = distribution_directory / "sing-box"
            self._inspector.verify(installed_binary, staged.version)
            _publish_release_manifest(distribution_directory, staged)

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

    def switch(
        self,
        *,
        target: CoreReleaseIdentity,
        expected_active: CoreReleaseIdentity,
    ) -> CoreActivation:
        """Atomically select one retained exact identity after rechecking current."""

        with self._apply_lock.acquire():
            expected_directory, expected_target = self._require_installed(expected_active)
            target_directory, target_name = self._require_installed(target)
            current_target = self._current_target()
            if current_target != expected_target:
                raise CoreSwitchConflictError(
                    f"Active core changed after review; expected {expected_target!r}, "
                    f"found {current_target!r}"
                )
            if target_name == expected_target:
                raise CoreSwitchConflictError("Retained core target is already active")
            self._inspector.verify(expected_directory / "sing-box", expected_active.version)
            self._switch_current(target_name)
            return CoreActivation(
                version=target.version,
                distribution_directory=target_directory,
                binary_path=self._current_path / "sing-box",
                activated_target=target_name,
                previous_target=expected_target,
            )

    def _require_installed(self, identity: CoreReleaseIdentity) -> tuple[Path, str]:
        release_name = _release_name(identity)
        distribution_directory = self._versions_directory / release_name
        if not distribution_directory.is_dir() or distribution_directory.is_symlink():
            raise CoreInstallError(f"Installed core distribution is missing: {release_name}")
        manifest_path = distribution_directory / RELEASE_MANIFEST_NAME
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise CoreInstallError(f"Installed core manifest is missing: {release_name}")
        if _read_release_manifest(manifest_path) != _identity_document(identity):
            raise CoreInstallError(f"Installed core manifest does not match: {release_name}")
        self._inspector.verify(distribution_directory / "sing-box", identity.version)
        return distribution_directory, f"versions/{release_name}"

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
            _publish_release_manifest(temporary_distribution, staged)
            temporary_distribution.replace(destination)
        finally:
            shutil.rmtree(temporary_root, ignore_errors=True)

    def _current_target(self) -> str | None:
        return _current_target(self._current_path)

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


def _current_target(current_path: Path) -> str | None:
    if current_path.is_symlink():
        return str(current_path.readlink())
    if current_path.exists():
        raise CoreInstallError(f"Current core path is not a symlink: {current_path}")
    return None


def _publish_release_manifest(
    distribution_directory: Path,
    staged: StagedCoreArtifact,
) -> None:
    manifest_path = distribution_directory / RELEASE_MANIFEST_NAME
    document = _identity_document(
        CoreReleaseIdentity(
            version=staged.version,
            architecture=staged.architecture,
            source_sha256=staged.source_sha256,
        )
    )
    if manifest_path.exists() or manifest_path.is_symlink():
        if _read_release_manifest(manifest_path) != document:
            raise CoreInstallError(f"Installed core manifest does not match: {manifest_path}")
        return
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=distribution_directory,
            prefix=f".{RELEASE_MANIFEST_NAME}.",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(json.dumps(document, sort_keys=True) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(manifest_path)
        temporary_path = None
        CoreDistributionInstaller._sync_directory(distribution_directory)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _read_release_manifest(path: Path) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, json.JSONDecodeError) as error:
        raise CoreInstallError(f"Installed core manifest is unreadable: {path}") from error
    expected_fields = {"schema_version", "version", "architecture", "source_sha256"}
    if not isinstance(document, dict) or set(document) != expected_fields:
        raise CoreInstallError(f"Installed core manifest fields are invalid: {path}")
    schema_version = document["schema_version"]
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != RELEASE_MANIFEST_SCHEMA_VERSION
    ):
        raise CoreInstallError(f"Installed core manifest schema is unsupported: {path}")
    return document


def _unique_object(pairs: Iterable[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CoreInstallError(f"Installed core manifest contains duplicate field: {key}")
        result[key] = value
    return result


def _manifest_string(manifest: dict[str, object], field: str) -> str:
    value = manifest[field]
    if not isinstance(value, str):
        raise CoreInstallError(f"Installed core manifest field {field} must be a string")
    return value


def _manifest_sha256(manifest: dict[str, object]) -> str:
    sha256 = _manifest_string(manifest, "source_sha256")
    if len(sha256) != SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in sha256
    ):
        raise CoreInstallError("Installed core manifest SHA-256 is invalid")
    return sha256


def _release_name(identity: CoreReleaseIdentity) -> str:
    try:
        CoreArtifactRequest(version=identity.version, architecture=identity.architecture)
    except ValueError as error:
        raise CoreInstallError(
            f"Installed core version is invalid: {identity.version!r}"
        ) from error
    if len(identity.source_sha256) != SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in identity.source_sha256
    ):
        raise CoreInstallError("Installed core SHA-256 is invalid")
    return f"{identity.version}-{identity.source_sha256}"


def _identity_document(identity: CoreReleaseIdentity) -> dict[str, object]:
    _release_name(identity)
    return {
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
        "version": identity.version,
        "architecture": identity.architecture.value,
        "source_sha256": identity.source_sha256,
    }
