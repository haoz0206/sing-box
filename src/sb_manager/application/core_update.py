"""Plan and explicitly authorize one trusted sing-box core update."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from sb_manager.artifacts.installation import (
    CoreActivation,
    CoreReleaseIdentity,
    InstalledCoreRelease,
)
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    CoreArtifactRequest,
    CoreArtifactSource,
    CoreArtifactTrustMode,
    CoreReleaseChannel,
    CoreReleaseSource,
    PlannedCoreArtifact,
)
from sb_manager.seams.core_activator import CoreActivationRequest, CoreActivator
from sb_manager.seams.core_inventory import CoreInventory
from sb_manager.seams.core_switcher import CoreSwitcher, CoreSwitchRequest


class CorePrereleaseConsentRequiredError(PermissionError):
    """A prerelease version requires a separate explicit operator choice."""


class CoreUpdateConfirmationRequiredError(PermissionError):
    """Artifact acquisition and host activation require explicit confirmation."""


class CoreArtifactAcquisitionError(RuntimeError):
    """The exact release artifact could not be acquired and verified."""


class CoreUpdateWarning(str, Enum):
    """Stable review warning rendered by the presentation catalog."""

    PRERELEASE_COMPATIBILITY_RISK = "prerelease-compatibility-risk"
    DIGEST_PINNED_MUTABLE_RELEASE = "digest-pinned-mutable-release"


@dataclass(frozen=True, slots=True)
class PlanCoreUpdateRequest:
    """Operator-selected exact core version and host architecture."""

    version: str
    architecture: ArtifactArchitecture
    allow_prerelease: bool


@dataclass(frozen=True, slots=True)
class CoreUpdatePlan:
    """Pure preview of the exact upstream artifact and trust boundary."""

    artifact: PlannedCoreArtifact
    mutates_host: bool
    warnings: tuple[CoreUpdateWarning, ...]

    @property
    def version(self) -> str:
        return self.artifact.version

    @property
    def architecture(self) -> ArtifactArchitecture:
        return self.artifact.architecture

    @property
    def asset_name(self) -> str:
        return self.artifact.asset_name

    @property
    def allow_prerelease(self) -> bool:
        return self.artifact.prerelease

    @property
    def source(self) -> str:
        return "SagerNet/sing-box official GitHub release"


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
        requested_prerelease = "-" in artifact_request.version.partition("+")[0]
        if requested_prerelease and not artifact_request.allow_prerelease:
            raise CorePrereleaseConsentRequiredError(
                f"Core version {artifact_request.version} is a prerelease"
            )
        try:
            artifact = self._artifact_source.inspect(artifact_request)
            if (
                artifact.version != artifact_request.version
                or artifact.architecture is not artifact_request.architecture
                or artifact.prerelease is not requested_prerelease
            ):
                raise CoreArtifactAcquisitionError(
                    "Artifact inspection returned evidence for a different requested release"
                )
        except CoreArtifactAcquisitionError:
            raise
        except Exception as error:
            raise CoreArtifactAcquisitionError(str(error)) from error
        warnings: list[CoreUpdateWarning] = []
        if artifact.prerelease:
            warnings.append(CoreUpdateWarning.PRERELEASE_COMPATIBILITY_RISK)
        if artifact.trust_mode is CoreArtifactTrustMode.DIGEST_PINNED_STABLE:
            warnings.append(CoreUpdateWarning.DIGEST_PINNED_MUTABLE_RELEASE)
        return CoreUpdatePlan(
            artifact=artifact,
            mutates_host=False,
            warnings=tuple(warnings),
        )

    def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
        if not confirmed:
            raise CoreUpdateConfirmationRequiredError("Core update requires explicit confirmation")
        try:
            artifact = self._artifact_source.acquire(
                plan.artifact,
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


class CoreChannelPlanKind(str, Enum):
    """Exact action selected after discovery and installed-release inspection."""

    ALREADY_CURRENT = "already-current"
    SWITCH_RETAINED = "switch-retained"
    ACQUIRE_AND_ACTIVATE = "acquire-and-activate"


class CoreChannelPlanningError(RuntimeError):
    """Channel discovery and installed state did not produce one safe plan."""


@dataclass(frozen=True, slots=True)
class PlanCoreChannelRequest:
    """Operator-selected release policy and the managed host architecture."""

    channel: CoreReleaseChannel
    architecture: ArtifactArchitecture


@dataclass(frozen=True, slots=True)
class CoreChannelPlan:
    """One discovered exact release and its frozen host action."""

    kind: CoreChannelPlanKind
    channel: CoreReleaseChannel
    version: str
    architecture: ArtifactArchitecture
    prerelease: bool
    requires_confirmation: bool
    target: CoreReleaseIdentity | None
    expected_active: CoreReleaseIdentity | None
    exact_update: CoreUpdatePlan | None


class CoreChannelManager(Protocol):
    """Public application seam consumed by the channel-management interface."""

    def plan(self, request: PlanCoreChannelRequest) -> CoreChannelPlan: ...

    def execute(self, plan: CoreChannelPlan, *, confirmed: bool) -> CoreUpdateResult: ...


class CoreChannelService:
    """Choose one exact channel action without putting policy in the TUI."""

    def __init__(
        self,
        *,
        release_source: CoreReleaseSource,
        core_inventory: CoreInventory,
        core_updater: CoreUpdater,
        core_switcher: CoreSwitcher,
    ) -> None:
        self._release_source = release_source
        self._core_inventory = core_inventory
        self._core_updater = core_updater
        self._core_switcher = core_switcher

    def plan(self, request: PlanCoreChannelRequest) -> CoreChannelPlan:
        release = self._release_source.latest(request.channel)
        if release.channel is not request.channel:
            raise CoreChannelPlanningError(
                f"Release source returned {release.channel.value} for requested "
                f"{request.channel.value} channel"
            )
        expected_prerelease = request.channel is CoreReleaseChannel.PREVIEW
        if release.prerelease is not expected_prerelease:
            raise CoreChannelPlanningError(
                f"Release source returned an inconsistent prerelease classification "
                f"for {request.channel.value} channel"
            )
        installed = self._core_inventory.list_installed()
        target = self._one_matching_release(
            installed,
            version=release.version,
            architecture=request.architecture,
        )
        if target is not None and target.active:
            identity = self._identity(target)
            return CoreChannelPlan(
                kind=CoreChannelPlanKind.ALREADY_CURRENT,
                channel=release.channel,
                version=release.version,
                architecture=request.architecture,
                prerelease=release.prerelease,
                requires_confirmation=False,
                target=identity,
                expected_active=identity,
                exact_update=None,
            )
        active = self._one_active_release(installed)
        if target is not None and active is not None:
            return CoreChannelPlan(
                kind=CoreChannelPlanKind.SWITCH_RETAINED,
                channel=release.channel,
                version=release.version,
                architecture=request.architecture,
                prerelease=release.prerelease,
                requires_confirmation=True,
                target=self._identity(target),
                expected_active=self._identity(active),
                exact_update=None,
            )
        exact_update = self._core_updater.plan(
            PlanCoreUpdateRequest(
                version=release.version,
                architecture=request.architecture,
                allow_prerelease=release.prerelease,
            )
        )
        return CoreChannelPlan(
            kind=CoreChannelPlanKind.ACQUIRE_AND_ACTIVATE,
            channel=release.channel,
            version=release.version,
            architecture=request.architecture,
            prerelease=release.prerelease,
            requires_confirmation=True,
            target=None,
            expected_active=self._identity(active) if active is not None else None,
            exact_update=exact_update,
        )

    def execute(self, plan: CoreChannelPlan, *, confirmed: bool) -> CoreUpdateResult:
        if plan.kind is CoreChannelPlanKind.SWITCH_RETAINED:
            if not confirmed:
                raise CoreUpdateConfirmationRequiredError(
                    "Core channel switch requires confirmation"
                )
            if plan.target is None or plan.expected_active is None:
                raise CoreChannelPlanningError("Retained switch plan is missing exact identities")
            activation = self._core_switcher.switch_core(
                CoreSwitchRequest(
                    target=plan.target,
                    expected_active=plan.expected_active,
                )
            )
            return CoreUpdateResult(activation=activation)
        if plan.kind is CoreChannelPlanKind.ACQUIRE_AND_ACTIVATE:
            if plan.exact_update is None:
                raise CoreChannelPlanningError("Acquisition plan is missing exact update evidence")
            return self._core_updater.execute(plan.exact_update, confirmed=confirmed)
        raise CoreChannelPlanningError(f"Channel plan {plan.kind.value} has no host action")

    @staticmethod
    def _one_matching_release(
        installed: tuple[InstalledCoreRelease, ...],
        *,
        version: str,
        architecture: ArtifactArchitecture,
    ) -> InstalledCoreRelease | None:
        matches = tuple(
            release
            for release in installed
            if release.version == version and release.architecture is architecture
        )
        if len(matches) > 1:
            raise CoreChannelPlanningError(
                f"Multiple installed releases match {version} for {architecture.value}"
            )
        return matches[0] if matches else None

    @staticmethod
    def _identity(release: InstalledCoreRelease) -> CoreReleaseIdentity:
        return CoreReleaseIdentity(
            version=release.version,
            architecture=release.architecture,
            source_sha256=release.source_sha256,
        )

    @staticmethod
    def _one_active_release(
        installed: tuple[InstalledCoreRelease, ...],
    ) -> InstalledCoreRelease | None:
        active = tuple(release for release in installed if release.active)
        if len(active) > 1:
            raise CoreChannelPlanningError("Multiple installed core releases are marked active")
        return active[0] if active else None
