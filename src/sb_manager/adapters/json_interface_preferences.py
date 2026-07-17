"""Atomic JSON persistence for per-user interface preferences."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from sb_manager.application.interface_preferences import (
    ColorScheme,
    InterfacePreferences,
    PreferenceStoreError,
)

PREFERENCE_SCHEMA_VERSION = 1


class JsonInterfacePreferenceStore:
    """Persist one complete preference document beside no host-managed state."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> InterfacePreferences | None:
        self._ensure_safe_target()
        if not self.path.exists():
            return None
        try:
            decoded: object = json.loads(self.path.read_text(encoding="utf-8"))
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
        temporary_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_path.chmod(0o600)
                json.dump(
                    {
                        "schema_version": PREFERENCE_SCHEMA_VERSION,
                        "color_scheme": preferences.color_scheme.value,
                    },
                    temporary_file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(self.path)
        except OSError as error:
            raise PreferenceStoreError(
                "interface preference document could not be saved"
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

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
