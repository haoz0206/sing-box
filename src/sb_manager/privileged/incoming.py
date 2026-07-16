"""Race-resistant private copies of unprivileged incoming files."""

import hashlib
import hmac
import os
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile

from sb_manager.privileged.errors import PrivilegedInputError
from sb_manager.seams.artifact_source import ArtifactIntegrityError

COPY_CHUNK_BYTES = 1024 * 1024


def require_real_directory(path: Path, *, role: str) -> None:
    if not path.is_dir() or path.is_symlink():
        raise PrivilegedInputError(f"{role} must be a real directory: {path}")


def prepare_private_directory(path: Path) -> None:
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.is_symlink():
        raise PrivilegedInputError("Private working directory must not be a symlink")
    path.chmod(0o700)


class VerifiedIncomingFileCopier:
    """Open without following links and hash while copying into private storage."""

    def __init__(self, *, working_directory: Path) -> None:
        self._working_directory = working_directory

    def copy(
        self,
        source_path: Path,
        *,
        expected_sha256: str,
        maximum_bytes: int,
        prefix: str,
    ) -> Path:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(source_path, flags)
        except OSError as error:
            raise PrivilegedInputError(
                f"Incoming file must be a regular file: {source_path}"
            ) from error

        private_path: Path | None = None
        try:
            source_stat = os.fstat(descriptor)
            if not stat.S_ISREG(source_stat.st_mode):
                raise PrivilegedInputError(f"Incoming file must be a regular file: {source_path}")
            if source_stat.st_size > maximum_bytes:
                raise PrivilegedInputError(f"Incoming file exceeds {maximum_bytes} bytes")

            digest = hashlib.sha256()
            with (
                os.fdopen(descriptor, "rb", closefd=False) as source,
                NamedTemporaryFile(
                    mode="wb",
                    dir=self._working_directory,
                    prefix=prefix,
                    delete=False,
                ) as destination,
            ):
                private_path = Path(destination.name)
                copied_bytes = 0
                while chunk := source.read(COPY_CHUNK_BYTES):
                    copied_bytes += len(chunk)
                    if copied_bytes > maximum_bytes:
                        raise PrivilegedInputError(f"Incoming file exceeds {maximum_bytes} bytes")
                    digest.update(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())

            actual_sha256 = digest.hexdigest()
            if not hmac.compare_digest(actual_sha256, expected_sha256):
                raise ArtifactIntegrityError(
                    f"SHA-256 mismatch for {source_path.name}: "
                    f"expected {expected_sha256}, got {actual_sha256}"
                )
            private_path.chmod(0o400)
            verified_path = private_path
            private_path = None
            return verified_path
        finally:
            os.close(descriptor)
            if private_path is not None:
                private_path.unlink(missing_ok=True)
