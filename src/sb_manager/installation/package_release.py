"""Plan versioned Python package releases without mutating the host."""

import hashlib
import os
import re
import secrets
import shutil
import stat
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile

from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.package_environment import (
    PackageEnvironmentBuilder,
    PackageEnvironmentBuildRequest,
)

MAX_WHEEL_BYTES = 256 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024
PACKAGE_NAME = "sing-box-manager"
SAFE_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
ACTIVE_RELEASE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*-[0-9a-f]{64}")
ACTIVE_TARGET_PARTS = 2
PACKAGE_COMMANDS = (
    "sb-manager",
    "sb-manager-privileged",
    "sb-manager-install-policy",
    "sb-manager-install",
)


class PackageInstallError(RuntimeError):
    """A Python package release cannot be safely planned or installed."""


class DependencySource(str, Enum):
    """Explicit source from which pip may resolve runtime dependencies."""

    INDEX = "index"
    WHEELHOUSE = "wheelhouse"


@dataclass(frozen=True, slots=True)
class PackageInstallRequest:
    """Operator-selected local wheel and dependency trust mode."""

    wheel_path: Path
    dependency_source: DependencySource
    wheelhouse: Path | None = None


@dataclass(frozen=True, slots=True)
class PackageInstallPlan:
    """Immutable preview of one versioned manager package release."""

    wheel_path: Path
    package_version: str
    wheel_sha256: str
    release_directory: Path
    current_link: Path
    launcher_directory: Path
    dependency_source: DependencySource
    wheelhouse: Path | None
    mutates_host: bool = False


@dataclass(frozen=True, slots=True)
class PackageInstallResult:
    """Activated release and prior target returned after a confirmed installation."""

    package_version: str
    release_directory: Path
    launcher_directory: Path
    active_target: str
    previous_target: str | None


@dataclass(frozen=True, slots=True)
class PackageRollbackRequest:
    """Operator-selected immutable package release to reactivate."""

    target_release: str


@dataclass(frozen=True, slots=True)
class PackageRollbackPlan:
    """Read-only preview of one exact retained-release activation."""

    active_target: str
    target_release: str
    target_directory: Path
    current_link: Path
    mutates_host: bool = False


@dataclass(frozen=True, slots=True)
class PackageRollbackResult:
    """Atomic activation result for one retained package release."""

    active_target: str
    previous_target: str


