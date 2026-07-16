"""Public seam for activating one already acquired trusted core archive."""

from dataclasses import dataclass
from typing import Protocol

from sb_manager.artifacts.installation import CoreActivation
from sb_manager.seams.artifact_source import ArtifactArchitecture


class CoreActivationError(RuntimeError):
    """One requested core activation did not produce trusted host evidence."""


@dataclass(frozen=True, slots=True)
class CoreActivationRequest:
    """Exact artifact identity allowed to cross the privileged seam."""

    version: str
    architecture: ArtifactArchitecture
    sha256: str


class CoreActivator(Protocol):
    """Activate one exact archive already present in the fixed incoming directory."""

    def activate_core(self, request: CoreActivationRequest) -> CoreActivation: ...
