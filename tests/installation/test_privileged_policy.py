import os
import stat
from pathlib import Path

import pytest

from sb_manager.installation.privileged_policy import (
    AuthorizationProvider,
    HostOwnershipPolicy,
    HostPolicyInstaller,
    HostPolicyInstallError,
    render_authorization_policy,
)

HELPER_RELATIVE_PATH = Path("opt/sing-box-manager/venv/bin/sb-manager-privileged")


class RecordingValidator:
    def __init__(self) -> None:
        self.calls: list[tuple[AuthorizationProvider, str, int]] = []

    def validate(self, provider: AuthorizationProvider, path: Path) -> None:
        self.calls.append(
            (
                provider,
                path.read_text(encoding="utf-8"),
                stat.S_IMODE(path.stat().st_mode),
            )
        )


class RecordingOwnership:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, int, int]] = []

    def set(self, path: Path, *, uid: int, gid: int) -> None:
        self.calls.append((path, uid, gid))


class RejectingValidator:
    def validate(self, provider: AuthorizationProvider, path: Path) -> None:
        raise HostPolicyInstallError("native parser rejected policy")


def write_helper(root: Path, *, mode: int = 0o755) -> Path:
    helper = root / HELPER_RELATIVE_PATH
    helper.parent.mkdir(parents=True)
    helper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    helper.chmod(mode)
    return helper


def installer(
    root: Path,
) -> tuple[HostPolicyInstaller, RecordingValidator, RecordingOwnership]:
    validator = RecordingValidator()
    ownership = RecordingOwnership()
    return (
        HostPolicyInstaller(
            root=root,
            ownership_policy=HostOwnershipPolicy(
                root_uid=os.geteuid(),
                root_gid=os.getegid(),
                manager_gid=os.getegid(),
            ),
            validator=validator,
            ownership=ownership,
        ),
        validator,
        ownership,
    )


def test_authorization_policies_allow_only_the_argument_free_fixed_helper() -> None:
    assert render_authorization_policy(
        AuthorizationProvider.SUDO,
        group_name="sing-box-manager",
    ) == (
        "%sing-box-manager ALL=(root) NOPASSWD: "
        '/opt/sing-box-manager/venv/bin/sb-manager-privileged ""\n'
    )
    assert render_authorization_policy(
        AuthorizationProvider.DOAS,
        group_name="sing-box-manager",
    ) == (
        "permit nopass :sing-box-manager as root cmd "
        "/opt/sing-box-manager/venv/bin/sb-manager-privileged args\n"
    )


@pytest.mark.parametrize(
    ("provider", "relative_policy_path", "policy_mode"),
    (
        (AuthorizationProvider.SUDO, Path("etc/sudoers.d/sing-box-manager"), 0o440),
        (AuthorizationProvider.DOAS, Path("etc/doas.d/sing-box-manager.conf"), 0o600),
    ),
)
def test_installer_creates_fixed_directories_and_validated_authorization(
    tmp_path: Path,
    provider: AuthorizationProvider,
    relative_policy_path: Path,
    policy_mode: int,
) -> None:
    root = tmp_path / "host"
    root.mkdir()
    write_helper(root)
    policy_installer, validator, ownership = installer(root)

    result = policy_installer.install(provider, group_name="sing-box-manager")

    expected_directories = {
        Path("var/lib/sing-box-manager"): 0o750,
        Path("var/lib/sing-box-manager/incoming"): 0o770,
        Path("var/lib/sing-box-manager/work"): 0o700,
        Path("var/lib/sing-box-manager/acme"): 0o700,
        Path("opt/sing-box-manager/core"): 0o755,
        Path("etc/sing-box"): 0o755,
        Path("etc/sing-box-manager/tls"): 0o755,
    }
    for relative_path, expected_mode in expected_directories.items():
        path = root / relative_path
        assert path.is_dir()
        assert not path.is_symlink()
        assert stat.S_IMODE(path.stat().st_mode) == expected_mode
    assert result.authorization_path == root / relative_policy_path
    assert result.authorization_path.read_text(encoding="utf-8") == (
        render_authorization_policy(provider, group_name="sing-box-manager")
    )
    assert stat.S_IMODE(result.authorization_path.stat().st_mode) == policy_mode
    assert validator.calls == [
        (
            provider,
            render_authorization_policy(provider, group_name="sing-box-manager"),
            policy_mode,
        )
    ]
    assert any(path == root / "var/lib/sing-box-manager/incoming" for path, _, _ in ownership.calls)


def test_installer_rejects_a_helper_writable_by_group_or_other(tmp_path: Path) -> None:
    root = tmp_path / "host"
    root.mkdir()
    write_helper(root, mode=0o775)
    policy_installer, validator, _ = installer(root)

    with pytest.raises(HostPolicyInstallError, match="group or other"):
        policy_installer.install(AuthorizationProvider.SUDO, group_name="sing-box-manager")

    assert validator.calls == []
    assert not (root / "etc/sudoers.d/sing-box-manager").exists()


def test_installer_rejects_symlinked_managed_directories(tmp_path: Path) -> None:
    root = tmp_path / "host"
    root.mkdir()
    write_helper(root)
    outside = tmp_path / "outside"
    outside.mkdir()
    managed_parent = root / "var/lib/sing-box-manager"
    managed_parent.parent.mkdir(parents=True)
    managed_parent.symlink_to(outside, target_is_directory=True)
    policy_installer, validator, _ = installer(root)

    with pytest.raises(HostPolicyInstallError, match="symlink"):
        policy_installer.install(AuthorizationProvider.DOAS, group_name="sing-box-manager")

    assert validator.calls == []


def test_validator_rejection_preserves_existing_authorization(tmp_path: Path) -> None:
    root = tmp_path / "host"
    root.mkdir()
    write_helper(root)
    policy_path = root / "etc/sudoers.d/sing-box-manager"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text("existing safe policy\n", encoding="utf-8")
    policy_installer = HostPolicyInstaller(
        root=root,
        ownership_policy=HostOwnershipPolicy(
            root_uid=os.geteuid(),
            root_gid=os.getegid(),
            manager_gid=os.getegid(),
        ),
        validator=RejectingValidator(),
        ownership=RecordingOwnership(),
    )

    with pytest.raises(HostPolicyInstallError, match="native parser rejected"):
        policy_installer.install(AuthorizationProvider.SUDO, group_name="sing-box-manager")

    assert policy_path.read_text(encoding="utf-8") == "existing safe policy\n"
    assert not any(policy_path.parent.glob(".sing-box-manager.*"))
