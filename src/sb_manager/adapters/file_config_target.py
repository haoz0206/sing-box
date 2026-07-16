"""Direct filesystem adapter for live configuration identity."""

import hashlib
from pathlib import Path

from sb_manager.seams.config_target import (
    ConfigTargetInspectionError,
    LiveConfigObservation,
)


class FileConfigurationTargetInspector:
    """Hash one regular configuration file without parsing or exposing its content."""

    def __init__(self, *, config_path: Path) -> None:
        self._config_path = config_path

    def inspect(self) -> LiveConfigObservation:
        if self._config_path.is_symlink():
            raise ConfigTargetInspectionError(
                f"Live configuration target is not a regular file: {self._config_path}"
            )
        if not self._config_path.exists():
            return LiveConfigObservation(exists=False, sha256=None)
        if not self._config_path.is_file():
            raise ConfigTargetInspectionError(
                f"Live configuration target is not a regular file: {self._config_path}"
            )
        digest = hashlib.sha256()
        try:
            with self._config_path.open("rb") as config_file:
                for chunk in iter(lambda: config_file.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as error:
            raise ConfigTargetInspectionError(
                f"Unable to inspect live configuration: {error}"
            ) from error
        return LiveConfigObservation(exists=True, sha256=digest.hexdigest())
