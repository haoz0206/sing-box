"""Plan and explicitly authorize one trusted sing-box core update."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from sb_manager.artifacts.installation import CoreActivation
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    CoreArtifactRequest,
    CoreArtifactSource,
)
from sb_manager.seams.core_activator import CoreActivationRequest, CoreActivator


class CorePrereleaseConsentRequiredError(PermissionError):
    """A prerelease version requires a separate explicit operator choice."""


class CoreUpdateConfirmationRequiredError(PermissionError):
    """Artifact acquisition and host activation require explicit confirmation."""


class CoreArtifactAcquisitionError(RuntimeError):
    """The exact release artifact could not be acquired and verified."""


class CoreUpdateWarning(str, Enum):
    """Stable review warning rendered by the presentation catalog."""

    PRERELEASE_COMPATIBILITY_RISK = "prerelease-compatibility-risk"


@dataclass(frozen=True, slots=True)
class PlanCoreUpdateRequest:
    """Operator-selected exact core version and host architecture."""

    version: str
    architecture: ArtifactArchitecture
    allow_prerelease: bool


@dataclass(frozen=True, slots=True)
class CoreUpdatePlan:
    """Pure preview of the exact upstream artifact and trust boundary."""

    version: str
    architecture: ArtifactArchitecture
    allow_prerelease: bool
    asset_name: str
    source: str
    mutates_host: bool
    warnings: tuple[CoreUpdateWarning, ...]


@dataclass(frozen=True, slots=True)
class CoreUpdateResult:
    """Evidence returned by the privileged atomic activation."""

    activation: CoreActivation


class CoreUpdater(Protocol):
    """Public application seam consumed by the operator interface."""

    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan: ...

    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult: ...


class CoreUpdateService:
    """Keep discovery and host mutation behind a confirmed exact-version plan."""

    def __init__(
        self,
        *,
        artifact_source: CoreArtifactSource,
        core_activator: CoreActivator,
        incoming_directory: Path,
    ) -> None:
        self._artifact_source = artifact_source
        self._core_activator = core_activator
        self._incoming_directory = incoming_directory

    def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
        artifact_request = CoreArtifactRequest(
            version=request.version,
            architecture=request.architecture,
            allow_prerelease=request.allow_prerelease,
        )
        is_prerelease = "-" in artifact_request.version
        if is_prerelease and not artifact_request.allow_prerelease:
            raise CorePrereleaseConsentRequiredError(
                f"Core version {artifact_request.version} is a prerelease"
            )
        return CoreUpdatePlan(
            version=artifact_request.version,
            architecture=artifact_request.architecture,
            allow_prerelease=artifact_request.allow_prerelease,
            asset_name=(
                f"sing-box-{artifact_request.version}-linux-"
                f"{artifact_request.architecture.value}.tar.gz"
            ),
            source="SagerNet/sing-box immutable GitHub release",
            mutates_host=False,
            warnings=((CoreUpdateWarning.PRERELEASE_COMPATIBILITY_RISK,) if is_prerelease else ()),
        )

    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
        if not confirmed:
            raise CoreUpdateConfirmationRequiredError("Core update requires explicit confirmation")
        try:
            artifact = self._artifact_source.acquire(
                CoreArtifactRequest(
                    version=plan.version,
                    architecture=plan.architecture,
                    allow_prerelease=plan.allow_prerelease,
                ),
                destination_directory=self._incoming_directory,
            )
        except Exception as error:
            raise CoreArtifactAcquisitionError(str(error)) from error
        try:
            activation = self._core_activator.activate_core(
                CoreActivationRequest(
                    version=artifact.version,
                    architecture=artifact.architecture,
                    sha256=artifact.sha256,
                )
            )
        finally:
            artifact.archive_path.unlink(missing_ok=True)
        return CoreUpdateResult(activation=activation)
