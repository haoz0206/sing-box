"""Read-only seam for resolving public endpoint domains from desired state."""

from dataclasses import dataclass
from typing import Protocol

from sb_manager.domain.installation import ManagedInstallation


class DomainResolutionInspectionError(RuntimeError):
    """Public domain resolution could not return trustworthy evidence."""


@dataclass(frozen=True, slots=True)
class DomainResolutionResult:
    """One normalized domain and its address or failure evidence."""

    domain: str
    addresses: tuple[str, ...]
    error: str | None

    def __post_init__(self) -> None:
        if self.addresses and self.error is not None:
            raise ValueError(
                "A domain resolution result cannot contain both addresses and an error"
            )
        if not self.addresses and self.error is None:
            raise ValueError("A domain resolution result requires addresses or an error")


@dataclass(frozen=True, slots=True)
class DomainResolutionObservation:
    """Complete DNS evidence for one desired-state snapshot."""

    results: tuple[DomainResolutionResult, ...]
    skipped_ip_addresses: int


class DomainResolutionInspector(Protocol):
    """Resolve every relevant public domain without changing desired or host state."""

    def inspect(self, installation: ManagedInstallation) -> DomainResolutionObservation: ...
