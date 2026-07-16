"""Crash-safe recovery adapter for JSON desired-state files."""

import json
import os
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

from sb_manager.adapters.json_file_state import JsonFileStateStore
from sb_manager.seams.state_recovery import (
    StateFileCondition,
    StateFileSnapshot,
    StateRecoveryCommit,
    StateRecoveryPreconditionError,
    StateRecoverySnapshot,
    StateRecoverySourceError,
)
from sb_manager.seams.state_store import UnsupportedStateSchemaError

_CORRUPT_STATE_ERRORS = (
    json.JSONDecodeError,
    UnicodeDecodeError,
    KeyError,
    TypeError,
    ValueError,
    AttributeError,
)


class JsonStateRecoverySource:
    """Inspect exact state bytes and atomically restore a reviewed backup."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.backup_path = path.with_name(f"{path.name}.bak")

    def inspect(self) -> StateRecoverySnapshot:
        return StateRecoverySnapshot(
            primary=self._inspect_path(self.path),
            backup=self._inspect_path(self.backup_path),
        )

    def restore(
        self,
        *,
        expected_primary_sha256: str,
        expected_backup_sha256: str,
    ) -> StateRecoveryCommit:
        try:
            return self._restore(
                expected_primary_sha256=expected_primary_sha256,
                expected_backup_sha256=expected_backup_sha256,
            )
        except StateRecoverySourceError:
            raise
        except OSError as error:
            raise StateRecoverySourceError(
                "Desired-state recovery could not establish a durable result"
            ) from error

    def _restore(
        self,
        *,
        expected_primary_sha256: str,
        expected_backup_sha256: str,
    ) -> StateRecoveryCommit:
        primary = self._read_exact(self.path, expected_primary_sha256)
        backup = self._read_exact(self.backup_path, expected_backup_sha256)
        primary_snapshot = self._inspect_payload(primary)
        backup_snapshot = self._inspect_payload(backup)
        if primary_snapshot.condition is not StateFileCondition.CORRUPT:
            raise StateRecoveryPreconditionError("Primary state is no longer corrupt")
        if (
            backup_snapshot.condition is not StateFileCondition.READABLE
            or backup_snapshot.installation is None
        ):
            raise StateRecoveryPreconditionError("Backup state is no longer readable")

        archive_path = self.path.with_name(f"{self.path.name}.corrupt-{expected_primary_sha256}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._preserve_once(archive_path, primary)
        self._sync_directory(self.path.parent)
        self._replace_atomically(self.path, backup)
        self._sync_directory(self.path.parent)
        return StateRecoveryCommit(
            installation=backup_snapshot.installation,
            corrupt_archive_path=archive_path,
        )

    def _inspect_path(self, path: Path) -> StateFileSnapshot:
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            return StateFileSnapshot(condition=StateFileCondition.MISSING)
        except OSError:
            return StateFileSnapshot(condition=StateFileCondition.INACCESSIBLE)
        return self._inspect_payload(payload)

    @staticmethod
    def _inspect_payload(payload: bytes) -> StateFileSnapshot:
        fingerprint = sha256(payload).hexdigest()
        try:
            installation = JsonFileStateStore.load_payload(payload)
        except UnsupportedStateSchemaError as error:
            return StateFileSnapshot(
                condition=StateFileCondition.UNSUPPORTED_SCHEMA,
                sha256=fingerprint,
                schema_version=error.found,
            )
        except _CORRUPT_STATE_ERRORS:
            return StateFileSnapshot(
                condition=StateFileCondition.CORRUPT,
                sha256=fingerprint,
            )
        return StateFileSnapshot(
            condition=StateFileCondition.READABLE,
            sha256=fingerprint,
            installation=installation,
            schema_version=installation.schema_version,
        )

    @staticmethod
    def _read_exact(path: Path, expected_sha256: str) -> bytes:
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise StateRecoveryPreconditionError(
                "Reviewed state file is no longer readable"
            ) from error
        if sha256(payload).hexdigest() != expected_sha256:
            raise StateRecoveryPreconditionError("Reviewed state file changed")
        return payload

    @classmethod
    def _preserve_once(cls, path: Path, payload: bytes) -> None:
        try:
            existing = path.read_bytes()
        except FileNotFoundError:
            cls._link_atomically(path, payload)
            return
        except OSError as error:
            raise StateRecoveryPreconditionError(
                "Corrupt-state archive cannot be verified"
            ) from error
        if existing != payload:
            raise StateRecoveryPreconditionError("Corrupt-state archive path is occupied")

    @staticmethod
    def _link_atomically(path: Path, payload: bytes) -> None:
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                if path.read_bytes() != payload:
                    raise StateRecoveryPreconditionError(
                        "Corrupt-state archive path is occupied"
                    ) from None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _replace_atomically(path: Path, payload: bytes) -> None:
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
