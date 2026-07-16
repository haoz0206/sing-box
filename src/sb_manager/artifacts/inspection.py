"""Self-verification for staged or installed sing-box binaries."""

import subprocess
from pathlib import Path

from sb_manager.seams.artifact_source import ArtifactVersionError


class CoreBinaryInspector:
    """Require a core binary to self-report one exact version."""

    def verify(self, binary_path: Path, expected_version: str) -> None:
        try:
            completed = subprocess.run(
                [str(binary_path), "version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ArtifactVersionError(f"Unable to inspect staged sing-box: {error}") from error
        output = (completed.stdout or completed.stderr).strip()
        first_line = output.splitlines()[0] if output else ""
        expected_line = f"sing-box version {expected_version}"
        if completed.returncode != 0 or first_line != expected_line:
            raise ArtifactVersionError(
                f"Staged sing-box reported {first_line!r}; expected {expected_line!r}"
            )
