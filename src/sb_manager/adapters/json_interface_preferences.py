"""Atomic JSON persistence for per-user interface preferences."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from sb_manager.application.interface_preferences import (
    ColorScheme,
    InterfacePreferences,
    PreferenceResetCandidate,
    PreferenceResetConflictError,
    PreferenceStoreError,
)

PREFERENCE_SCHEMA_VERSION = 1
MAX_PREFERENCE_DOCUMENT_BYTES = 64 * 1024


class JsonInterfacePreferenceStore:
    """Persist one complete preference document beside no host-managed state."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> InterfacePreferences | None:
        self._ensure_safe_target()
        if not self.path.exists():
            return None
        try:
            decoded: object = json.loads(self._read_document_bytes())
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise PreferenceStoreError("interface preference document is unreadable") from error
        if not isinstance(decoded, dict) or set(decoded) != {
            "schema_version",
            "color_scheme",
        }:
            raise PreferenceStoreError("interface preference document has an invalid shape")
        if decoded["schema_version"] != PREFERENCE_SCHEMA_VERSION:
            raise PreferenceStoreError("unsupported interface preference schema")
        color_scheme = decoded["color_scheme"]
        if not isinstance(color_scheme, str):
            raise PreferenceStoreError("interface preference color scheme is invalid")
        try:
            return InterfacePreferences(color_scheme=ColorScheme(color_scheme))
        except ValueError as error:
            raise PreferenceStoreError("interface preference color scheme is invalid") from error

    def save(self, preferences: InterfacePreferences) -> None:
        self._ensure_safe_target()
        if self.path.exists():
            self.load()
        self._write_preferences(preferences)

    def inspect_reset_candidate(self) -> PreferenceResetCandidate:
        self._ensure_reset_is_required()
        payload = self._read_document_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        return PreferenceResetCandidate(
            expected_sha256=digest,
            archive_path=self._archive_path(digest),
        )

    def reset_candidate(
        self,
        *,
        expected_sha256: str,
        preferences: InterfacePreferences,
    ) -> Path:
        self._ensure_reset_is_required()
        payload = self._read_document_bytes()
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            raise PreferenceResetConflictError(
                "interface preference document changed after reset review"
            )
        archive_path = self._archive_path(expected_sha256)
        self._preserve_archive(archive_path, payload)
        self._write_preferences(preferences)
        return archive_path

    def _write_preferences(self, preferences: InterfacePreferences) -> None:
        payload = (
            json.dumps(
                {
                    "schema_version": PREFERENCE_SCHEMA_VERSION,
                    "color_scheme": preferences.color_scheme.value,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode()
        self._atomic_write(self.path, payload)

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_path.chmod(0o600)
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(path)
        except OSError as error:
            raise PreferenceStoreError(
                "interface preference document could not be saved"
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _ensure_reset_is_required(self) -> None:
        self._ensure_safe_target()
        if not self.path.exists():
            raise PreferenceStoreError("interface preference reset is not required")
        try:
            self.load()
        except PreferenceStoreError:
            pass
        else:
            raise PreferenceStoreError("interface preference reset is not required")

    def _read_document_bytes(self) -> bytes:
        try:
            if self.path.stat().st_size > MAX_PREFERENCE_DOCUMENT_BYTES:
                raise PreferenceStoreError("interface preference document is too large")
            payload = self.path.read_bytes()
        except OSError as error:
            raise PreferenceStoreError("interface preference document could not be read") from error
        if len(payload) > MAX_PREFERENCE_DOCUMENT_BYTES:
            raise PreferenceStoreError("interface preference document is too large")
        return payload

    def _archive_path(self, digest: str) -> Path:
        return self.path.with_name(f"{self.path.name}.rejected-{digest}.json")

    def _preserve_archive(self, archive_path: Path, payload: bytes) -> None:
        try:
            if archive_path.exists():
                self._ensure_archive_matches(archive_path, payload)
                return
            self._publish_archive_exclusively(archive_path, payload)
        except OSError as error:
            raise PreferenceStoreError(
                "interface preference archive could not be preserved"
            ) from error

    def _publish_archive_exclusively(self, archive_path: Path, payload: bytes) -> None:
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=archive_path.parent,
                prefix=f".{archive_path.name}.",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_path.chmod(0o600)
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            try:
                os.link(temporary_path, archive_path)
            except FileExistsError:
                self._ensure_archive_matches(archive_path, payload)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _ensure_archive_matches(archive_path: Path, payload: bytes) -> None:
        if archive_path.is_symlink() or not archive_path.is_file():
            raise PreferenceStoreError("interface preference archive target is not a regular file")
        if archive_path.stat().st_size != len(payload) or archive_path.read_bytes() != payload:
            raise PreferenceStoreError("interface preference archive does not match reviewed bytes")

    def _ensure_safe_target(self) -> None:
        try:
            if self.path.is_symlink() or (self.path.exists() and not self.path.is_file()):
                raise PreferenceStoreError(
                    "interface preference target is not a manager-owned regular file"
                )
        except OSError as error:
            raise PreferenceStoreError(
                "interface preference target could not be inspected"
            ) from error
