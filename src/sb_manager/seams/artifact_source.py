"""Public seams and trusted values for sing-box release discovery and acquisition."""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


class ArtifactArchitecture(str, Enum):
    """Linux architectures with release and host verification coverage."""

    AMD64 = "amd64"
    ARM64 = "arm64"


class CoreReleaseChannel(str, Enum):
    """Operator-facing policy for resolving one exact upstream release."""

    STABLE = "stable"
    PREVIEW = "preview"


class ArtifactTrustError(RuntimeError):
    """Release metadata does not satisfy the accepted trust policy."""


class ArtifactIntegrityError(RuntimeError):
    """Downloaded bytes do not match trusted release metadata."""


class ArtifactArchiveError(RuntimeError):
    """A verified archive does not have the required safe distribution shape."""


class ArtifactVersionError(RuntimeError):
    """A staged core binary cannot prove the requested version."""


@dataclass(frozen=True, slots=True)
class CoreArtifactRequest:
    """Explicit sing-box version and platform selection."""

    version: str
    architecture: ArtifactArchitecture
    allow_prerelease: bool = False

    def __post_init__(self) -> None:
        if (
            re.fullmatch(
                r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?",
                self.version,
            )
            is None
        ):
            raise ValueError(f"Invalid artifact version: {self.version!r}")


@dataclass(frozen=True, slots=True)
class CoreRelease:
    """Exact upstream release resolved from one read-only channel policy."""

    channel: CoreReleaseChannel
    version: str
    prerelease: bool


class CoreReleaseSource(Protocol):
    """Resolve one channel policy to an exact trusted release without mutation."""

    def latest(self, channel: CoreReleaseChannel) -> CoreRelease: ...


@dataclass(frozen=True, slots=True)
class VerifiedCoreArtifact:
    """Archive whose bytes match immutable release metadata."""

    version: str
    architecture: ArtifactArchitecture
    asset_name: str
    archive_path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class StagedCoreArtifact:
    """Verified distribution ready to cross the privileged install seam."""

    version: str
    architecture: ArtifactArchitecture
    distribution_directory: Path
    binary_path: Path
    source_sha256: str


class CoreArtifactSource(Protocol):
    """Acquire one exact verified sing-box archive without installing it."""

    def acquire(
        self,
        request: CoreArtifactRequest,
        *,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact: ...
