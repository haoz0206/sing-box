"""Validation adapter backed by the sing-box executable."""

import subprocess
from pathlib import Path

from sb_manager.seams.config_validator import ConfigValidationResult


class SingBoxConfigValidator:
    """Run ``sing-box check`` against a staged configuration file."""

    def __init__(self, *, binary: str | Path = "sing-box") -> None:
        self._binary = str(binary)

    def validate(self, config_path: Path) -> ConfigValidationResult:
        try:
            completed = subprocess.run(
                [self._binary, "check", "-c", str(config_path)],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return ConfigValidationResult(
                valid=False,
                diagnostics=f"sing-box executable not found: {self._binary}",
            )
        return ConfigValidationResult(
            valid=completed.returncode == 0,
            diagnostics=(completed.stderr or completed.stdout).strip(),
        )