class VersionedPackageInstaller:
    """Own package identity and fixed versioned host destinations."""

    def __init__(
        self,
        *,
        root: Path,
        environment_builder: PackageEnvironmentBuilder,
        install_lock: ApplyLock | None = None,
    ) -> None:
        if not root.is_absolute():
            raise ValueError("Package installation root must be absolute")
        self._root = root
        self._environment_builder = environment_builder
        self._install_lock = install_lock or FileApplyLock(
            root.parent / ".sing-box-manager-package.lock"
        )

    def plan(self, request: PackageInstallRequest) -> PackageInstallPlan:
        wheel_path = request.wheel_path.resolve()
        self._validate_request(request, wheel_path=wheel_path)
        package_version = self._read_package_version(wheel_path)
        wheel_sha256 = self._sha256(wheel_path)
        release_name = f"{package_version}-{wheel_sha256}"
        return PackageInstallPlan(
            wheel_path=wheel_path,
            package_version=package_version,
            wheel_sha256=wheel_sha256,
            release_directory=self._root / "releases" / release_name,
            current_link=self._root / "current",
            launcher_directory=self._root / "bin",
            dependency_source=request.dependency_source,
            wheelhouse=(request.wheelhouse.resolve() if request.wheelhouse is not None else None),
        )

    def plan_rollback(self, request: PackageRollbackRequest) -> PackageRollbackPlan:
        """Inspect one retained release without changing package activation."""
        self._validate_existing_root()
        if ACTIVE_RELEASE_PATTERN.fullmatch(request.target_release) is None:
            raise PackageInstallError(
                f"Invalid retained package release: {request.target_release!r}"
            )
        current_link = self._root / "current"
        active_target = self._current_target(current_link)
        if active_target is None:
            raise PackageInstallError("No active package release is available to roll back")
        target = f"releases/{request.target_release}"
        if target == active_target:
            raise PackageInstallError(f"Package release is already active: {target}")
        target_directory = self._root / target
        if target_directory.is_symlink() or not target_directory.is_dir():
            raise PackageInstallError(
                f"Retained package release is missing or unsafe: {target_directory}"
            )
        self._verify_retained_release(target_directory)
        self._verify_release_commands(target_directory)
        return PackageRollbackPlan(
            active_target=active_target,
            target_release=request.target_release,
            target_directory=target_directory,
            current_link=current_link,
        )

    def install(
        self,
        plan: PackageInstallPlan,
        *,
        confirmed: bool,
    ) -> PackageInstallResult:
        if not confirmed:
            raise PackageInstallError("Package installation requires explicit confirmation")
        with self._install_lock.acquire():
            return self._install_locked(plan)

    def rollback(
        self,
        plan: PackageRollbackPlan,
        *,
        confirmed: bool,
    ) -> PackageRollbackResult:
        if not confirmed:
            raise PackageInstallError("Package rollback requires explicit confirmation")
        with self._install_lock.acquire():
            expected_plan = self.plan_rollback(
                PackageRollbackRequest(target_release=plan.target_release)
            )
            if plan != expected_plan:
                raise PackageInstallError(
                    "Package rollback plan no longer matches active package state"
                )
            target = str(plan.target_directory.relative_to(self._root))
            self._switch_current(plan.current_link, target=target)
            return PackageRollbackResult(
                active_target=target,
                previous_target=plan.active_target,
            )

    def _install_locked(self, plan: PackageInstallPlan) -> PackageInstallResult:
        expected_plan = self.plan(
            PackageInstallRequest(
                wheel_path=plan.wheel_path,
                dependency_source=plan.dependency_source,
                wheelhouse=plan.wheelhouse,
            )
        )
        if plan != expected_plan:
            raise PackageInstallError("Package install plan no longer matches its source wheel")
        self._prepare_root()
        if plan.release_directory.exists() or plan.release_directory.is_symlink():
            raise PackageInstallError(
                f"Package release destination already exists: {plan.release_directory}"
            )
        plan.release_directory.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        previous_target = self._current_target(plan.current_link)
        try:
            plan.release_directory.mkdir(mode=0o700)
            private_wheel = self._copy_verified_wheel(plan)
            try:
                try:
                    self._environment_builder.build(
                        PackageEnvironmentBuildRequest(
                            release_directory=plan.release_directory,
                            wheel_path=private_wheel,
                            wheelhouse=plan.wheelhouse,
                            allow_index=plan.dependency_source is DependencySource.INDEX,
                        )
                    )
                except PackageInstallError:
                    raise
                except Exception as error:
                    raise PackageInstallError(
                        f"Package environment build failed: {error}"
                    ) from error
            finally:
                private_wheel.unlink(missing_ok=True)
            self._verify_release_commands(plan.release_directory)
            self._harden_release(plan.release_directory)
            self._install_launchers(plan.launcher_directory)
            active_target = str(plan.release_directory.relative_to(self._root))
            self._switch_current(plan.current_link, target=active_target)
        except Exception:
            shutil.rmtree(plan.release_directory, ignore_errors=True)
            raise
        return PackageInstallResult(
            package_version=plan.package_version,
            release_directory=plan.release_directory,
            launcher_directory=plan.launcher_directory,
            active_target=active_target,
            previous_target=previous_target,
        )

    @staticmethod
    def _copy_verified_wheel(plan: PackageInstallPlan) -> Path:
        private_wheel = plan.release_directory / plan.wheel_path.name
        source_descriptor: int | None = None
        try:
            source_descriptor = os.open(
                plan.wheel_path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
            metadata = os.fstat(source_descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_WHEEL_BYTES:
                raise PackageInstallError("Planned package wheel is no longer a safe regular file")
            digest = hashlib.sha256()
            with (
                os.fdopen(source_descriptor, "rb") as source_file,
                private_wheel.open("xb") as destination_file,
            ):
                source_descriptor = None
                for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                    digest.update(chunk)
                    destination_file.write(chunk)
                destination_file.flush()
                os.fsync(destination_file.fileno())
        except OSError as error:
            private_wheel.unlink(missing_ok=True)
            raise PackageInstallError(f"Unable to copy planned package wheel: {error}") from error
        finally:
            if source_descriptor is not None:
                os.close(source_descriptor)
        if digest.hexdigest() != plan.wheel_sha256:
            private_wheel.unlink(missing_ok=True)
            raise PackageInstallError("Planned package wheel changed before installation")
        return private_wheel

    def _prepare_root(self) -> None:
        if self._root.is_symlink():
            raise PackageInstallError(f"Package installation root is a symlink: {self._root}")
        if self._root.exists() and not self._root.is_dir():
            raise PackageInstallError(f"Package installation root is not a directory: {self._root}")
        self._root.mkdir(mode=0o755, parents=True, exist_ok=True)
        if stat.S_IMODE(self._root.stat().st_mode) & 0o022:
            raise PackageInstallError(
                f"Package installation root is writable by group or other: {self._root}"
            )

    def _validate_existing_root(self) -> None:
        if self._root.is_symlink() or not self._root.is_dir():
            raise PackageInstallError(
                f"Package installation root is missing or unsafe: {self._root}"
            )
        if stat.S_IMODE(self._root.stat().st_mode) & 0o022:
            raise PackageInstallError(
                f"Package installation root is writable by group or other: {self._root}"
            )

    @staticmethod
    def _verify_release_commands(release_directory: Path) -> None:
        command_directory = release_directory / "venv/bin"
        for command in PACKAGE_COMMANDS:
            command_path = command_directory / command
            if (
                command_path.is_symlink()
                or not command_path.is_file()
                or not os.access(command_path, os.X_OK)
            ):
                raise PackageInstallError(
                    f"Installed package command is missing or unsafe: {command_path}"
                )

    def _verify_retained_release(self, release_directory: Path) -> None:
        trusted_uid = self._root.stat().st_uid
        for path in (release_directory, *release_directory.rglob("*")):
            metadata = path.lstat()
            if metadata.st_uid != trusted_uid:
                raise PackageInstallError(
                    f"Retained package release has an untrusted owner: {path}"
                )
            if not stat.S_ISLNK(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) & 0o022:
                raise PackageInstallError(
                    f"Retained package release is writable by group or other: {path}"
                )

    def _install_launchers(self, launcher_directory: Path) -> None:
        launcher_directory.mkdir(mode=0o755, parents=True, exist_ok=True)
        content = self._launcher_content()
        for command in PACKAGE_COMMANDS:
            self._atomic_write_executable(launcher_directory / command, content=content)

    def _launcher_content(self) -> str:
        commands = repr(PACKAGE_COMMANDS)
        current_bin = repr(str(self._root / "current/venv/bin"))
        return (
            "#!/usr/bin/python3\n"
            "import os\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"allowed = {commands}\n"
            "command = Path(sys.argv[0]).name\n"
            "if command not in allowed:\n"
            "    raise SystemExit('unsupported manager command')\n"
            f"target = Path({current_bin}) / command\n"
            "os.execv(str(target), [str(target), *sys.argv[1:]])\n"
        )

    @staticmethod
    def _atomic_write_executable(destination: Path, *, content: str) -> None:
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.chmod(0o755)
            temporary_path.replace(destination)
            VersionedPackageInstaller._sync_directory(destination.parent)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _current_target(current_link: Path) -> str | None:
        if current_link.is_symlink():
            target = current_link.readlink()
            if (
                target.is_absolute()
                or len(target.parts) != ACTIVE_TARGET_PARTS
                or target.parts[0] != "releases"
                or ACTIVE_RELEASE_PATTERN.fullmatch(target.parts[1]) is None
            ):
                raise PackageInstallError(
                    f"Current package target is outside versioned releases: {target}"
                )
            return str(target)
        if current_link.exists():
            raise PackageInstallError(f"Current package path is not a symlink: {current_link}")
        return None

    @staticmethod
    def _switch_current(current_link: Path, *, target: str) -> None:
        temporary_link = current_link.parent / f".current.{secrets.token_hex(16)}"
        try:
            temporary_link.symlink_to(target, target_is_directory=True)
            temporary_link.replace(current_link)
            VersionedPackageInstaller._sync_directory(current_link.parent)
        finally:
            temporary_link.unlink(missing_ok=True)

    @staticmethod
    def _harden_release(release_directory: Path) -> None:
        for path in (release_directory, *release_directory.rglob("*")):
            if path.is_symlink():
                continue
            mode = stat.S_IMODE(path.stat().st_mode) & ~0o022
            path.chmod(mode | (0o555 if path.is_dir() else 0o444))

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _validate_request(request: PackageInstallRequest, *, wheel_path: Path) -> None:
        if request.wheel_path.is_symlink() or not wheel_path.is_file():
            raise PackageInstallError("Package wheel must be a regular non-symlink file")
        if wheel_path.suffix != ".whl":
            raise PackageInstallError("Package source must be a wheel file")
        if wheel_path.stat().st_size > MAX_WHEEL_BYTES:
            raise PackageInstallError("Package wheel exceeds the maximum accepted size")
        if request.dependency_source is DependencySource.WHEELHOUSE:
            if request.wheelhouse is None or not request.wheelhouse.is_dir():
                raise PackageInstallError("Wheelhouse dependency mode requires a directory")
        elif request.wheelhouse is not None:
            raise PackageInstallError("Index dependency mode cannot also select a wheelhouse")

    @staticmethod
    def _read_package_version(wheel_path: Path) -> str:
        try:
            with zipfile.ZipFile(wheel_path) as archive:
                metadata_entries = [
                    item
                    for item in archive.infolist()
                    if item.filename.endswith(".dist-info/METADATA")
                ]
                if len(metadata_entries) != 1:
                    raise PackageInstallError(
                        "Package wheel must contain exactly one dist-info METADATA file"
                    )
                metadata_entry = metadata_entries[0]
                if metadata_entry.file_size > MAX_METADATA_BYTES:
                    raise PackageInstallError("Package wheel metadata exceeds the accepted size")
                metadata_text = archive.read(metadata_entry).decode("utf-8")
        except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as error:
            raise PackageInstallError(f"Unable to inspect package wheel: {error}") from error
        metadata = Parser().parsestr(metadata_text)
        normalized_name = metadata.get("Name", "").strip().lower().replace("_", "-")
        if normalized_name != PACKAGE_NAME:
            raise PackageInstallError(f"Unexpected package name: {normalized_name!r}")
        version = metadata.get("Version", "").strip()
        if SAFE_VERSION_PATTERN.fullmatch(version) is None:
            raise PackageInstallError(f"Unsafe package version: {version!r}")
        return version

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as wheel_file:
                for chunk in iter(lambda: wheel_file.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as error:
            raise PackageInstallError(f"Unable to hash package wheel: {error}") from error
        return digest.hexdigest()
