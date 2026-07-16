"""System seam for building one isolated manager Python environment."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PackageEnvironmentBuildRequest:
    """Fixed destination and explicit dependency source for one environment build."""

    release_directory: Path
    wheel_path: Path
    wheelhouse: Path | None
    allow_index: bool


class PackageEnvironmentBuilder(Protocol):
    """Build all installed console commands below one inactive release directory."""

    def build(self, request: PackageEnvironmentBuildRequest) -> None: ...
