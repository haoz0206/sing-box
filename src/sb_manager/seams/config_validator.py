"""Public seam for validating staged configuration artifacts."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ConfigValidationResult:
    """Typed outcome of validating one generated configuration."""

    valid: bool
    diagnostics: str


class ConfigValidator(Protocol):
    """Validate staged configuration without changing the running service."""

    def validate(self, config_path: Path) -> ConfigValidationResult: ...
