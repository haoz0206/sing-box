"""Read-only seam for checking the configuration projected from desired state."""

from dataclasses import dataclass
from typing import Protocol

from sb_manager.domain.installation import ManagedInstallation


class GeneratedConfigurationInspectionError(RuntimeError):
    """The projected configuration could not be checked safely."""


@dataclass(frozen=True, slots=True)
class GeneratedConfigurationObservation:
    """Semantic validation evidence for one desired-state snapshot."""

    valid: bool
    diagnostics: str


class GeneratedConfigurationInspector(Protocol):
    """Project and validate desired state without changing the host."""

    def inspect(
        self,
        installation: ManagedInstallation,
    ) -> GeneratedConfigurationObservation: ...
