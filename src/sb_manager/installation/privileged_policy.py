"""Install the fixed filesystem and authorization policy for the root helper."""

import os
import re
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

HELPER_RELATIVE_PATH = Path("opt/sing-box-manager/venv/bin/sb-manager-privileged")
HELPER_ABSOLUTE_PATH = Path("/") / HELPER_RELATIVE_PATH
GROUP_NAME_PATTERN = re.compile(r"[a-z_][a-z0-9_-]*[$]?")


class HostPolicyInstallError(RuntimeError):
    """The host cannot safely accept the fixed privileged helper policy."""


class AuthorizationProvider(str, Enum):
    """Supported non-interactive authorization policy formats."""

    SUDO = "sudo"
    DOAS = "doas"


class AuthorizationPolicyValidator(Protocol):
    """Validate one complete policy fragment before it replaces host policy."""

    def validate(self, provider: AuthorizationProvider, path: Path) -> None: ...


class FileOwnership(Protocol):
    """Apply numeric ownership without resolving names inside the installer."""

    def set(self, path: Path, *, uid: int, gid: int) -> None: ...


class PosixFileOwnership:
    """Production ownership adapter."""

    def set(self, path: Path, *, uid: int, gid: int) -> None:
        os.chown(path, uid, gid, follow_symlinks=False)


@dataclass(frozen=True, slots=True)
class PolicyInstallResult:
    """Root-owned policy evidence for operator verification."""

    provider: AuthorizationProvider
    authorization_path: Path
    helper_path: Path


@dataclass(frozen=True, slots=True)
class HostOwnershipPolicy:
    """Numeric identities resolved by the root-only composition boundary."""

    root_uid: int
    root_gid: int
    manager_gid: int


@dataclass(frozen=True, slots=True)
class _DirectoryPolicy:
    relative_path: Path
    mode: int
    manager_group: bool


DIRECTORY_POLICIES = (
    _DirectoryPolicy(Path("var/lib/sing-box-manager"), 0o750, True),
    _DirectoryPolicy(Path("var/lib/sing-box-manager/incoming"), 0o770, True),
    _DirectoryPolicy(Path("var/lib/sing-box-manager/work"), 0o700, False),
    _DirectoryPolicy(Path("var/lib/sing-box-manager/acme"), 0o700, False),
    _DirectoryPolicy(Path("opt/sing-box-manager/core"), 0o755, False),
    _DirectoryPolicy(Path("etc/sing-box"), 0o755, False),
    _DirectoryPolicy(Path("etc/sing-box-manager/tls"), 0o755, False),
)


def render_authorization_policy(
    provider: AuthorizationProvider,
    *,
    group_name: str,
) -> str:
    """Render an exact no-arguments rule for one validated POSIX group."""
    if GROUP_NAME_PATTERN.fullmatch(group_name) is None:
        raise ValueError(f"Invalid authorization group name: {group_name!r}")
    helper = str(HELPER_ABSOLUTE_PATH)
    if provider is AuthorizationProvider.SUDO:
        return f'%{group_name} ALL=(root) NOPASSWD: {helper} ""\n'
    return f"permit nopass :{group_name} as root cmd {helper} args\n"


