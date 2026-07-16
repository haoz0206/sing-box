"""Read-only seam for identifying the live sing-box configuration."""

from dataclasses import dataclass
from typing import Protocol

SHA256_HEX_LENGTH = 64


class ConfigTargetInspectionError(RuntimeError):
    """The live configuration target cannot be safely identified."""


@dataclass(frozen=True, slots=True)
class LiveConfigObservation:
    """Existence and exact identity of one observed live configuration."""

    exists: bool
    sha256: str | None

    def __post_init__(self) -> None:
        if not self.exists and self.sha256 is not None:
            raise ValueError("An absent live configuration cannot have a fingerprint")
        if self.exists and (
            self.sha256 is None
            or len(self.sha256) != SHA256_HEX_LENGTH
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise ValueError("An existing live configuration requires a SHA-256 fingerprint")


class ConfigurationTargetInspector(Protocol):
    """Observe target identity without returning configuration content."""

    def inspect(self) -> LiveConfigObservation: ...
