from dataclasses import replace
from pathlib import Path

import pytest

from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.artifacts.installation import (
    CoreActivation,
    CoreDistributionInstaller,
    CoreInstallError,
    CoreRollbackConflictError,
)
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    ArtifactVersionError,
    StagedCoreArtifact,
)


def staged_distribution(parent: Path, *, version: str, digest_character: str) -> StagedCoreArtifact:
    distribution = parent / f"staged-{version}"
    distribution.mkdir()
    binary = distribution / "sing-box"
    binary.write_text(
        f"#!/usr/bin/env python3\nprint('sing-box version {version}')\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    (distribution / "LICENSE").write_text("license", encoding="utf-8")
    return StagedCoreArtifact(
        version=version,
        architecture=ArtifactArchitecture.AMD64,
        distribution_directory=distribution,
        binary_path=binary,
        source_sha256=digest_character * 64,
    )


def installer(tmp_path: Path) -> CoreDistributionInstaller:
    return CoreDistributionInstaller(
        installation_root=tmp_path / "installation",
        apply_lock=FileApplyLock(tmp_path / "core-install.lock"),
    )


def test_first_activation_uses_an_atomic_relative_current_link(tmp_path: Path) -> None:
    staged = staged_distribution(tmp_path, version="1.14.0", digest_character="a")

    activation = installer(tmp_path).activate(staged)

    digest = "a" * 64
    expected_distribution = tmp_path / f"installation/versions/1.14.0-{digest}"
    assert activation == CoreActivation(
        version="1.14.0",
        distribution_directory=expected_distribution,
        binary_path=tmp_path / "installation/current/sing-box",
        activated_target=f"versions/1.14.0-{digest}",
        previous_target=None,
    )
    current = tmp_path / "installation/current"
    assert current.is_symlink()
    assert str(current.readlink()) == f"versions/1.14.0-{digest}"
    assert activation.binary_path.resolve() == expected_distribution / "sing-box"


def test_upgrade_retains_previous_distribution_and_can_roll_back(tmp_path: Path) -> None:
    core_installer = installer(tmp_path)
    first = core_installer.activate(
        staged_distribution(tmp_path, version="1.14.0", digest_character="a")
    )
    second = core_installer.activate(
        staged_distribution(tmp_path, version="1.14.1", digest_character="b")
    )

    rollback = core_installer.rollback(second)

    assert second.previous_target == first.activated_target
    assert rollback.active_target == first.activated_target
    assert rollback.binary_path == tmp_path / "installation/current/sing-box"
    assert rollback.binary_path.resolve() == first.distribution_directory / "sing-box"
    assert second.distribution_directory.is_dir()


def test_rollback_rejects_an_activation_that_is_no_longer_current(tmp_path: Path) -> None:
    core_installer = installer(tmp_path)
    first = core_installer.activate(
        staged_distribution(tmp_path, version="1.14.0", digest_character="a")
    )
    core_installer.activate(staged_distribution(tmp_path, version="1.14.1", digest_character="b"))

    with pytest.raises(CoreRollbackConflictError, match="no longer current"):
        core_installer.rollback(first)


def test_tampered_staged_binary_is_rejected_before_activation(tmp_path: Path) -> None:
    staged = staged_distribution(tmp_path, version="1.14.0", digest_character="a")
    staged.binary_path.write_text(
        "#!/usr/bin/env python3\nprint('sing-box version 0.0.0')\n",
        encoding="utf-8",
    )
    current = tmp_path / "installation/current"

    with pytest.raises(ArtifactVersionError, match=r"0\.0\.0"):
        installer(tmp_path).activate(staged)

    assert not current.exists()


def test_staged_distribution_links_are_rejected_before_copy(tmp_path: Path) -> None:
    staged = staged_distribution(tmp_path, version="1.14.0", digest_character="a")
    (staged.distribution_directory / "unsafe-link").symlink_to(tmp_path / "outside")

    with pytest.raises(CoreInstallError, match="unsafe entry"):
        installer(tmp_path).activate(staged)

    assert not (tmp_path / "installation").exists()


def test_untrusted_staged_digest_is_rejected_before_path_construction(tmp_path: Path) -> None:
    staged = staged_distribution(tmp_path, version="1.14.0", digest_character="a")
    untrusted = replace(staged, source_sha256="../escape")

    with pytest.raises(CoreInstallError, match="SHA-256"):
        installer(tmp_path).activate(untrusted)

    assert not (tmp_path / "installation").exists()
