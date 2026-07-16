"""Read-only sing-box version observation."""

import subprocess
from pathlib import Path

from sb_manager.seams.core_status import CoreStatusObservation

VERSION_PREFIX = "sing-box version "
INSPECTION_TIMEOUT_SECONDS = 10


class SingBoxCoreStatusInspector:
    """Run one bounded ``sing-box version`` probe and return typed evidence."""

    def __init__(self, *, binary: str | Path) -> None:
        self._binary = str(binary)

    def inspect(self) -> CoreStatusObservation:
        try:
            completed = subprocess.run(
                [self._binary, "version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=INSPECTION_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return CoreStatusObservation(
                available=False,
                version=None,
                diagnostics=f"Unable to inspect sing-box at {self._binary}: {error}",
            )
        output = (completed.stdout or completed.stderr).strip()
        first_line = output.splitlines()[0] if output else ""
        version = first_line.removeprefix(VERSION_PREFIX)
        if (
            completed.returncode == 0
            and first_line.startswith(VERSION_PREFIX)
            and version
            and not any(character.isspace() for character in version)
        ):
            return CoreStatusObservation(
                available=True,
                version=version,
                diagnostics=first_line,
            )
        return CoreStatusObservation(
            available=False,
            version=None,
            diagnostics=(
                f"sing-box at {self._binary} reported {first_line!r}"
                if first_line
                else f"sing-box at {self._binary} returned no version information"
            ),
        )