class HostPolicyInstaller:
    """Create fixed directories and atomically install one validated auth rule."""

    def __init__(
        self,
        *,
        root: Path,
        ownership_policy: HostOwnershipPolicy,
        validator: AuthorizationPolicyValidator,
        ownership: FileOwnership | None = None,
    ) -> None:
        self._root = root
        self._ownership_policy = ownership_policy
        self._validator = validator
        self._ownership = ownership or PosixFileOwnership()

    def install(
        self,
        provider: AuthorizationProvider,
        *,
        group_name: str,
    ) -> PolicyInstallResult:
        policy_content = render_authorization_policy(provider, group_name=group_name)
        self._require_real_root()
        helper_path = self._root / HELPER_RELATIVE_PATH
        self._require_trusted_helper(helper_path)
        for policy in DIRECTORY_POLICIES:
            self._ensure_directory(
                self._root / policy.relative_path,
                mode=policy.mode,
                gid=(
                    self._ownership_policy.manager_gid
                    if policy.manager_group
                    else self._ownership_policy.root_gid
                ),
            )
        relative_policy_path, policy_mode = {
            AuthorizationProvider.SUDO: (Path("etc/sudoers.d/sing-box-manager"), 0o440),
            AuthorizationProvider.DOAS: (Path("etc/doas.d/sing-box-manager.conf"), 0o600),
        }[provider]
        authorization_path = self._root / relative_policy_path
        self._ensure_directory(
            authorization_path.parent,
            mode=0o755,
            gid=self._ownership_policy.root_gid,
        )
        self._install_policy_file(
            provider,
            authorization_path,
            content=policy_content,
            mode=policy_mode,
        )
        return PolicyInstallResult(
            provider=provider,
            authorization_path=authorization_path,
            helper_path=helper_path,
        )

    def _require_real_root(self) -> None:
        if not self._root.is_dir() or self._root.is_symlink():
            raise HostPolicyInstallError(f"Installation root is not a real directory: {self._root}")

    def _require_trusted_helper(self, helper_path: Path) -> None:
        current = helper_path
        while current != self._root:
            if current.is_symlink():
                raise HostPolicyInstallError(f"Trusted helper path contains a symlink: {current}")
            try:
                metadata = current.stat()
            except FileNotFoundError as error:
                raise HostPolicyInstallError(
                    f"Trusted helper path is missing: {current}"
                ) from error
            if metadata.st_uid != self._ownership_policy.root_uid:
                raise HostPolicyInstallError(f"Trusted helper path is not root-owned: {current}")
            if stat.S_IMODE(metadata.st_mode) & 0o022:
                raise HostPolicyInstallError(
                    f"Trusted helper path is writable by group or other: {current}"
                )
            current = current.parent
        metadata = helper_path.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise HostPolicyInstallError(f"Trusted helper is not a regular file: {helper_path}")
        if not metadata.st_mode & stat.S_IXUSR:
            raise HostPolicyInstallError(f"Trusted helper is not owner-executable: {helper_path}")

    def _ensure_directory(self, path: Path, *, mode: int, gid: int) -> None:
        self._ensure_parent_chain(path)
        if path.is_symlink():
            raise HostPolicyInstallError(f"Managed directory is a symlink: {path}")
        if path.exists():
            if not path.is_dir():
                raise HostPolicyInstallError(f"Managed path is not a directory: {path}")
        else:
            path.mkdir(mode=mode)
        path.chmod(mode)
        self._ownership.set(path, uid=self._ownership_policy.root_uid, gid=gid)

    def _ensure_parent_chain(self, path: Path) -> None:
        relative = path.relative_to(self._root)
        current = self._root
        for component in relative.parts[:-1]:
            current /= component
            if current.is_symlink():
                raise HostPolicyInstallError(f"Managed parent is a symlink: {current}")
            if current.exists():
                if not current.is_dir():
                    raise HostPolicyInstallError(f"Managed parent is not a directory: {current}")
                continue
            current.mkdir(mode=0o755)
            self._ownership.set(
                current,
                uid=self._ownership_policy.root_uid,
                gid=self._ownership_policy.root_gid,
            )

    def _install_policy_file(
        self,
        provider: AuthorizationProvider,
        destination: Path,
        *,
        content: str,
        mode: int,
    ) -> None:
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
            temporary_path.chmod(mode)
            self._ownership.set(
                temporary_path,
                uid=self._ownership_policy.root_uid,
                gid=self._ownership_policy.root_gid,
            )
            self._validator.validate(provider, temporary_path)
            temporary_path.replace(destination)
            temporary_path = None
            self._sync_directory(destination.parent)
        except HostPolicyInstallError:
            raise
        except Exception as error:
            raise HostPolicyInstallError(
                f"Unable to install authorization policy: {error}"
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
