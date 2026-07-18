import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from sb_manager.artifacts.installation import CoreReleaseIdentity
from sb_manager.privileged.core_install import (
    PrivilegedCoreInstallPolicy,
    PrivilegedCoreInstallService,
)
from sb_manager.privileged.errors import PrivilegedInputError
from sb_manager.seams.artifact_source import ArtifactArchitecture, ArtifactIntegrityError
from sb_manager.seams.core_activator import CoreActivationRequest
from sb_manager.seams.core_switcher import CoreSwitchRequest

VERSION = "1.14.0-alpha.45"
ASSET_NAME = f"sing-box-{VERSION}-linux-amd64.tar.gz"


def write_core_archive(path: Path, *, version: str = VERSION) -> str:
    root = f"sing-box-{version}-linux-amd64"
    binary = f"#!/usr/bin/env python3\nprint('sing-box version {version}')\n".encode()
    member = tarfile.TarInfo(f"{root}/sing-box")
    member.size = len(binary)
    member.mode = 0o755
    with tarfile.open(path, "w:gz") as archive:
        archive.addfile(member, io.BytesIO(binary))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy(tmp_path: Path) -> PrivilegedCoreInstallPolicy:
    return PrivilegedCoreInstallPolicy(
        incoming_directory=tmp_path / "incoming",
        working_directory=tmp_path / "work",
        installation_root=tmp_path / "installation",
        lock_path=tmp_path / "core.lock",
    )


def request(sha256: str, *, version: str = VERSION) -> CoreActivationRequest:
    return CoreActivationRequest(
        version=version,
        architecture=ArtifactArchitecture.AMD64,
        sha256=sha256,
    )


def test_fixed_incoming_archive_is_privately_copied_and_activated(tmp_path: Path) -> None:
    install_policy = policy(tmp_path)
    install_policy.incoming_directory.mkdir()
    archive_path = install_policy.incoming_directory / ASSET_NAME
    sha256 = write_core_archive(archive_path)

    activation = PrivilegedCoreInstallService(policy=install_policy).activate_core(request(sha256))

    assert activation.version == VERSION
    assert activation.binary_path == install_policy.installation_root / "current/sing-box"
    assert activation.binary_path.resolve() == activation.distribution_directory / "sing-box"
    assert not any(path.is_file() for path in install_policy.working_directory.rglob("*"))


def test_retained_core_switch_uses_only_catalogued_release_identities(tmp_path: Path) -> None:
    install_policy = policy(tmp_path)
    install_policy.incoming_directory.mkdir()
    service = PrivilegedCoreInstallService(policy=install_policy)
    identities = []
    activations = []
    for version in ("1.13.14", "1.14.0-alpha.46"):
        asset_name = f"sing-box-{version}-linux-amd64.tar.gz"
        sha256 = write_core_archive(
            install_policy.incoming_directory / asset_name,
            version=version,
        )
        activations.append(service.activate_core(request(sha256, version=version)))
        identities.append(
            CoreReleaseIdentity(
                version=version,
                architecture=ArtifactArchitecture.AMD64,
                source_sha256=sha256,
            )
        )

    switched = service.switch_core(
        CoreSwitchRequest(
            target=identities[0],
            expected_active=identities[1],
        )
    )

    assert switched.version == "1.13.14"
    assert switched.activated_target == activations[0].activated_target
    assert switched.previous_target == activations[1].activated_target
    assert switched.binary_path.resolve() == activations[0].distribution_directory / "sing-box"


def test_incoming_digest_mismatch_never_creates_installation(tmp_path: Path) -> None:
    install_policy = policy(tmp_path)
    install_policy.incoming_directory.mkdir()
    write_core_archive(install_policy.incoming_directory / ASSET_NAME)

    with pytest.raises(ArtifactIntegrityError, match="SHA-256 mismatch"):
        PrivilegedCoreInstallService(policy=install_policy).activate_core(request("0" * 64))

    assert not install_policy.installation_root.exists()


def test_incoming_archive_symlink_is_rejected(tmp_path: Path) -> None:
    install_policy = policy(tmp_path)
    install_policy.incoming_directory.mkdir()
    outside = tmp_path / "outside.tar.gz"
    sha256 = write_core_archive(outside)
    (install_policy.incoming_directory / ASSET_NAME).symlink_to(outside)

    with pytest.raises(PrivilegedInputError, match="regular file"):
        PrivilegedCoreInstallService(policy=install_policy).activate_core(request(sha256))

    assert not install_policy.installation_root.exists()
