"""Safely stage and self-verify one trusted sing-box distribution."""

import hashlib
import hmac
import shutil
import tarfile
from pathlib import Path, PurePosixPath
from tempfile import mkdtemp

from sb_manager.artifacts.inspection import CoreBinaryInspector
from sb_manager.seams.artifact_source import (
    ArtifactArchiveError,
    ArtifactIntegrityError,
    ArtifactVersionError,
    StagedCoreArtifact,
    VerifiedCoreArtifact,
)


class CoreArtifactStager:
    """Turn a verified archive into a safe, version-proven distribution."""

    def stage(
        self,
        artifact: VerifiedCoreArtifact,
        *,
        destination_directory: Path,
    ) -> StagedCoreArtifact:
        actual_sha256 = self._hash(artifact.archive_path)
        if not hmac.compare_digest(actual_sha256, artifact.sha256):
            raise ArtifactIntegrityError(
                f"Artifact changed after acquisition: expected {artifact.sha256}, "
                f"got {actual_sha256}"
            )

        destination_directory.mkdir(parents=True, exist_ok=True)
        staging_root = Path(
            mkdtemp(
                dir=destination_directory,
                prefix=f".sing-box-{artifact.version}.",
            )
        )
        expected_root = f"sing-box-{artifact.version}-linux-{artifact.architecture.value}"
        distribution_directory = staging_root / expected_root
        try:
            binary_path = self._extract(
                artifact.archive_path,
                expected_root=expected_root,
                distribution_directory=distribution_directory,
            )
            CoreBinaryInspector().verify(binary_path, artifact.version)
        except (ArtifactArchiveError, ArtifactVersionError):
            shutil.rmtree(staging_root)
            raise
        except (OSError, tarfile.TarError) as error:
            shutil.rmtree(staging_root)
            raise ArtifactArchiveError(f"Unable to stage artifact: {error}") from error

        return StagedCoreArtifact(
            version=artifact.version,
            architecture=artifact.architecture,
            distribution_directory=distribution_directory,
            binary_path=binary_path,
            source_sha256=artifact.sha256,
        )

    def _extract(
        self,
        archive_path: Path,
        *,
        expected_root: str,
        distribution_directory: Path,
    ) -> Path:
        seen_files: set[PurePosixPath] = set()
        binary_path: Path | None = None
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive:
                relative_path = self._relative_path(member, expected_root)
                if relative_path is None:
                    continue
                if member.isdir():
                    (distribution_directory / Path(*relative_path.parts)).mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    continue
                if not member.isfile():
                    raise ArtifactArchiveError(
                        f"Archive may contain only directories and regular files: {member.name}"
                    )
                if relative_path in seen_files:
                    raise ArtifactArchiveError(f"Archive contains duplicate file: {member.name}")
                seen_files.add(relative_path)

                target = distribution_directory / Path(*relative_path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise ArtifactArchiveError(f"Cannot read archive member: {member.name}")
                with source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                if relative_path == PurePosixPath("sing-box"):
                    target.chmod(0o755)
                    if binary_path is not None:
                        raise ArtifactArchiveError("Archive contains duplicate core binary")
                    binary_path = target
                else:
                    target.chmod(0o644)

        if binary_path is None:
            raise ArtifactArchiveError("Archive contains no sing-box core binary")
        return binary_path

    @staticmethod
    def _relative_path(member: tarfile.TarInfo, expected_root: str) -> PurePosixPath | None:
        member_path = PurePosixPath(member.name)
        parts = member_path.parts
        if member_path.is_absolute() or ".." in parts or not parts or parts[0] != expected_root:
            raise ArtifactArchiveError(f"Archive contains unsafe path: {member.name}")
        if len(parts) == 1:
            if member.isdir():
                return None
            raise ArtifactArchiveError(f"Archive contains unsafe path: {member.name}")
        return PurePosixPath(*parts[1:])

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as artifact_file:
            while chunk := artifact_file.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
