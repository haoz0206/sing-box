"""Read-only seam for observing the configured sing-box executable."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CoreStatusObservation:
    """Availability and self-reported version of one configured core binary."""

    available: bool
    version: str | None
    diagnostics: str

    def __post_init__(self) -> None:
        if self.available and not self.version:
            raise ValueError("An available core requires a version")
        if not self.available and self.version is not None:
            raise ValueError("An unavailable core cannot have a version")


class CoreStatusInspector(Protocol):
    """Observe core availability without changing the host."""

    def inspect(self) -> CoreStatusObservation: ...
