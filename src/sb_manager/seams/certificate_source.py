"""Read-only seam for certificate validity evidence without private keys."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Protocol


class CertificateTargetKind(str, Enum):
    """Supported locations for manager-declared X.509 material."""

    OPERATOR_FILE = "operator-file"
    CERTMAGIC_ACME = "certmagic-acme"


@dataclass(frozen=True, slots=True)
class CertificateTarget:
    """Public certificate location derived from desired state."""

    kind: CertificateTargetKind
    server_name: str
    location: Path


class CertificateMaterialState(str, Enum):
    """Typed result of locating and decoding one certificate target."""

    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CertificateObservation:
    """Public leaf-certificate evidence or a typed reason it is absent."""

    target: CertificateTarget
    state: CertificateMaterialState
    source_label: str
    diagnostics: str
    not_valid_before: datetime | None = None
    not_valid_after: datetime | None = None
    dns_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state is CertificateMaterialState.AVAILABLE:
            if self.not_valid_before is None or self.not_valid_after is None:
                raise ValueError("Available certificate requires complete validity timestamps")
            if (
                self.not_valid_before.utcoffset() is None
                or self.not_valid_after.utcoffset() is None
            ):
                raise ValueError("Certificate validity timestamps must be timezone-aware")
            if self.not_valid_before >= self.not_valid_after:
                raise ValueError("Certificate validity interval must increase")
            if not self.dns_names:
                raise ValueError("Available certificate requires at least one DNS name")
        elif (
            self.not_valid_before is not None or self.not_valid_after is not None or self.dns_names
        ):
            raise ValueError("Unavailable certificate evidence must not include validity metadata")


@dataclass(frozen=True, slots=True)
class CertificateInspection:
    """Independent observations for the requested certificate targets."""

    observations: tuple[CertificateObservation, ...]


class CertificateInspectionError(RuntimeError):
    """The certificate source could not complete a trustworthy inspection."""


class CertificateSource(Protocol):
    """Inspect public certificate material without returning PEM or private keys."""

    def inspect(self, targets: Collection[CertificateTarget]) -> CertificateInspection: ...
