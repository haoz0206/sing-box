import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from sb_manager.artifacts.staging import CoreArtifactStager
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    ArtifactArchiveError,
    ArtifactIntegrityError,
    ArtifactVersionError,
    StagedCoreArtifact,
    VerifiedCoreArtifact,
)

VERSION = "1.14.0-alpha.45"
ROOT = f"sing-box-{VERSION}-linux-amd64"
EXECUTABLE_MODE = 0o755


def write_archive(
    path: Path,
    members: tuple[tuple[tarfile.TarInfo, bytes], ...],
) -> VerifiedCoreArtifact:
    with tarfile.open(path, "w:gz") as archive:
        for member, content in members:
            archive.addfile(member, io.BytesIO(content))
    return VerifiedCoreArtifact(
        version=VERSION,
        architecture=ArtifactArchitecture.AMD64,
        asset_name=path.name,
        archive_path=path,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def regular_file(name: str, content: bytes, *, mode: int = 0o644) -> tuple[tarfile.TarInfo, bytes]:
    member = tarfile.TarInfo(name)
    member.size = len(content)
    member.mode = mode
    return member, content


def version_binary(version: str = VERSION) -> tuple[tarfile.TarInfo, bytes]:
    return regular_file(
        f"{ROOT}/sing-box",
        f"#!/usr/bin/env python3\nprint('sing-box version {version}')\n".encode(),
        mode=0o755,
    )


def test_verified_distribution_is_safely_staged_and_self_identifies(tmp_path: Path) -> None:
    artifact = write_archive(
        tmp_path / f"{ROOT}.tar.gz",
        (
            version_binary(),
            regular_file(f"{ROOT}/LICENSE", b"license text"),
        ),
    )
    staging_parent = tmp_path / "staging"

    staged = CoreArtifactStager().stage(
        artifact,
        destination_directory=staging_parent,
    )

    assert staged == StagedCoreArtifact(
        version=VERSION,
        architecture=ArtifactArchitecture.AMD64,
        distribution_directory=staged.distribution_directory,
        binary_path=staged.distribution_directory / "sing-box",
        source_sha256=artifact.sha256,
    )
    assert staged.binary_path.is_file()
    assert staged.binary_path.stat().st_mode & 0o777 == EXECUTABLE_MODE
    assert (staged.distribution_directory / "LICENSE").read_text() == "license text"


@pytest.mark.parametrize("unsafe_name", (f"{ROOT}/../escape", "/absolute/sing-box"))
def test_unsafe_archive_paths_are_rejected_and_cleaned(
    tmp_path: Path,
    unsafe_name: str,
) -> None:
    artifact = write_archive(
        tmp_path / f"{ROOT}.tar.gz",
        (version_binary(), regular_file(unsafe_name, b"unsafe")),
    )
    staging_parent = tmp_path / "staging"

    with pytest.raises(ArtifactArchiveError, match="unsafe path"):
        CoreArtifactStager().stage(artifact, destination_directory=staging_parent)

    assert list(staging_parent.iterdir()) == []
    assert not (tmp_path / "escape").exists()


def test_archive_links_are_rejected_and_cleaned(tmp_path: Path) -> None:
    link = tarfile.TarInfo(f"{ROOT}/sing-box-link")
    link.type = tarfile.SYMTYPE
    link.linkname = f"{ROOT}/sing-box"
    artifact = write_archive(
        tmp_path / f"{ROOT}.tar.gz",
        (version_binary(), (link, b"")),
    )
    staging_parent = tmp_path / "staging"

    with pytest.raises(ArtifactArchiveError, match="regular files"):
        CoreArtifactStager().stage(artifact, destination_directory=staging_parent)

    assert list(staging_parent.iterdir()) == []


def test_duplicate_core_binary_is_rejected_and_cleaned(tmp_path: Path) -> None:
    artifact = write_archive(
        tmp_path / f"{ROOT}.tar.gz",
        (version_binary(), version_binary()),
    )
    staging_parent = tmp_path / "staging"

    with pytest.raises(ArtifactArchiveError, match="duplicate"):
        CoreArtifactStager().stage(artifact, destination_directory=staging_parent)

    assert list(staging_parent.iterdir()) == []


def test_staged_binary_must_report_requested_version(tmp_path: Path) -> None:
    artifact = write_archive(
        tmp_path / f"{ROOT}.tar.gz",
        (version_binary("1.13.0"),),
    )
    staging_parent = tmp_path / "staging"

    with pytest.raises(ArtifactVersionError, match=r"1\.13\.0"):
        CoreArtifactStager().stage(artifact, destination_directory=staging_parent)

    assert list(staging_parent.iterdir()) == []


def test_archive_digest_is_rechecked_before_opening(tmp_path: Path) -> None:
    artifact = write_archive(
        tmp_path / f"{ROOT}.tar.gz",
        (version_binary(),),
    )
    tampered = VerifiedCoreArtifact(
        version=artifact.version,
        architecture=artifact.architecture,
        asset_name=artifact.asset_name,
        archive_path=artifact.archive_path,
        sha256="0" * 64,
    )
    staging_parent = tmp_path / "staging"

    with pytest.raises(ArtifactIntegrityError, match="changed after acquisition"):
        CoreArtifactStager().stage(tampered, destination_directory=staging_parent)

    assert not staging_parent.exists()
